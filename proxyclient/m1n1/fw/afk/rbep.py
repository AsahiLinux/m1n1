# SPDX-License-Identifier: MIT

import struct

from ..common import *
from ...utils import *
from ..asc.base import *


class AFKEPMessage(Register64):
    TYPE = 63, 48

class AFKEP_GetBuf(AFKEPMessage):
    TYPE = 63, 48, Constant(0x89)
    SIZE = 31, 16
    TAG = 15, 0

class AFKEP_GetBuf_Ack(AFKEPMessage):
    TYPE = 63, 48, Constant(0xa1)
    DVA = 47, 0

class AFKEP_InitRB(AFKEPMessage):
    OFFSET = 47, 32
    SIZE = 31, 16
    TAG = 15, 0

class AFKEP_Send(AFKEPMessage):
    TYPE = 63, 48, Constant(0xa2)
    WPTR = 31, 0

class AFKEP_Recv(AFKEPMessage):
    TYPE = 63, 48, Constant(0x85)
    WPTR = 31, 0

class AFKEP_Init(AFKEPMessage):
    TYPE = 63, 48, Constant(0x80)

class AFKEP_Init_Ack(AFKEPMessage):
    TYPE = 63, 48, Constant(0xa0)

class AFKEP_Start(AFKEPMessage):
    TYPE = 63, 48, Constant(0xa3)

class AFKEP_Start_Ack(AFKEPMessage):
    TYPE = 63, 48, Constant(0x86)

class AFKEP_Shutdown(AFKEPMessage):
    TYPE = 63, 48, Constant(0xc0)

class AFKEP_Shutdown_Ack(AFKEPMessage):
    TYPE = 63, 48, Constant(0xc1)


class AFKError(Exception):
    pass

"""
The first three blocks of the ringbuffer is reserved for exchanging size,
rptr, wptr:

           bufsize      unk
00000000  00007e80 00070006 00000000 00000000 00000000 00000000 00000000 00000000
00000020  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
00000040  *   rptr
00000080  00000600 00000000 00000000 00000000 00000000 00000000 00000000 00000000
000000a0  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
000000c0  *   wptr
00000100  00000680 00000000 00000000 00000000 00000000 00000000 00000000 00000000
00000120  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
00000140  *

Note how each block is spread out by some block_size multiple of 0x40
(step).  Here, the block_size is 0x80. The 0th block holds the bufsize,
the 1st block holds the rptr, and the 2nd block holds the wptr. The
actual contents of the ringbuffer starts after the first three blocks,
which will be called the "header". Since we're *always* given the total
block size at offset +0x0 or +block_size*0, we can calculate the block
size by dividing by 3.
"""

class AFKRingBuf(Reloadable):
    BLOCK_STEP = 0x40
    BLOCK_COUNT = 3

    def __init__(self, ep, base, size):
        self.ep = ep
        self.base = base

        bs, unk = struct.unpack("<II", self.read_buf(0, 8))
        # calculate block_size
        # bs + self.BLOCK_COUNT * block_size) == size
        assert((size - bs) % self.BLOCK_COUNT == 0)
        block_size = (size - bs) // self.BLOCK_COUNT
        assert(block_size % self.BLOCK_STEP == 0)
        self.block_size = block_size
        self.bufsize = bs
        self.rptr = 0
        self.wptr = 0

    def read_buf(self, off, size):
        return self.ep.iface.readmem(self.base + off, size)

    def write_buf(self, off, data):
        return self.ep.iface.writemem(self.base + off, data)
    
    def get_rptr(self):
        return struct.unpack("<I", self.read_buf(self.block_size * 1, 4))[0]
        #return self.ep.asc.p.read32(self.base + self.BLOCK_STEP)

    def get_wptr(self):
        return struct.unpack("<I", self.read_buf(self.block_size * 2, 4))[0]
        #return self.ep.asc.p.read32(self.base + 2 * self.BLOCK_STEP)

    def update_rptr(self, rptr):
        self.write_buf(self.block_size * 1, struct.pack("<I", rptr))
        self.ep.asc.p.write32(self.base + self.BLOCK_STEP, rptr)

    def update_wptr(self, wptr):
        self.write_buf(self.block_size * 2, struct.pack("<I", wptr))
        self.ep.asc.p.write32(self.base + 2 * self.BLOCK_STEP, wptr)

    def read(self):
        self.wptr = self.get_wptr()

        base = self.block_size * 3  # after header (size, rptr, wptr)
        while self.wptr != self.rptr:
            hdr = self.read_buf(base + self.rptr, 16)
            self.rptr += 16
            magic, size = struct.unpack("<4sI", hdr[:8])
            assert magic in [b"IOP ", b"AOP "]
            if size > (self.bufsize - self.rptr):
                hdr = self.read_buf(base, 16)
                self.rptr = 16
                magic, size = struct.unpack("<4sI", hdr[:8])
                assert magic in [b"IOP ", b"AOP "]

            payload = self.read_buf(base + self.rptr, size)
            self.rptr = (align_up(self.rptr + size, self.block_size)) % self.bufsize
            self.update_rptr(self.rptr)
            yield hdr[8:] + payload
            self.wptr = self.get_wptr()

        self.update_rptr(self.rptr)

    def write(self, data):
        base = self.block_size * 3  # after header (size, rptr, wptr)
        hdr2, data = data[:8], data[8:]
        self.rptr = self.get_rptr()
        
        if self.wptr < self.rptr and self.wptr + 0x10 >= self.rptr:
            raise AFKError("Ring buffer is full")

        hdr = struct.pack("<4sI", b"IOP ", len(data)) + hdr2
        self.write_buf(base + self.wptr, hdr)

        if len(data) > (self.bufsize - self.wptr - 16):
            if self.rptr < 0x10:
                raise AFKError("Ring buffer is full")
            self.write_buf(base, hdr)
            self.wptr = 0

        if self.wptr < self.rptr and self.wptr + 0x10 + len(data) >= self.rptr:
            raise AFKError("Ring buffer is full")

        self.write_buf(base + self.wptr + 0x10, data)
        self.wptr = align_up(self.wptr + 0x10 + len(data), self.block_size) % self.bufsize

        self.update_wptr(self.wptr)
        return self.wptr

class AFKRingBufEndpoint(ASCBaseEndpoint):
    BASE_MESSAGE = AFKEPMessage
    SHORT = "afkep"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.txq = None
        self.rxq = None
        self.iface = self.asc.iface
        self.alive = False
        self.started = False
        self.iobuffer = None
        self.verbose = 2
        self.msgid = 0

    def start(self):
        self.send(AFKEP_Init())

    def stop(self):
        self.log("Shutting down")
        self.send(AFKEP_Shutdown())
        while self.alive:
            self.asc.work()

    @msg_handler(0xa0, AFKEP_Init_Ack)
    def Init_Ack(self, msg):
        self.alive = True
        return True

    @msg_handler(0xc1, AFKEP_Shutdown_Ack)
    def Shutdown_Ack(self, msg):
        self.alive = False
        self.log("Shutdown ACKed")
        return True

    @msg_handler(0x80, AFKEP_Init)
    def Hello(self, msg):
        self.rxbuf, self.rxbuf_dva = self.asc.ioalloc(0x10000)
        self.txbuf, self.txbuf_dva = self.asc.ioalloc(0x10000)
        self.send(AFKEP_Init_Ack())
        return True

    @msg_handler(0x89, AFKEP_GetBuf)
    def GetBuf(self, msg):
        size = msg.SIZE * AFKRingBuf.BLOCK_STEP

        if self.iobuffer:
            print("WARNING: trying to reset iobuffer!")

        self.iobuffer, self.iobuffer_dva = self.asc.ioalloc(size)
        self.asc.p.write32(self.iobuffer, 0xdeadbeef)
        self.send(AFKEP_GetBuf_Ack(DVA=self.iobuffer_dva))
        self.log(f"Buffer: phys={self.iobuffer:#x} dva={self.iobuffer_dva:#x} size={size:#x}")
        return True

    @msg_handler(0x8a, AFKEP_InitRB)
    def InitTX(self, msg):
        self.txq = self.init_rb(msg)
        if self.rxq and self.txq:
            self.start_queues()
        return True

    @msg_handler(0x8b, AFKEP_InitRB)
    def InitRX(self, msg):
        self.rxq = self.init_rb(msg)
        if self.rxq and self.txq:
            self.start_queues()
        return True

    @msg_handler(0x8c, AFKEP_InitRB)
    def InitUnk(self, msg):
        return True  # no op

    def init_rb(self, msg):
        off = msg.OFFSET * AFKRingBuf.BLOCK_STEP
        size = msg.SIZE * AFKRingBuf.BLOCK_STEP
        return AFKRingBuf(self, self.iobuffer + off, size)

    def start_queues(self):
        self.send(AFKEP_Start())

    @msg_handler(0x86, AFKEP_Start_Ack)
    def Start_Ack(self, msg):
        self.started = True
        return True

    @msg_handler(0x85, AFKEP_Recv)
    def Recv(self, msg):
        for data in self.rxq.read():
            if self.verbose >= 3:
                self.log(f"<RX rptr={self.rxq.rptr:#x}")
                chexdump(data)
            self.handle_ipc(data)
        return True

    def handle_ipc(self, data):
        pass

    def send_ipc(self, data):
        wptr = self.txq.write(data)
        self.send(AFKEP_Send(WPTR = wptr))

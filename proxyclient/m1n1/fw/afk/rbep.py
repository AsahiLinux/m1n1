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

class AFKRingBuf(Reloadable):
    BLOCK_SIZE = 0x40

    def __init__(self, ep, base, size):
        self.ep = ep
        self.base = base

        bs, unk = struct.unpack("<II", self.read_buf(0, 8))
        assert (bs + 3 * self.BLOCK_SIZE) == size
        self.bufsize = bs
        self.rptr = 0
        self.wptr = 0

    def read_buf(self, off, size):
        return self.ep.iface.readmem(self.base + off, size)

    def write_buf(self, off, data):
        return self.ep.iface.writemem(self.base + off, data)
    
    def get_rptr(self):
        return self.ep.asc.p.read32(self.base + self.BLOCK_SIZE)

    def get_wptr(self):
        return self.ep.asc.p.read32(self.base + 2 * self.BLOCK_SIZE)

    def update_rptr(self, rptr):
        self.ep.asc.p.write32(self.base + self.BLOCK_SIZE, self.rptr)

    def update_wptr(self, rptr):
        self.ep.asc.p.write32(self.base + 2 * self.BLOCK_SIZE, self.wptr)

    def read(self):
        self.wptr = self.get_wptr()

        while self.wptr != self.rptr:
            hdr = self.read_buf(3 * self.BLOCK_SIZE + self.rptr, 16)
            self.rptr += 16
            magic, size = struct.unpack("<4sI", hdr[:8])
            assert magic in [b"IOP ", b"AOP "]
            if size > (self.bufsize - self.rptr):
                hdr = self.read_buf(3 * self.BLOCK_SIZE, 16)
                self.rptr = 16
                magic, size = struct.unpack("<4sI", hdr[:8])
                assert magic in [b"IOP ", b"AOP "]

            payload = self.read_buf(3 * self.BLOCK_SIZE + self.rptr, size)
            self.rptr = (align_up(self.rptr + size, self.BLOCK_SIZE)) % self.bufsize
            self.update_rptr(self.rptr)
            yield hdr[8:] + payload
            self.wptr = self.get_wptr()

        self.update_rptr(self.rptr)

    def write(self, data):
        hdr2, data = data[:8], data[8:]
        self.rptr = self.get_rptr()
        
        if self.wptr < self.rptr and self.wptr + 0x10 >= self.rptr:
            raise AFKError("Ring buffer is full")

        hdr = struct.pack("<4sI", b"IOP ", len(data)) + hdr2
        self.write_buf(3 * self.BLOCK_SIZE + self.wptr, hdr)

        if len(data) > (self.bufsize - self.wptr - 16):
            if self.rptr < 0x10:
                raise AFKError("Ring buffer is full")
            self.write_buf(3 * self.BLOCK_SIZE, hdr)
            self.wptr = 0

        if self.wptr < self.rptr and self.wptr + 0x10 + len(data) >= self.rptr:
            raise AFKError("Ring buffer is full")

        self.write_buf(3 * self.BLOCK_SIZE + self.wptr + 0x10, data)
        self.wptr = align_up(self.wptr + 0x10 + len(data), self.BLOCK_SIZE) % self.bufsize

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

    @msg_handler(0xa0, AFKEP_Init_Ack)
    def Init_Ack(self, msg):
        self.alive = True
        return True

    @msg_handler(0x89, AFKEP_GetBuf)
    def GetBuf(self, msg):
        size = msg.SIZE * AFKRingBuf.BLOCK_SIZE

        if self.iobuffer:
            print("WARNING: trying to reset iobuffer!")

        self.iobuffer, self.iobuffer_dva = self.asc.ioalloc(size)
        self.asc.p.write32(self.iobuffer, 0xdeadbeef)
        self.send(AFKEP_GetBuf_Ack(DVA=self.iobuffer_dva))
        self.log(f"Buffer: phys={self.iobuffer:#x} dva={self.iobuffer_dva:#x} size={size:#x}")
        return True

    def stop(self):
        self.log("Shutting down")
        self.send(AFKEP_Shutdown())
        while self.alive:
            self.asc.work()

    @msg_handler(0xc1, AFKEP_Shutdown_Ack)
    def Shutdown_Ack(self, msg):
        self.alive = False
        self.log("Shutdown ACKed")
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

    def init_rb(self, msg):
        off = msg.OFFSET * AFKRingBuf.BLOCK_SIZE
        size = msg.SIZE * AFKRingBuf.BLOCK_SIZE

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

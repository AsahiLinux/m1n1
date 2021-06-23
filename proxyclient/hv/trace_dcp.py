# SPDX-License-Identifier: MIT

import struct

from enum import IntEnum

from m1n1.proxyutils import RegMonitor
from m1n1.utils import *
from m1n1.trace.dart import DARTTracer
from m1n1.trace.asc import ASCTracer, EP, EPState, msg, msg_log, DIR

trace_device("/arm-io/dcp", True, ranges=[1])

DARTTracer = DARTTracer._reloadcls()
ASCTracer = ASCTracer._reloadcls()

iomon = RegMonitor(hv.u, ascii=True)

class IOEpMessage(Register64):
    TYPE = 63, 48

class IOEp_Generic(IOEpMessage):
    ARG3 = 47, 32
    ARG2 = 31, 16
    ARG1 = 15, 0

class IOEp_SetBuf_Ack(IOEpMessage):
    UNK1 = 47, 32
    IOVA = 31, 0

class IOEp_Send(IOEpMessage):
    WPTR = 31, 0

class IORingBuf(Reloadable):
    def __init__(self, ep, state, base):
        self.ep = ep
        self.dart = ep.dart
        self.state = state
        self.base = base
        self.align = 0x40

    def init(self):
        self.state.bufsize, unk = struct.unpack("<II", self.dart.ioread(0, self.base, 8))
        self.state.rptr = 0

    def read(self, max=None, wptr=None):
        wptr2 = struct.unpack("<I", self.dart.ioread(0, self.base + 0x80, 4))[0]
        assert wptr is None or wptr == wptr2

        rptr = self.state.rptr
        while wptr2 != rptr:
            hdr = self.dart.ioread(0, self.base + 0xc0 + rptr, 16)
            rptr += 16
            magic, size = struct.unpack("<4sI", hdr[:8])
            assert magic == b"IOP "
            if size > (self.state.bufsize - rptr - 16):
                hdr = self.dart.ioread(0, self.base + 0xc0, 16)
                rptr = 16
                magic, size = struct.unpack("<4sI", hdr[:8])
                assert magic == b"IOP "

            payload = self.dart.ioread(0, self.base + 0xc0 + rptr, size)
            rptr = (align_up(rptr + size, self.align)) % self.state.bufsize
            self.state.rptr = rptr
            yield hdr[8:] + payload
            if max is not None:
                max -= 1
                if max <= 0:
                    break

class IOEp(EP):
    BASE_MESSAGE = IOEp_Generic

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)
        self.state.txbuf = EPState()
        self.state.rxbuf = EPState()
        self.state.shmem_iova = None
        self.state.verbose = 1

    def start(self):
        #self.add_mon()
        self.create_bufs()

    def create_bufs(self):
        if not self.state.shmem_iova:
            return
        self.txbuf = IORingBuf(self, self.state.txbuf, self.state.shmem_iova)
        self.rxbuf = IORingBuf(self, self.state.rxbuf, self.state.shmem_iova + 0x4000)

    def add_mon(self):
        if self.state.shmem_iova:
            iomon.add(self.state.shmem_iova, 32768,
                      name=f"{self.name}.shmem@{self.state.shmem_iova:08x}", offset=0)

    Init =          msg_log(0x80, DIR.TX)
    Init_Ack =      msg_log(0xa0, DIR.RX)

    GetBuf =        msg_log(0x89, DIR.RX)

    @msg(0xa1, DIR.TX, IOEp_SetBuf_Ack)
    def GetBuf_Ack(self, msg):
        self.state.shmem_iova = msg.IOVA
        #self.add_mon()

    @msg(0xa2, DIR.TX, IOEp_Send)
    def Send(self, msg):
        for data in self.txbuf.read(wptr=msg.WPTR):
            if self.state.verbose >= 1:
                self.log(f">TX rptr={self.txbuf.state.rptr:#x}")
                chexdump(data)
        return True

    Hello =         msg_log(0xa3, DIR.TX)

    @msg(0x85, DIR.RX, IOEpMessage)
    def Recv(self, msg):
        for data in self.rxbuf.read():
            if self.state.verbose >= 1:
                self.log(f"<RX rptr={self.rxbuf.state.rptr:#x}")
                chexdump(data)
        return True

    @msg(0x8b, DIR.RX)
    def BufInitialized(self, msg):
        self.create_bufs()
        self.txbuf.init()
        self.rxbuf.init()

class DCPMessage(Register64):
    TYPE        = 3, 0
    CMD_EMPTY   = 6

class DCPEp_SetShmem(DCPMessage):
    IOVA        = 47, 16

class TxOp(IntEnum):
    ACK_REPLY   = 0
    CMD         = 2
    ACK_ASYNC   = 3
    CMD_ALT     = 6

class RxOp(IntEnum):
    REPLY       = 0
    ACK_CMD     = 2
    ASYNC       = 3
    ACK_ALT     = 6

class DCPEp_Tx(DCPMessage):
    LEN         = 63, 32
    OP          = 11, 8, TxOp

class DCPEp_Rx(DCPMessage):
    LEN         = 63, 32
    OP          = 11, 8, RxOp

KNOWN_MSGS = {
    "D581": "Cursor updated",
    "D589": "Frame presented",
    "A407": "Pre present",
    "A408": "Present",
    "A435": "Set Processing",
    "A422": "Set Night Shift",
}

class DCPEp(EP):
    BASE_MESSAGE = DCPMessage

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)
        self.state.shmem_iova = None
        self.state.show_globals = True
        self.state.show_acks = True
        self.state.max_len = 1024 * 1024
        self.state.verbosity = 3
        self.state.op_verb = {}
        self.state.req_info = None
        self.state.cmd_info = None
        self.state.alt_info = None
        self.state.async_info = None
        self.state.req_len = None
        self.state.cmd_len = None
        self.state.alt_len = None
        self.state.async_len = None

    def start(self):
        self.add_mon()

    def add_mon(self):
        if self.state.shmem_iova and self.state.show_globals:
            addr = self.state.shmem_iova + 0x80000
            iomon.add(addr, 128,
                      name=f"{self.name}.shmem@{addr:08x}", offset=addr)

    InitComplete = msg_log(1, DIR.RX)

    @msg(0, DIR.TX, DCPEp_SetShmem)
    def SetShmem(self, msg):
        self.log(f"Shared memory IOVA: {msg.IOVA:#x}")
        self.state.shmem_iova = msg.IOVA
        self.add_mon()

    @msg(2, DIR.TX, DCPEp_Tx)
    def Tx(self, msg):
        #self.log(f">{msg.OP.name} ({msg})")
        if msg.OP in (TxOp.ACK_REPLY, TxOp.CMD, TxOp.ACK_ASYNC):
            if msg.OP == TxOp.ACK_ASYNC:
                addr = self.state.shmem_iova + 0x40000
                size = self.state.async_len
                info = self.state.async_info
            else:
                addr = self.state.shmem_iova + 0x60000
                size = self.state.req_len
                info = self.state.req_info
            if size is not None:
                tag, din, dout = info
                verb = self.get_verbosity(tag)
                if verb >= 3 and len(dout) > 0:
                    dout2 = self.dart.ioread(0, addr + 12 + len(din), len(dout))
                    print(f"< Output buffer ({len(dout2):#x} bytes):")
                    chexdump(dout2[:self.state.max_len])
                if msg.OP == TxOp.ACK_ASYNC:
                    self.state.async_len = None
                else:
                    self.state.req_len = None
        if msg.LEN > 0:
            assert msg.OP in (TxOp.CMD, TxOp.CMD_ALT, TxOp.ACK_REPLY)
            addr = self.state.shmem_iova
            if msg.OP == TxOp.CMD_ALT:
                addr += 0x8000
            data = self.dart.ioread(0, addr, msg.LEN)
            tag, din, dout = self.dec_msg(data)
            if msg.OP == TxOp.CMD_ALT:
                self.state.alt_info = tag, din, dout
                self.state.alt_len = msg.LEN
            else:
                self.state.cmd_info = tag, din, dout
                self.state.cmd_len = msg.LEN

            verb = self.get_verbosity(tag)
            if verb >= 1:
                self.log(f">{msg.OP.name} {tag}:{KNOWN_MSGS.get(tag, 'unk')} ({msg})")
            if verb >= 2:
                self.show_msg(tag, din, dout)
        else:
            if self.state.show_acks:
                self.log(f">{msg.OP.name} ({msg})")

        return True

    @msg(2, DIR.RX, DCPEp_Rx)
    def Rx(self, msg):
        #self.log(f"<{msg.OP.name} ({msg})")
        if msg.OP in (RxOp.ACK_CMD, RxOp.ACK_ALT, RxOp.REPLY):
            if msg.OP == RxOp.ACK_ALT:
                addr = self.state.shmem_iova + 0x8000
                size = self.state.alt_len
                info = self.state.alt_info
            else:
                addr = self.state.shmem_iova
                size = self.state.cmd_len
                info = self.state.cmd_info
            if size is not None:
                tag, din, dout = info
                verb = self.get_verbosity(tag)
                if verb >= 3 and len(dout) > 0:
                    dout2 = self.dart.ioread(0, addr + 12 + len(din), len(dout))
                    print(f"< Output buffer ({len(dout2):#x} bytes):")
                    chexdump(dout2[:self.state.max_len])
                if msg.OP == RxOp.ACK_ALT:
                    self.state.alt_len = None
                else:
                    self.state.cmd_len = None
        if msg.LEN > 0:
            addr = self.state.shmem_iova
            if msg.OP == RxOp.ASYNC:
                addr += 0x40000
            else:
                addr += 0x60000
            data = self.dart.ioread(0, addr, msg.LEN)
            tag, din, dout = self.dec_msg(data)
            if msg.OP == RxOp.ASYNC:
                self.state.async_info = tag, din, dout
                self.state.async_len = msg.LEN
            else:
                self.state.req_info = tag, din, dout
                self.state.req_len = msg.LEN
            verb = self.get_verbosity(tag)
            if verb >= 1:
                self.log(f"<{msg.OP.name} {tag}:{KNOWN_MSGS.get(tag, 'unk')} ({msg})")
            if verb >= 2:
                self.show_msg(tag, din, dout)
        else:
            if self.state.show_acks:
                self.log(f"<{msg.OP.name} ({msg})")

        if self.state.show_globals:
            iomon.poll()
        return True

    def get_verbosity(self, tag):
        return self.state.op_verb.get(tag, self.state.verbosity)

    def set_verb_known(self, verb):
        for i in KNOWN_MSGS:
            if verb is None:
                self.state.op_verb.pop(i, None)
            else:
                self.state.op_verb[i] = verb

    def dec_msg(self, data):
        #chexdump(data)
        tag = data[:4][::-1].decode("ascii")
        size_in, size_out = struct.unpack("<II", data[4:12])
        data_in = data[12:12+size_in]
        data_out = data[12+size_in:12+size_in+size_out]
        assert len(data_in) == size_in
        if len(data_out) < size_out:
            data_out += bytes(size_out)
        return tag, data_in, data_out

    def show_msg(self, tag, data_in, data_out):
        print(f"Message: {tag} ({KNOWN_MSGS.get(tag, 'unk')}): (in {len(data_in):#x}, out {len(data_out):#x})")
        if data_in:
            print(f"> Input ({len(data_in):#x} bytes):")
            chexdump(data_in[:self.state.max_len])
        #if data_out:
            #print(f"> Output buffer ({len(data_out):#x} bytes):")
            #chexdump(data_out[:self.state.max_len])

class SystemService(IOEp):
    NAME = "system"

class TestService(IOEp):
    NAME = "test"

class DCPExpertService(IOEp):
    NAME = "dcpexpert"

class Disp0Service(IOEp):
    NAME = "disp0"

class DPTXService(IOEp):
    NAME = "dptx"

class DPSACService(IOEp):
    NAME = "dpsac"

class DPDevService(IOEp):
    NAME = "dpdev"

class MDCP29XXService(IOEp):
    NAME = "mcdp29xx"

class AVService(IOEp):
    NAME = "av"

class HDCPService(IOEp):
    NAME = "hdcp"

class RemoteAllocService(IOEp):
    NAME = "remotealloc"

class DCPTracer(ASCTracer):
    ENDPOINTS = {
        0x20: SystemService,
        0x21: TestService,
        0x22: DCPExpertService,
        0x23: Disp0Service,
        0x24: DPTXService,
        0x25: IOEp,
        0x26: DPSACService,
        0x27: DPDevService,
        0x28: MDCP29XXService,
        0x29: AVService,
        0x2a: IOEp,
        0x2b: HDCPService,
        0x2c: IOEp,
        0x2d: RemoteAllocService,
        0x37: DCPEp,
    }

    def handle_msg(self, direction, r0, r1):
        super().handle_msg(direction, r0, r1)
        #iomon.poll()

dart_dcp_tracer = DARTTracer(hv, "/arm-io/dart-dcp")
dart_dcp_tracer.start()

def readmem_iova(addr, size):
    try:
        return dart_dcp_tracer.dart.ioread(0, addr, size)
    except Exception as e:
        print(e)
        return None

iomon.readmem = readmem_iova

dcp_tracer = DCPTracer(hv, "/arm-io/dcp", verbose=1)
dcp_tracer.start(dart_dcp_tracer.dart)

# SPDX-License-Identifier: MIT
import struct
from dataclasses import dataclass
from enum import IntEnum

from ..asc.base import *
from ...utils import *

## DCP main endpoint

class DCPMessage(Register64):
    TYPE        = 3, 0

class DCPEp_SetShmem(DCPMessage):
    DVA         = 63, 16
    FLAG        = 7, 4, Constant(4)
    TYPE        = 3, 0, Constant(0)

class DCPEp_InitComplete(DCPMessage):
    TYPE        = 3, 0, Constant(1)

class CallContext(IntEnum):
    CB          = 0
    CMD         = 2
    ASYNC       = 3
    OOBCB       = 4
    OOBCMD      = 6

class DCPEp_Msg(DCPMessage):
    LEN         = 63, 32
    OFF         = 31, 16
    CTX         = 11, 8, CallContext
    ACK         = 6
    TYPE        = 3, 0, Constant(2)

@dataclass
class DCPCallState:
    tag: str
    off: int
    in_len: int
    in_data: bytes
    out_addr: int
    out_len: int
    complete: bool = False

class DCPCallChannel(Reloadable):
    def __init__(self, dcpep, name, buf, bufsize):
        self.dcp = dcpep
        self.name = name
        self.buf = buf
        self.bufsize = bufsize
        self.off = 0
        self.pending = []

    def ack(self):
        if not self.pending:
            raise Exception("ACK with no calls pending")

        self.pending[-1].complete = True

    def call(self, ctx, tag, inbuf, out_len):
        in_len = len(inbuf)
        data = tag.encode("ascii")[::-1] + struct.pack("<II", in_len, out_len) + inbuf
        data_size = len(data) + out_len
        assert (self.off + data_size) <= self.bufsize

        self.dcp.asc.iface.writemem(self.dcp.shmem + self.buf + self.off, data)

        state = DCPCallState(off=self.off, tag=tag, in_len=in_len, in_data=data, out_len=out_len,
                             out_addr=self.buf + self.off + 12 + in_len)

        self.off += align_up(data_size, 0x40)
        self.pending.append(state)

        print(f"len={data_size:#x} {in_len}")
        self.dcp.send(DCPEp_Msg(LEN=data_size, OFF=state.off, CTX=ctx, ACK=0))

        while not state.complete:
            self.dcp.asc.work()

        print(f"off={state.out_addr:#x} len={out_len}")
        out_data = self.dcp.asc.iface.readmem(self.dcp.shmem + state.out_addr, out_len)

        assert self.pending.pop() is state
        self.off = state.off

        return out_data

class DCPCallbackChannel(Reloadable):
    def __init__(self, dcpep, name, buf, bufsize):
        self.dcp = dcpep
        self.name = name
        self.buf = buf
        self.bufsize = bufsize
        self.pending = []

    def cb(self, msg):
        data = self.dcp.asc.iface.readmem(self.dcp.shmem + self.buf + msg.OFF, msg.LEN)
        tag = data[:4][::-1].decode("ascii")
        in_len, out_len = struct.unpack("<II", data[4:12])
        in_data = data[12:12 + in_len]

        state = DCPCallState(off=msg.OFF, tag=tag, in_len=in_len, out_len=out_len,
                             in_data=in_data, out_addr=self.buf + msg.OFF + 12 + in_len)

        self.pending.append(state)

        out_data = self.dcp.mgr.handle_cb(state)
        self.dcp.asc.iface.writemem(self.dcp.shmem + state.out_addr, out_data)
        self.dcp.send(DCPEp_Msg(CTX=msg.CTX, ACK=1))

        assert self.pending.pop() is state


class DCPEndpoint(ASCBaseEndpoint):
    BASE_MESSAGE = DCPMessage
    SHORT = "dcpep"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shmem = self.shmem_dva = None
        self.init_complete = False
        self.mgr = None

        self.ch_cb = DCPCallbackChannel(self, "CB", 0x60000, 0x8000)
        self.ch_cmd = DCPCallChannel(self, "CMD", 0, 0x8000)
        self.ch_async = DCPCallbackChannel(self, "ASYNC", 0x40000, 0x20000)
        self.ch_oobcb = DCPCallbackChannel(self, "OOBCB", 0x68000, 0x8000)
        self.ch_oobcmd = DCPCallChannel(self, "OOBCMD", 0x8000, 0x8000)

    @msg_handler(2, DCPEp_Msg)
    def Rx(self, msg):
        if msg.ACK:
            if msg.CTX in (CallContext.CMD, CallContext.CB):
                self.ch_cmd.ack()
            elif msg.CTX in (CallContext.OOBCMD, CallContext.OOBCB):
                self.ch_oobcmd.ack()
            else:
                raise Exception(f"Unknown RX ack channel {msg.CTX}")
        else:
            if msg.CTX == CallContext.CB:
                self.ch_cb.cb(msg)
            elif msg.CTX == CallContext.OOBCMD:
                self.ch_oobcb.cb(msg)
            elif msg.CTX == CallContext.ASYNC:
                self.ch_async.cb(msg)
            else:
                raise Exception(f"Unknown RX callback channel {msg.CTX}")
        return True

    @msg_handler(1, DCPEp_InitComplete)
    def InitComplete(self, msg):
        self.log("init complete")
        self.init_complete = True
        return True

    def initialize(self):
        self.shmem, self.shmem_dva = self.asc.ioalloc(0x100000)
        self.asc.p.memset32(self.shmem, 0, 0x100000)
        self.send(DCPEp_SetShmem(DVA=self.shmem_dva))
        while not self.init_complete:
            self.asc.work()


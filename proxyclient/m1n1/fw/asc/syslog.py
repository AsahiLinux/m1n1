# SPDX-License-Identifier: MIT
import struct

from .base import *
from ...utils import *

## Syslog endpoint

class SyslogMessage(Register64):
    TYPE        = 59, 52

class Syslog_Init(SyslogMessage):
    TYPE        = 59, 52, Constant(8)
    ENTRYSIZE   = 39, 24
    COUNT       = 15, 0

class Syslog_GetBuf(SyslogMessage):
    TYPE        = 59, 52, Constant(1)
    SIZE        = 51, 44
    DVA         = 43, 0

class Syslog_Log(SyslogMessage):
    TYPE        = 59, 52, Constant(5)
    INDEX       = 7, 0

class ASCSysLogEndpoint(ASCBaseEndpoint):
    BASE_MESSAGE = SyslogMessage
    SHORT = "syslog"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entrysize = None
        self.count = None
        self.iobuffer = None
        self.iobuffer_dva = None
        self.started = False

    @msg_handler(8, Syslog_Init)
    def Init(self, msg):
        self.entrysize = msg.ENTRYSIZE
        self.count = msg.COUNT
        self.log(f"count {self.count}, entrysize {self.entrysize}")
        return True

    @msg_handler(1, Syslog_GetBuf)
    def GetBuf(self, msg):
        size = align(0x1000 * msg.SIZE, 0x4000)

        if self.iobuffer:
            print("WARNING: trying to reset iobuffer!")

        if msg.DVA:
            self.iobuffer_dva = msg.DVA
            self.log(f"buf prealloc at dva {self.iobuffer_dva:#x}")
        else:
            self.iobuffer, self.iobuffer_dva = self.asc.ioalloc(size)
            self.log(f"buf {self.iobuffer:#x} / {self.iobuffer_dva:#x}")
            self.send(Syslog_GetBuf(SIZE=size // 0x1000, DVA=self.iobuffer_dva))

        self.started = True
        return True

    @msg_handler(5, Syslog_Log)
    def Log(self, msg):
        stride = 0x20 + self.entrysize
        log = self.asc.ioread(self.iobuffer_dva + msg.INDEX * stride, stride)
        hdr, unk, context, logmsg = struct.unpack(f"<II24s{self.entrysize}s", log)
        context = context.split(b"\x00")[0].decode("ascii")
        logmsg = logmsg.split(b"\x00")[0].decode("ascii").rstrip("\n")
        self.log(f"* [{context}]{logmsg}")
        self.send(msg)
        return True

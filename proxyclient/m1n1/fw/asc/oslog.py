# SPDX-License-Identifier: MIT
from .base import *
from ...utils import *

## OSLog endpoint

class OSLogMessage(Register64):
    TYPE = 63, 56

class OSLog_GetBuf(OSLogMessage):
    TYPE = 63, 56, Constant(1)
    SIZE = 55, 48
    DVA = 47, 0

class ASCOSLogEndpoint(ASCBaseEndpoint):
    BASE_MESSAGE = OSLogMessage
    SHORT = "iorep"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.iobuffer = None
        self.iobuffer_dva = None

    @msg_handler(1, OSLog_GetBuf)
    def GetBuf(self, msg):
        if self.iobuffer:
            self.log("WARNING: trying to reset iobuffer!")


        if msg.DVA != 0:
            self.bufsize = 0x1000 * msg.SIZE
            self.iobuffer = self.iobuffer_dva = msg.DVA << 12
            self.log(f"buf prealloc {self.iobuffer:#x} / {self.iobuffer_dva:#x}")
        else:
            self.bufsize = align(0x1000 * msg.SIZE, 0x4000)
            self.iobuffer, self.iobuffer_dva = self.asc.ioalloc(self.bufsize)
            self.log(f"buf {self.iobuffer:#x} / {self.iobuffer_dva:#x}")
            self.send(OSLog_GetBuf(DVA=self.iobuffer_dva >> 12, SIZE=self.bufsize // 0x1000))

        return True

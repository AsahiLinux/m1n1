# SPDX-License-Identifier: MIT
from .base import *
from ...utils import *

class IOReportingMessage(Register64):
    TYPE = 63, 52

class IOReporting_GetBuf(IOReportingMessage):
    TYPE = 63, 52, Constant(1)
    SIZE = 51, 44
    DVA = 43, 0

class IOReporting_Start(IOReportingMessage):
    TYPE = 63, 52, Constant(0xc)

class IOReporting_Report(IOReportingMessage):
    TYPE = 63, 52, Constant(0x8)

class ASCIOReportingEndpoint(ASCBaseEndpoint):
    BASE_MESSAGE = IOReportingMessage
    SHORT = "iorep"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.iobuffer = None
        self.iobuffer_dva = None

    @msg_handler(1, IOReporting_GetBuf)
    def GetBuf(self, msg):
        if self.iobuffer:
            self.log("WARNING: trying to reset iobuffer!")

        self.bufsize = align(0x1000 * msg.SIZE, 0x4000)
        self.iobuffer, self.iobuffer_dva = self.asc.ioalloc(self.bufsize)
        self.log(f"buf {self.iobuffer:#x} / {self.iobuffer_dva:#x}")
        self.send(IOReporting_GetBuf(DVA=self.iobuffer_dva, SIZE=self.bufsize // 0x1000))
        return True

    @msg_handler(0xc, IOReporting_Start)
    def Start(self, msg):
        self.log("start")
        return True

    @msg_handler(8, IOReporting_Report)
    def Init(self, msg):
        self.log("report!")
        buf = self.asc.iface.readmem(self.iobuffer, self.bufsize)
        #chexdump(buf)
        self.send(IOReporting_Report())
        return True

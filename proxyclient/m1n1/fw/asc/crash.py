# SPDX-License-Identifier: MIT
from .base import *
from ...utils import *

class CrashLogMessage(Register64):
    TYPE = 63, 52
    SIZE = 51, 44
    DVA = 43, 0

class ASCCrashLogEndpoint(ASCBaseEndpoint):
    SHORT = "crash"
    BASE_MESSAGE = CrashLogMessage

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.iobuffer = None
        self.iobuffer_dva = None
        self.started = False

    @msg_handler(0x1)
    def Handle(self, msg):
        if self.started:
            return self.handle_crashed(msg)
        else:
            return self.handle_getbuf(msg)

    def handle_getbuf(self, msg):
        size = 0x1000 * msg.SIZE

        if msg.DVA:
            self.iobuffer_dva = msg.DVA
            self.log(f"buf prealloc at dva {self.iobuffer_dva:#x}")
            self.send(CrashLogMessage(TYPE=1, SIZE=msg.SIZE))
        else:
            self.iobuffer, self.iobuffer_dva = self.asc.ioalloc(size)
            self.log(f"buf {self.iobuffer:#x} / {self.iobuffer_dva:#x}")
            self.send(CrashLogMessage(TYPE=1, SIZE=msg.SIZE, DVA=self.iobuffer_dva))

        self.started = True
        return True

    def crash_soft(self):
        self.send(0x40)

    def crash_hard(self):
        self.send(0x22)

    def handle_crashed(self, msg):
        size = 0x1000 * msg.SIZE

        self.log(f"Crashed!")
        crashdata = self.asc.ioread(msg.DVA, size)
        chexdump(crashdata)

        return True

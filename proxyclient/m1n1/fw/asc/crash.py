# SPDX-License-Identifier: MIT
from .base import *
from ...utils import *

class CrashLogMessage(Register64):
    TYPE = 63, 44

class CrashLog_TranslateDva(Register64):
    TYPE = 63, 44, Constant(0x104)
    ADDR = 43, 0

class CrashLog_Crashed(Register64):
    TYPE = 63, 44, Constant(0x103)
    DVA = 43, 0

class ASCCrashLogEndpoint(ASCBaseEndpoint):
    SHORT = "crash"
    BASE_MESSAGE = CrashLogMessage

    @msg_handler(0x104, CrashLog_TranslateDva)
    def TranslateDva(self, msg):
        ranges = self.asc.dart.iotranslate(0, msg.ADDR & 0xffffffff, 4096)
        assert len(ranges) == 1
        self.crashbuf = ranges[0][0]
        self.log(f"Translate {msg.ADDR:#x} -> {self.crashbuf:#x}")
        self.send(CrashLog_TranslateDva(ADDR=self.crashbuf))
        return True

    def crash_soft(self):
        self.send(0x40)

    def crash_hard(self):
        self.send(0x22)

    @msg_handler(0x103, CrashLog_Crashed)
    def Crashed(self, msg):
        self.log(f"Crashed!")
        crashdata = self.asc.dart.ioread(0, msg.DVA & 0xffffffff, 2048)
        chexdump(crashdata)

        return True

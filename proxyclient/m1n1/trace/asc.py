# SPDX-License-Identifier: MIT

from ..hv import TraceMode
from ..utils import *
from . import ADTDevTracer

class R_OUTBOX_CTRL(Register32):
    EMPTY = 17

class R_INBOX_CTRL(Register32):
    ENABLE = 1

class ASCRegs(RegMap):
    INBOX_CTRL  = 0x8110, R_INBOX_CTRL
    OUTBOX_CTRL = 0x8114, R_OUTBOX_CTRL
    INBOX0      = 0x8800, Register64
    INBOX1      = 0x8808, Register64
    OUTBOX0     = 0x8830, Register64
    OUTBOX1     = 0x8838, Register64

class ASCTracer(ADTDevTracer):
    DEFAULT_MODE = TraceMode.SYNC

    REGMAPS = [ASCRegs, None]
    NAMES = ["asc", None]

    def w_OUTBOX_CTRL(self, val):
        self.log(f"OUTBOX_CTRL = {val!s}")

    def w_INBOX1(self, val):
        inbox0 = self.asc.cached.INBOX0.val
        self.log(f"SEND: {inbox0:016x}:{val.value:016x}")

    def r_OUTBOX1(self, val):
        outbox0 = self.asc.cached.OUTBOX0.val
        self.log(f"RECV: {outbox0:016x}:{val.value:016x}")

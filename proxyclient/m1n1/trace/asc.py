# SPDX-License-Identifier: MIT

from enum import Enum
from ..hv import TraceMode
from ..utils import *
from . import ADTDevTracer

class DIR(Enum):
    RX = 0
    TX = 1

class R_OUTBOX_CTRL(Register32):
    EMPTY = 17

class R_INBOX_CTRL(Register32):
    ENABLE = 1

class R_MESSAGE(Register64):
    TYPE    = 59, 52

class R_INBOX1(Register64):
    EP      = 7, 0

class R_OUTBOX1(Register64):
    OUTCNT  = 56, 52
    INCNT   = 51, 48
    OUTPTR  = 47, 44
    INPTR   = 43, 40
    EP      = 7, 0

class ASCRegs(RegMap):
    INBOX_CTRL  = 0x8110, R_INBOX_CTRL
    OUTBOX_CTRL = 0x8114, R_OUTBOX_CTRL
    INBOX0      = 0x8800, R_MESSAGE
    INBOX1      = 0x8808, R_INBOX1
    OUTBOX0     = 0x8830, R_MESSAGE
    OUTBOX1     = 0x8838, R_OUTBOX1

class MSG_EP_MAP(R_MESSAGE):
    LAST    = 51
    BASE    = 34, 32
    BITMAP  = 31, 0

class MSG_EP_ACK(R_MESSAGE):
    LAST    = 51
    EP      = 34, 32
    FLAG    = 0

class MSG_EP_START(R_MESSAGE):
    EP      = 39, 32

def msg(channel, message, direction=None, regtype=None, name=None):
    def f(x):
        x.is_message = True
        x.direction = direction
        x.channel = channel
        x.message = message
        x.regtype = regtype
        x.name = name
        return x
    return f

def msg_log(*args, **kwargs):
    def x(self, r0, r1):
        return False
    return msg(*args, **kwargs)(x)

class ASCTracer(ADTDevTracer):
    DEFAULT_MODE = TraceMode.SYNC

    REGMAPS = [ASCRegs, None]
    NAMES = ["asc", None]

    EP_MGMT = 0
    EP_CRASHLOG = 1
    EP_SYSLOG = 2
    EP_KDEBUG = 3
    EP_IOREPORTING = 4

    def w_OUTBOX_CTRL(self, val):
        self.log(f"OUTBOX_CTRL = {val!s}")

    def w_INBOX1(self, inbox1):
        inbox0 = self.asc.cached.INBOX0.reg
        if self.verbose >= 2:
            self.log(f"SEND: {inbox0.value:016x}:{inbox1.value:016x} " +
                    f"{inbox0.str_fields()} | {inbox1.str_fields()}")
        self.handle_msg(DIR.TX, inbox0, inbox1)

    def r_OUTBOX1(self, outbox1):
        outbox0 = self.asc.cached.OUTBOX0.reg
        if self.verbose >= 2:
            self.log(f"RECV: {outbox0.value:016x}:{outbox1.value:016x} " +
                    f"{outbox0.str_fields()} | {outbox1.str_fields()}")
        self.handle_msg(DIR.RX, outbox0, outbox1)

    def init_state(self):
        self.state.endpoints = set()
        self.state.mbox = {}

    def handle_msg(self, direction, r0, r1):
        msgids = [
            (direction, r1.EP, r0.TYPE),
            (None, r1.EP, r0.TYPE),
            (direction, r1.EP, None),
            (None, r1.EP, None),
            (direction, None, r0.TYPE),
            (None, None, r0.TYPE),
            (None, None, None),
        ]
        handler = None

        for msgid in msgids:
            handler, name, regtype = self.msgmap.get(msgid, (None, None, None))
            if handler:
                break
        assert handler

        if regtype is not None:
            r0 = regtype(r0.value)

        if handler.name is not None:
            name = handler.name

        d = ">" if direction == DIR.TX else "<"
        if not handler(r0, r1):
            self.log(f" {d}{r1.EP:02x}:{r0.TYPE:02x} {name} {r0.value:016x} ({r0.str_fields()})")

    def start(self):
        super().start()
        self.msgmap = {}
        for name in dir(self):
            i = getattr(self, name)
            if not callable(i) or not getattr(i, "is_message", False):
                continue
            self.msgmap[i.direction, i.channel, i.message] = getattr(self, name), name, i.regtype

    unknown =   msg_log(None, None, None, name="<unknown>")

    INIT =      msg_log(EP_MGMT, 6, DIR.TX)
    HELLO =     msg_log(EP_MGMT, 1, DIR.RX)
    HELLO_ACK = msg_log(EP_MGMT, 2, DIR.TX)

    @msg(EP_MGMT, 8, DIR.RX, MSG_EP_MAP)
    def EP_MAP(self, r0, r1):
        for i in range(32):
            if r0.BITMAP & (1 << i):
                ep = 32 * r0.BASE + i
                self.log(f"  Registering endpoint #{ep:#02x}")
                self.state.endpoints.add(ep)

    EP_ACK =    msg_log(EP_MGMT, 8, DIR.TX, MSG_EP_ACK)
    EP_START =  msg_log(EP_MGMT, 5, DIR.TX, MSG_EP_START)

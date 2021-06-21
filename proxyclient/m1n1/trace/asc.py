# SPDX-License-Identifier: MIT

import struct
from enum import IntEnum
from ..hv import TraceMode
from ..utils import *
from . import ADTDevTracer

class DIR(IntEnum):
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

# Management messages

class MSG_EP_MAP(R_MESSAGE):
    LAST    = 51
    BASE    = 34, 32
    BITMAP  = 31, 0

class MSG_EP_MAP_ACK(R_MESSAGE):
    LAST    = 51
    BASE    = 34, 32
    MORE    = 0

class MSG_START_EP(R_MESSAGE):
    EP      = 39, 32

class MSG_START_SYSLOG(R_MESSAGE):
    UNK1 = 15, 0

# Syslog messages

class MSG_SYSLOG_INIT(R_MESSAGE):
    BUFSIZE = 7, 0

class MSG_SYSLOG_GET_BUF(R_MESSAGE):
    UNK1 = 51, 44
    UNK2 = 39, 32
    IOVA = 31, 0

class MSG_SYSLOG_LOG(R_MESSAGE):
    INDEX = 7, 0

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

def msg_ign(*args, **kwargs):
    def x(self, r0, r1):
        return True
    return msg(*args, **kwargs)(x)

class EP(object):
    def __init__(self, tracer, epid):
        self.tracer = tracer
        self.epid = epid
        self.started = False

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
        self.state.ep = {}

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

    def start(self, dart=None):
        super().start()
        self.dart = dart
        self.msgmap = {}
        for name in dir(self):
            i = getattr(self, name)
            if not callable(i) or not getattr(i, "is_message", False):
                continue
            self.msgmap[i.direction, i.channel, i.message] = getattr(self, name), name, i.regtype

    unknown = msg_log(None, None, None, name="<unknown>")

    # Management operations

    HELLO =     msg_log(EP_MGMT, 1, DIR.RX)
    HELLO_ACK = msg_log(EP_MGMT, 2, DIR.TX)

    @msg(EP_MGMT, 5, DIR.TX, MSG_START_EP)
    def START_EP(self, r0, r1):
        self.state.ep[r0.EP].started = True

    INIT = msg_log(EP_MGMT, 6, DIR.TX)

    @msg(EP_MGMT, 8, DIR.RX, MSG_EP_MAP)
    def EP_MAP(self, r0, r1):
        for i in range(32):
            if r0.BITMAP & (1 << i):
                ep = 32 * r0.BASE + i
                self.log(f"  Registering endpoint #{ep:#02x}")
                if ep not in self.state.ep:
                    self.state.ep[ep] = EP(self, ep)

    EP_MAP_ACK = msg_log(EP_MGMT, 8, DIR.TX, MSG_EP_MAP_ACK)

    START_SYSLOG = msg_log(EP_MGMT, 0x0b, DIR.TX, MSG_START_SYSLOG)
    START_SYSLOG_ACK = msg_log(EP_MGMT, 0x0b, DIR.RX, MSG_START_SYSLOG)

    SYSLOG_INIT = msg_log(EP_SYSLOG, 8, DIR.RX)
    SYSLOG_GET_BUF_REQ = msg_log(EP_SYSLOG, 1, DIR.RX, MSG_SYSLOG_GET_BUF)

    @msg(EP_SYSLOG, 1, DIR.TX, MSG_SYSLOG_GET_BUF)
    def SYSLOG_GET_BUF_ACK(self, r0, r1):
        self.state.ep[r1.EP].syslog_buf = r0.IOVA

    @msg(EP_SYSLOG, 5, DIR.RX, MSG_SYSLOG_LOG)
    def SYSLOG_LOG(self, r0, r1):
        if self.dart is None:
            return False
        buf = self.state.ep[r1.EP].syslog_buf
        log = self.dart.ioread(0, buf + r0.INDEX * 0xa0, 0xa0)
        hdr, unk, context, msg = struct.unpack("<II24s128s", log)
        context = context.rstrip(b"\x00").decode("ascii")
        msg = msg.rstrip(b"\x00").decode("ascii").rstrip("\n")
        self.log(f"syslog: [{context}]{msg}")
        return True

    SYSLOG_LOG_ACK = msg_ign(EP_SYSLOG, 5, DIR.TX, MSG_SYSLOG_LOG)

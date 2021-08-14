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
    INBOX0      = 0x8800, Register64
    INBOX1      = 0x8808, R_INBOX1
    OUTBOX0     = 0x8830, Register64
    OUTBOX1     = 0x8838, R_OUTBOX1

def msg(message, direction=None, regtype=None, name=None):
    def f(x):
        x.is_message = True
        x.direction = direction
        x.message = message
        x.regtype = regtype
        x.name = name
        return x
    return f

def msg_log(*args, **kwargs):
    def x(self, msg):
        return False
    return msg(*args, **kwargs)(x)

def msg_ign(*args, **kwargs):
    def x(self, msg):
        return True
    return msg(*args, **kwargs)(x)

class EPState(object):
    pass

class EP(object):
    NAME = None
    BASE_MESSAGE = None

    def __init__(self, tracer, epid):
        self.tracer = tracer
        self.epid = epid
        self.present = False
        self.started = False
        self.name = self.NAME or type(self).__name__.lower()
        self.state = EPState()
        self.hv = self.tracer.hv
        self.msgmap = {}
        for name in dir(self):
            i = getattr(self, name)
            if not callable(i) or not getattr(i, "is_message", False):
                continue
            self.msgmap[i.direction, i.message] = getattr(self, name), name, i.regtype

    def log(self, msg):
        self.tracer.log(f"[{self.name}] {msg}")

    def start(self):
        pass

    def handle_msg(self, direction, r0, r1):
        msgtype = None
        if self.BASE_MESSAGE:
            r0 = self.BASE_MESSAGE(r0.value)
            msgtype = r0.TYPE

        handler = None
        name = "<unknown>"
        regtype = None

        msgids = [
            (direction, msgtype),
            (None, msgtype),
            (direction, None),
            (None, None),
        ]

        for msgid in msgids:
            handler, name, regtype = self.msgmap.get(msgid, (None, None, None))
            if handler:
                break

        if regtype is not None:
            r0 = regtype(r0.value)

        if handler:
            if handler.name is not None:
                name = handler.name
            if handler(r0):
                return True

        d = ">" if direction == DIR.TX else "<"
        self.log(f"{d}{msgtype:#x}({name}) {r0.value:016x} ({r0.str_fields()})")
        return True

class EPContainer(object):
    pass

class BaseASCTracer(ADTDevTracer):
    DEFAULT_MODE = TraceMode.SYNC

    REGMAPS = [ASCRegs, None]
    NAMES = ["asc", None]

    ENDPOINTS = {}

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
        if r1.EP in self.epmap:
            if self.epmap[r1.EP].handle_msg(direction, r0, r1):
                return

        d = ">" if direction == DIR.TX else "<"
        self.log(f"{d}ep:{r1.EP:02x} {r0.value:016x} ({r0.str_fields()})")

    def start(self, dart=None):
        super().start()
        self.dart = dart
        self.msgmap = {}
        for name in dir(self):
            i = getattr(self, name)
            if not callable(i) or not getattr(i, "is_message", False):
                continue
            self.msgmap[i.direction, i.endpoint, i.message] = getattr(self, name), name, i.regtype

        self.epmap = {}
        self.ep = EPContainer()
        for cls in type(self).mro():
            eps = getattr(cls, "ENDPOINTS", None)
            if eps is None:
                break
            for k, v in eps.items():
                if k in self.epmap:
                    continue
                ep = v(self, k)
                ep.dart = dart
                self.epmap[k] = ep
                if k in self.state.ep:
                    ep.state.__dict__.update(self.state.ep[k])
                self.state.ep[k] = ep.state.__dict__
                if getattr(self.ep, ep.name, None):
                    ep.name = f"{ep.name}{k:02x}"
                setattr(self.ep, ep.name, ep)
                ep.start()

# System endpoints

class SystemMessage(Register64):
    TYPE    = 59, 52

## Management endpoint

class Mgmt_EPMap(SystemMessage):
    LAST    = 51
    BASE    = 34, 32
    BITMAP  = 31, 0

class Mgmt_EPMap_Ack(SystemMessage):
    LAST    = 51
    BASE    = 34, 32
    MORE    = 0

class Mgmt_StartEP(SystemMessage):
    EP      = 39, 32

class Mgmt_StartSyslog(SystemMessage):
    UNK1 = 15, 0

class Management(EP):
    BASE_MESSAGE = SystemMessage

    HELLO =     msg_log(1, DIR.RX)
    HELLO_ACK = msg_log(2, DIR.TX)

    @msg(5, DIR.TX, Mgmt_StartEP)
    def StartEP(self, msg):
        ep = self.tracer.epmap.get(msg.EP, None)
        if ep:
            ep.started = True
            self.log(f"  Starting endpoint #{msg.EP:#02x} ({ep.name})")
        else:
            self.log(f"  Starting endpoint #{msg.EP:#02x}")
        return True

    Init = msg_log(6, DIR.TX)

    @msg(8, DIR.RX, Mgmt_EPMap)
    def EPMap(self, msg):
        for i in range(32):
            if msg.BITMAP & (1 << i):
                epno = 32 * msg.BASE + i
                ep = self.tracer.epmap.get(epno, None)
                if ep:
                    ep.present = True
                    self.log(f"  Adding endpoint #{epno:#02x} ({ep.name})")
                else:
                    self.log(f"  Adding endpoint #{epno:#02x}")

    EPMap_Ack = msg_log(8, DIR.TX, Mgmt_EPMap_Ack)

    StartSyslog = msg_log(0x0b, DIR.TX, Mgmt_StartSyslog)
    StartSyslog_Ack = msg_log(0x0b, DIR.RX, Mgmt_StartSyslog)

## Syslog endpoint

class Syslog_Init(SystemMessage):
    BUFSIZE = 7, 0

class Syslog_GetBuf(SystemMessage):
    UNK1 = 51, 44
    UNK2 = 39, 32
    IOVA = 31, 0

class Syslog_Log(SystemMessage):
    INDEX = 7, 0

class Syslog(EP):
    BASE_MESSAGE = SystemMessage

    Init = msg_log(8, DIR.RX, Syslog_Init)
    GetBuf = msg_log(1, DIR.RX, Syslog_GetBuf)

    @msg(1, DIR.TX, Syslog_GetBuf)
    def GetBuf_Ack(self, msg):
        self.state.syslog_buf = msg.IOVA

    @msg(5, DIR.RX, Syslog_Log)
    def Log(self, msg):
        if self.tracer.dart is None:
            return False
        buf = self.state.syslog_buf
        log = self.tracer.dart.ioread(0, buf + msg.INDEX * 0xa0, 0xa0)
        hdr, unk, context, logmsg = struct.unpack("<II24s128s", log)
        context = context.split(b"\x00")[0].decode("ascii")
        logmsg = logmsg.split(b"\x00")[0].decode("ascii").rstrip("\n")
        self.log(f"* [{context}]{logmsg}")
        return True

    Log_Ack = msg_ign(5, DIR.TX, Syslog_Log)

class ASCTracer(BaseASCTracer):
    ENDPOINTS = {
        0: Management,
        #1: CrashLog,
        2: Syslog,
        #3: KDebug,
        #4: IOReporting,
    }

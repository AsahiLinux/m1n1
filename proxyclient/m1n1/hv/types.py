# SPDX-License-Identifier: MIT
from construct import *
from enum import IntEnum

from ..utils import *

__all__ = [
    "MMIOTraceFlags", "EvtMMIOTrace", "EvtIRQTrace", "HV_EVENT",
    "VMProxyHookData", "TraceMode",
]

class MMIOTraceFlags(Register32):
    ATTR = 31, 24
    CPU = 23, 16
    SH = 15, 14
    WIDTH = 4, 0
    WRITE = 5
    MULTI = 6

EvtMMIOTrace = Struct(
    "flags" / RegAdapter(MMIOTraceFlags),
    "reserved" / Int32ul,
    "pc" / Hex(Int64ul),
    "addr" / Hex(Int64ul),
    "data" / Hex(Int64ul),
)

EvtIRQTrace = Struct(
    "flags" / Int32ul,
    "type" / Hex(Int16ul),
    "num" / Int16ul,
)

class HV_EVENT(IntEnum):
    HOOK_VM = 1
    VTIMER = 2
    USER_INTERRUPT = 3
    WDT_BARK = 4
    CPU_SWITCH = 5

VMProxyHookData = Struct(
    "flags" / RegAdapter(MMIOTraceFlags),
    "id" / Int32ul,
    "addr" / Hex(Int64ul),
    "data" / Array(8, Hex(Int64ul)),
)

class TraceMode(IntEnum):
    '''
Different types of Tracing '''

    OFF = 0
    BYPASS = 1
    ASYNC = 2
    UNBUF = 3
    WSYNC = 4
    SYNC = 5
    HOOK = 6
    RESERVED = 7

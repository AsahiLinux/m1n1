# SPDX-License-Identifier: MIT
import struct

from ..utils import *

from .asc import StandardASC
from .asc.base import *

SMC_READ_KEY           = 0x10
SMC_WRITE_KEY          = 0x11
SMC_GET_KEY_BY_INDEX   = 0x12
SMC_GET_KEY_INFO       = 0x13
SMC_GET_SRAM_ADDR      = 0x17
SMC_NOTIFICATION       = 0x18
SMC_READ_KEY_PAYLOAD   = 0x20

class SMCGetSRAMAddr(Register64):
    TYPE = 8, 0, Constant(0x17)
    ID = 16, 12

class SMCWriteKey(Register64):
    TYPE = 8, 0, Constant(0x11)
    ID = 16, 12
    SIZE = 32, 16
    KEY = 64, 32

class SMCMessage(Register64):
    TYPE = 0, 0
    VALUE = 64, 0

class SMCMessage(Register64):
    TYPE = 8, 0
    ID = 16, 12
    HPARAM = 32, 16
    WPARAM = 64, 32

class SMCEndpoint(ASCBaseEndpoint):
    BASE_MESSAGE = SMCMessage
    SHORT = "smcep"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shmem = None
        self.msgid = 0
        self.outstanding = set()

    def start(self):
        self.send(SMCGetSRAMAddr(ID = self.new_msgid()))
        while self.shmem is None:
            self.asc.work()

    def new_msgid(self):
        mid = (self.msgid & 0xF)
        self.msgid += 1
        assert(mid not in self.outstanding)
        self.outstanding.add(mid)
        return mid


    def write_key(self, key, data):
        print(self.shmem, key, data, len(data))
        self.asc.iface.writemem(self.shmem, data)
        ID = self.new_msgid()
        self.send(SMCWriteKey(ID = ID, KEY = key, SIZE = len(data)))
        while ID in self.outstanding:
            self.asc.work()
        return True

    @msg_handler(0x00, SMCMessage)
    def Startup(self, msg):
        self.log(hex(msg.value))

        if self.shmem is None:
            self.log("Starting up")
            self.shmem = msg.value
        else:
            ret = msg.value & 0xFF
            mid = (msg.value >> 12) & 0xF
            print(f"msg {mid} return value {ret}")
            self.outstanding.discard(mid)

        return True

class SMCClient(StandardASC):
    pass

    ENDPOINTS = {
        0x20: SMCEndpoint,
    }

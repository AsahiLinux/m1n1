# SPDX-License-Identifier: MIT
import struct

from ..utils import *

from .asc import StandardASC
from .asc.base import *

SMC_READ_KEY           = 0x10
SMC_WRITE_KEY          = 0x11
SMC_GET_KEY_BY_INDEX   = 0x12
SMC_GET_KEY_INFO       = 0x13
SMC_INITIALIZE         = 0x17
SMC_NOTIFICATION       = 0x18
SMC_READ_KEY_PAYLOAD   = 0x20

class SMCMessage(Register64):
    TYPE = 7, 0
    UNK = 11, 8, Constant(0)
    ID = 15, 12

class SMCInitialize(SMCMessage):
    TYPE = 7, 0, Constant(SMC_INITIALIZE)

class SMCGetKeyInfo(SMCMessage):
    TYPE = 7, 0, Constant(SMC_GET_KEY_INFO)
    KEY = 63, 32

class SMCWriteKey(SMCMessage):
    TYPE = 7, 0, Constant(SMC_WRITE_KEY)
    SIZE = 31, 16
    KEY = 63, 32

class SMCReadKey(SMCMessage):
    TYPE = 7, 0, Constant(SMC_READ_KEY)
    SIZE = 31, 16
    KEY = 63, 32

class SMCResult(Register64):
    RESULT = 7, 0
    ID = 15, 12
    SIZE = 31, 16
    VALUE = 63, 32

class SMCError(Exception):
    pass

class SMCEndpoint(ASCBaseEndpoint):
    BASE_MESSAGE = SMCMessage
    SHORT = "smcep"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shmem = None
        self.msgid = 0
        self.outstanding = set()
        self.ret = {}

    def start(self):
        self.send(SMCInitialize(ID = 0))
        self.msgid += 1 # important!
        while self.shmem is None:
            self.asc.work()

    def new_msgid(self):
        mid = (self.msgid & 0xF)
        self.msgid += 1
        assert(mid not in self.outstanding)
        self.outstanding.add(mid)
        return mid

    def write(self, key, data):
        key = int.from_bytes(key.encode("ascii"), byteorder="big")
        self.asc.iface.writemem(self.shmem, data)
        ID = self.new_msgid()
        self.send(SMCWriteKey(ID = ID, KEY = key, SIZE = len(data)))
        while ID in self.outstanding:
            self.asc.work()
        ret = self.ret[ID]
        if ret.RESULT != 0:
            raise SMCError(f"SMC error {ret}", ret)

    def write32(self, key, data):
        self.write(key, struct.pack("<I", data))

    def write16(self, key, data):
        self.write(key, struct.pack("<H", data))

    def write8(self, key, data):
        self.write(key, struct.pack("<B", data))

    def read(self, key, size):
        key = int.from_bytes(key.encode("ascii"), byteorder="big")
        ID = self.new_msgid()
        self.send(SMCReadKey(ID = ID, KEY = key, SIZE = size))
        while ID in self.outstanding:
            self.asc.work()
        ret = self.ret[ID]
        if ret.RESULT != 0:
            raise SMCError(f"SMC error {ret.RESULT}", ret.RESULT)
        if size <= 4:
            return ret.VALUE
        else:
            return self.asc.iface.readmem(self.shmem, ret.SIZE)

    def read32(self, key):
        return self.read(key, 4)

    def read16(self, key):
        return self.read(key, 2)

    def read8(self, key):
        return self.read(key, 1)

    def handle_msg(self, msg0, msg1):
        if self.shmem is None:
            self.log("Starting up")
            self.shmem = msg0
        else:
            msg = SMCResult(msg0)
            ret = msg.RESULT
            mid = msg.ID
            print(f"msg {mid} return value {ret}")
            self.outstanding.discard(mid)
            self.ret[mid] = msg

        return True

class SMCClient(StandardASC):
    ENDPOINTS = {
        0x20: SMCEndpoint,
    }

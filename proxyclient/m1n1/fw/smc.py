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
SMC_RW_KEY             = 0x20

class SMCMessage(Register64):
    TYPE = 7, 0
    UNK = 11, 8, Constant(0)
    ID = 15, 12

class SMCInitialize(SMCMessage):
    TYPE = 7, 0, Constant(SMC_INITIALIZE)

class SMCGetKeyInfo(SMCMessage):
    TYPE = 7, 0, Constant(SMC_GET_KEY_INFO)
    KEY = 63, 32

class SMCGetKeyByIndex(SMCMessage):
    TYPE = 7, 0, Constant(SMC_GET_KEY_BY_INDEX)
    INDEX = 63, 32

class SMCWriteKey(SMCMessage):
    TYPE = 7, 0, Constant(SMC_WRITE_KEY)
    SIZE = 23, 16
    KEY = 63, 32

class SMCReadKey(SMCMessage):
    TYPE = 7, 0, Constant(SMC_READ_KEY)
    SIZE = 23, 16
    KEY = 63, 32

class SMCReadWriteKey(SMCMessage):
    TYPE = 7, 0, Constant(SMC_RW_KEY)
    RSIZE = 23, 16
    WSIZE = 31, 24
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
    TYPE_MAP = {
        "ui64": ("<Q", None),
        "ui32": ("<I", None),
        "ui16": ("<H", None),
        "ui8 ": ("<B", None),
        "si64": ("<q", None),
        "si32": ("<i", None),
        "si16": ("<h", None),
        "si8 ": ("<b", None),
        "flag": ("<B", None),
        "flt ": ("<f", None),
        "hex_": (None, hexdump),
        "ch8*": (None, lambda c: c.split(b"\x00")[0]),
        "ioft": ("<Q", None),
    }

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

    def cmd(self, cmd):
        cmd.ID = self.new_msgid()
        self.send(cmd)
        while cmd.ID in self.outstanding:
            self.asc.work()
        ret = self.ret[cmd.ID]
        if ret.RESULT != 0:
            raise SMCError(f"SMC error {ret}", ret)
        return ret

    def write(self, key, data):
        key = int.from_bytes(key.encode("ascii"), byteorder="big")
        self.asc.iface.writemem(self.shmem, data)
        self.cmd(SMCWriteKey(KEY = key, SIZE = len(data)))

    def read(self, key, size):
        key = int.from_bytes(key.encode("ascii"), byteorder="big")
        ret = self.cmd(SMCReadKey(KEY = key, SIZE = size))
        if size <= 4:
            return struct.pack("<I", ret.VALUE)[:size]
        else:
            return self.asc.iface.readmem(self.shmem, ret.SIZE)

    def rw(self, key, data, outsize):
        key = int.from_bytes(key.encode("ascii"), byteorder="big")
        self.asc.iface.writemem(self.shmem, data)
        ret = self.cmd(SMCReadWriteKey(KEY=key, RSIZE=outsize, WSIZE=len(data)))
        if outsize <= 4:
            return struct.pack("<I", ret.VALUE)[:outsize]
        else:
            return self.asc.iface.readmem(self.shmem, ret.SIZE)

    def get_key_by_index(self, index):
        ret = self.cmd(SMCGetKeyByIndex(INDEX = index))
        key = ret.VALUE.to_bytes(4, byteorder="little").decode("ascii")
        return key

    def get_key_info(self, key):
        key = int.from_bytes(key.encode("ascii"), byteorder="big")
        ret = self.cmd(SMCGetKeyInfo(KEY = key))
        info = self.asc.iface.readmem(self.shmem, 6)
        length, type, flags = struct.unpack("B4sB", info)
        return length, type.decode("ascii"), flags

    def read64(self, key):
        return struct.unpack("<Q", self.read(key, 8))[0]

    def read32(self, key):
        return struct.unpack("<I", self.read(key, 4))[0]

    def read16(self, key):
        return struct.unpack("<H", self.read(key, 2))[0]

    def read8(self, key):
        return struct.unpack("<B", self.read(key, 1))[0]

    def read32b(self, key):
        return struct.unpack(">I", self.read(key, 4))[0]

    def write64(self, key, data):
        self.write(key, struct.pack("<Q", data))

    def write32(self, key, data):
        self.write(key, struct.pack("<I", data))

    def write16(self, key, data):
        self.write(key, struct.pack("<H", data))

    def write8(self, key, data):
        self.write(key, struct.pack("<B", data))

    def rw32(self, key, data):
        return struct.unpack("<I", self.rw(key, struct.pack("<I", data), 4))[0]

    def read_type(self, key, size, typecode):
        fmt, func = self.TYPE_MAP.get(typecode, (None, None))

        val = self.read(key, size)

        if fmt:
            val = struct.unpack(fmt, val)[0]
        if func:
            val = func(val)
        return val

    def handle_msg(self, msg0, msg1):
        if self.shmem is None:
            self.log("Starting up")
            self.shmem = msg0
        else:
            msg = SMCResult(msg0)
            ret = msg.RESULT
            mid = msg.ID
            if ret == SMC_NOTIFICATION:
                self.log(f"Notification: {msg.VALUE:#x}")
                return True
            #print(f"msg {mid} return value {ret}")
            self.outstanding.discard(mid)
            self.ret[mid] = msg

        return True

class SMCClient(StandardASC):
    ENDPOINTS = {
        0x20: SMCEndpoint,
    }

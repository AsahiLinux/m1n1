# SPDX-License-Identifier: MIT
from .base import *
from ...utils import *
from construct import *

class CrashLogMessage(Register64):
    TYPE = 63, 52
    SIZE = 51, 44
    DVA = 43, 0

CrashHeader = Struct(
    "type" / Const("CLHE", FourCC),
    "ver" / Int32ul,
    "total_size" / Int32ul,
    "flags" / Int32ul,
    Padding(16)
)

CrashCver = Struct(
    "uuid" / Bytes(16),
    "version" / CString("utf8"),
)

CrashCstr = Struct(
    "id" / Int32ul,
    "string" / CString("utf8"),
)

CrashCtim = Struct(
    "time" / Int64ul,
)

CrashCmbx = Struct(
    "hdr" / Array(4, Hex(Int32ul)),
    "type" / Int32ul,
    "unk" / Int32ul,
    "index" / Int32ul,
    "messages" / GreedyRange(Struct(
        "endpoint" / Hex(Int64ul),
        "message" / Hex(Int64ul),
        "timestamp" / Hex(Int32ul),
        Padding(4),
    )),
)

CrashEntry = Struct(
    "type" / FourCC,
    Padding(4),
    "flags" / Hex(Int32ul),
    "len" / Int32ul,
    "payload" / FixedSized(lambda ctx: ctx.len - 16 if ctx.type != "CLHE" else 16,
                           Switch(this.type, {
        "Cver": CrashCver,
        "Ctim": CrashCtim,
        "Cmbx": CrashCmbx,
        "Cstr": CrashCstr,
    }, default=GreedyBytes)),
)

CrashLog = Struct(
    "header" / CrashHeader,
    "entries" / RepeatUntil(this.type == "CLHE", CrashEntry),
)

class CrashLogParser:
    def __init__(self, data=None):
        if data is not None:
            self.parse(data)

    def parse(self, data):
        self.data = CrashLog.parse(data)
        pass

    def default(self, entry):
        print(f"# {entry.type} flags={entry.flags:#x}")
        chexdump(entry.payload)
        print()

    def Cver(self, entry):
        print(f"RTKit Version: {entry.payload.version}")
        print()

    def Cstr(self, entry):
        print(f"Message {entry.payload.id}: {entry.payload.string}")
        print()

    def Ctim(self, entry):
        print(f"Crash time: {entry.payload.time:#x}")
        print()

    def Cmbx(self, entry):
        print(f"Mailbox log (type {entry.payload.type}, index {entry.payload.index}):")
        for i, msg in enumerate(entry.payload.messages):
            print(f" #{i:3d} @{msg.timestamp:#10x} ep={msg.endpoint:#4x} {msg.message:#18x}")
        print()

    def CLHE(self, entry):
        pass

    def dump(self):
        print("### Crash dump:")
        print()
        for entry in self.data.entries:
            getattr(self, entry.type, self.default)(entry)

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
        size = align(0x1000 * msg.SIZE, 0x4000)

        if msg.DVA:
            self.iobuffer_dva = msg.DVA
            self.log(f"buf prealloc at dva {self.iobuffer_dva:#x}")
            self.send(CrashLogMessage(TYPE=1, SIZE=msg.SIZE))
        else:
            self.iobuffer, self.iobuffer_dva = self.asc.ioalloc(size)
            self.log(f"buf {self.iobuffer:#x} / {self.iobuffer_dva:#x}")
            self.send(CrashLogMessage(TYPE=1, SIZE=size // 0x1000, DVA=self.iobuffer_dva))

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
        open("crash.bin", "wb").write(crashdata)
        clog = CrashLogParser(crashdata)
        clog.dump()
        raise Exception("ASC crashed!")

        return True

if __name__ == "__main__":
    import sys
    crashdata = open(sys.argv[1], "rb").read()
    clog = CrashLogParser(crashdata)
    clog.dump()

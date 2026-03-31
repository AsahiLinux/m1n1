# SPDX-License-Identifier: MIT
from .base import *
from ...utils import *
from construct import *
from ...sysreg import *

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

CrashCcst = Struct(
    "task" / Int32ul,
    "unk" / Int32ul,
    "stack" / GreedyRange(Int64ul)
)

CrashCasC = Struct(
    "l2c_err_sts" / Hex(Int64ul),
    "l2c_err_adr" / Hex(Int64ul),
    "l2c_err_inf" / Hex(Int64ul),
    "lsu_err_sts" / Hex(Int64ul),
    "fed_err_sts" / Hex(Int64ul),
    "mmu_err_sts" / Hex(Int64ul)
)

CrashCrg8 = Struct(
    "unk_0" / Int32ul,
    "unk_4" / Int32ul,
    "regs" / Array(31, Hex(Int64ul)),
    "sp" / Int64ul,
    "pc" / Int64ul,
    "psr" / Int64ul,
    "cpacr" / Int64ul,
    "fpsr" / Int64ul,
    "fpcr" / Int64ul,
    "unk" / Array(64, Hex(Int64ul)),
    "far" / Int64ul,
    "unk_X" / Int64ul,
    "esr" / Int64ul,
    "unk_Z" / Int64ul,
)

CrtkEntry = Struct(
    "id" / Int16ul,
    "flags" / Int16ul,
    "unk_4" / Int32ul,
    "unk_8" / Int32ul,
    "unk_c" / Int32ul,
    "ptr" / Int64ul,
    "unk_14" / Int32ul,
    "unk_18" / Int32ul,
    "unk_1c" / Int32ul,
    "unk_20" / Int32ul,
    "ptr_count" / Int32ul,
    "name" / Bytes(0x1c),
    "ptrs" / Array(this.ptr_count, Int64ul)
)

CrashCrtk = Struct(
    "tasks" / GreedyRange(CrtkEntry),
    "leftovers" / GreedyBytes,
)

CcdpEntry = Struct(
    "va" / Int64ul,
    "pa" / Int64ul,
    "unk_10" / Int32ul,
)

CrashCcdp = Struct(
    "entries" / GreedyRange(CcdpEntry),
    "leftovers" / GreedyBytes,
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
        "Crg8": CrashCrg8,
        "Ccst": CrashCcst,
        "CasC": CrashCasC,
        "Crtk": CrashCrtk,
        "Ccdp": CrashCcdp,
    }, default=GreedyBytes)),
)

CrashLog = Struct(
    "header" / CrashHeader,
    "entries" / RepeatUntil(this.type == "CLHE", CrashEntry),
)

class CrashLogParser:
    def __init__(self, data=None, asc=None):
        self.asc = asc
        self.task_id = None
        if data is not None:
            self.parse(data)

    def parse(self, data):
        self.data = CrashLog.parse(data)
        pass

    def default(self, entry):
        print(f"# {entry.type} flags={entry.flags:#x}")
        chexdump(entry.payload)
        print()

    def Ccst(self, entry):
        self.task_id = entry.payload.task
        print(f"Call stack (task {entry.payload.task}):")
        for i in entry.payload.stack:
            if not i:
                break
            print(f"  - {i:#x}")
        print()

    def CasC(self, entry):
        print(f"Async error info:")
        print(entry.payload)
        print()

    def Cver(self, entry):
        print(f"RTKit Version: {entry.payload.version}")
        print()

    def Crg8(self, entry):
        print(f"Exception info:")

        ctx = entry.payload

        addr = self.asc.addr

        spsr = SPSR(ctx.psr)
        esr = ESR(ctx.esr)
        elr = ctx.pc
        far_phys = self.asc.iotranslate(ctx.far, 1)[0][0]
        elr_phys = self.asc.iotranslate(ctx.pc, 1)[0][0]
        sp_phys = self.asc.iotranslate(ctx.sp, 1)[0][0]

        print(f"  == Exception taken from {spsr.M.name} ==")
        el = spsr.M >> 2
        print(f"  SPSR   = {spsr}")
        print(f"  ELR    = {addr(elr)}" + (f" (0x{elr_phys:x})" if elr_phys else ""))
        print(f"  ESR    = {esr}")
        print(f"  FAR    = {addr(ctx.far)}" + (f" (0x{far_phys:x})" if far_phys else ""))
        print(f"  SP     = {ctx.sp:#x}" + (f" (0x{sp_phys:x})" if sp_phys else ""))

        for i in range(0, 31, 4):
            j = min(30, i + 3)
            print(f"  {f'x{i}-x{j}':>7} = {' '.join(f'{r:016x}' for r in ctx.regs[i:j + 1])}")

        # print AGX objects where available
        for i in range(31):
            this_addr = addr(ctx.regs[i])
            if "@" in this_addr:
                print("  x%d: %s" % (i, this_addr))

        if elr_phys:
            v = self.asc.p.read32(elr_phys)

            print()
            if v == 0xabad1dea:
                print("  == Faulting code is not available ==")
            else:
                print("  == Faulting code ==")
                dist = 16
                self.asc.u.disassemble_at(elr_phys - dist * 4, (dist * 2 + 1) * 4, elr_phys)

        if sp_phys:
            for n in range(-4, 4):
                sp_ptr = sp_phys+8*n
                v = self.asc.p.read64(sp_ptr)
                print(f"  stack @ 0x{sp_ptr:016x}: {v:016x}")

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
        # terminator?
        pass

    def Crtk(self, entry):
        print("Tasks:")
        for task in entry.payload.tasks:
            name = task.name.rstrip(b'\x00').decode()
            if self.task_id == task.id:
                print(f"* {task.id}: {name} (flags 0x{task.flags:x})")
            else:
                print(f"  {task.id}: {name} @ {task.ptr:08x} (flags 0x{task.flags:x})")
                print(f"   Stack: ", end="")
                for p in task.ptrs:
                    print(f"0x{p:08x}", end=" ")
                print("")
            print(f"   Unknowns: {task.unk_4:08x} {task.unk_8:08x} {task.unk_c:08x} {task.unk_14:08x} {task.unk_18:08x} {task.unk_1c:08x} {task.unk_20:08x}")
        if len(entry.payload.leftovers):
            chexdump(entry.payload.leftovers)
        print()

    def Ccdp(self, entry):
        print("Ccdp:")
        for e in entry.payload.entries:
            real_pa = self.asc.iotranslate(e.va, 1)[0][0]
            name = self.asc.addr(e.va) if e.va else ""
            name = "("+name+")" if ('@' in name) else ""
            print(f" 0x{e.va:016x} -> 0x{e.pa:016x} {name} : {e.unk_10:08x}")
            if real_pa != e.pa:
                if real_pa != None:
                    print(f"  (wrong PA; should be 0x{real_pa:16x})")
                else:
                    print(f"  (wrong PA; not mapped)")
        print()

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

        if msg.DVA:
            size = 0x1000 * msg.SIZE
            self.iobuffer_dva = msg.DVA
            self.log(f"buf prealloc at dva {self.iobuffer_dva:#x}")
        else:
            size = align(0x1000 * msg.SIZE, 0x4000)
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
        self.log(f" DVA @ 0x{msg.DVA:x}")
        crashdata = self.asc.ioread(msg.DVA, size)
        open("crash.bin", "wb").write(crashdata)
        clog = CrashLogParser(crashdata, self.asc)
        clog.dump()
        raise Exception("ASC crashed!")

        return True

if __name__ == "__main__":
    import sys
    crashdata = open(sys.argv[1], "rb").read()
    clog = CrashLogParser(crashdata)
    clog.dump()

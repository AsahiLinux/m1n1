# SPDX-License-Identifier: MIT
from io import BytesIO, SEEK_END, SEEK_SET
import bisect
from construct import *
import subprocess

from .utils import *

__all__ = ["MachO"]

MachOLoadCmdType = "LoadCmdType" / Enum(Int32ul,
    SYMTAB = 0x02,
    UNIXTHREAD = 0x05,
    SEGMENT_64 = 0x19,
    UUID = 0x1b,
    BUILD_VERSION = 0x32,
    DYLD_CHAINED_FIXUPS = 0x80000034,
    FILESET_ENTRY = 0x80000035,
)

MachOArmThreadStateFlavor = "ThreadStateFlavor" / Enum(Int32ul,
    THREAD64 = 6,
)

MachOHeader = Struct(
    "magic" / Hex(Int32ul),
    "cputype" / Hex(Int32ul),
    "cpusubtype" / Hex(Int32ul),
    "filetype" / Hex(Int32ul),
    "ncmds" / Hex(Int32ul),
    "sizeofcmds" / Hex(Int32ul),
    "flags" / Hex(Int32ul),
    "reserved" / Hex(Int32ul),
)

MachOVmProt = FlagsEnum(Int32sl,
    PROT_READ = 0x01,
    PROT_WRITE = 0x02,
    PROT_EXECUTE = 0x04,
)

MachOCmdSymTab = Struct(
    "symoff" / Hex(Int32ul),
    "nsyms" / Int32ul,
    "stroff" / Hex(Int32ul),
    "strsize" / Hex(Int32ul),
)

MachOCmdUnixThread = GreedyRange(Struct(
    "flavor" / MachOArmThreadStateFlavor,
    "data" / Prefixed(ExprAdapter(Int32ul, obj_ * 4, obj_ / 4), Switch(this.flavor, {
        MachOArmThreadStateFlavor.THREAD64: Struct(
            "x" / Array(29, Hex(Int64ul)),
            "fp" / Hex(Int64ul),
            "lr" / Hex(Int64ul),
            "sp" / Hex(Int64ul),
            "pc" / Hex(Int64ul),
            "cpsr" / Hex(Int32ul),
            "flags" / Hex(Int32ul),
        )
    })),
))

NList = Struct(
    "n_strx" / Hex(Int32ul),
    "n_type" / Hex(Int8ul),
    "n_sect" / Hex(Int8ul),
    "n_desc" / Hex(Int16sl),
    "n_value" / Hex(Int64ul),
)

MachOCmdSegment64 = Struct(
    "segname" / PaddedString(16, "ascii"),
    "vmaddr" / Hex(Int64ul),
    "vmsize" / Hex(Int64ul),
    "fileoff" / Hex(Int64ul),
    "filesize" / Hex(Int64ul),
    "maxprot" / MachOVmProt,
    "initprot" / MachOVmProt,
    "nsects" / Int32ul,
    "flags" / Hex(Int32ul),
    "sections" / GreedyRange(Struct(
        "sectname" / PaddedString(16, "ascii"),
        "segname" / PaddedString(16, "ascii"),
        "addr" / Hex(Int64ul),
        "size" / Hex(Int64ul),
        "offset" / Hex(Int32ul),
        "align" / Hex(Int32ul),
        "reloff" / Hex(Int32ul),
        "nreloc" / Hex(Int32ul),
        "flags" / Hex(Int32ul),
        "reserved1" / Hex(Int32ul),
        "reserved2" / Hex(Int32ul),
        "reserved3" / Hex(Int32ul),
    )),
)

MachOFilesetEntry = Struct(
    "addr" / Hex(Int64ul),
    "offset" / Hex(Int64ul),
    "entryid" / Hex(Int32ul),
    "reserved" / Hex(Int32ul),
    "name" / CString("ascii"),
)

MachOCmd = Struct(
    "cmd" / Hex(MachOLoadCmdType),
    "args" / Prefixed(ExprAdapter(Int32ul, obj_ - 8, obj_ + 8), Switch(this.cmd, {
        MachOLoadCmdType.SYMTAB: MachOCmdSymTab,
        MachOLoadCmdType.UNIXTHREAD: MachOCmdUnixThread,
        MachOLoadCmdType.SEGMENT_64: MachOCmdSegment64,
        MachOLoadCmdType.UUID: Hex(Bytes(16)),
        MachOLoadCmdType.FILESET_ENTRY: MachOFilesetEntry,
    }, default=GreedyBytes)),
)

MachOFile = Struct(
    "header" / MachOHeader,
    "cmds" / Array(this.header.ncmds, MachOCmd),
)

class MachO:
    def __init__(self, data):
        if isinstance(data, bytes):
            self.io = BytesIO(data)
        else:
            self.io = data

        self.off = self.io.tell()
        self.io.seek(0, SEEK_END)
        self.end = self.io.tell()
        self.size = self.end - self.off
        self.io.seek(self.off, SEEK_SET)
        self.obj = MachOFile.parse_stream(self.io)
        self.symbols = {}
        self.load_info()
        self.load_fileset()

    def load_info(self):
        self.vmin, self.vmax = (1 << 64), 0
        self.entry = None
        for cmd in self.obj.cmds:
            if cmd.cmd == MachOLoadCmdType.SEGMENT_64:
                self.vmin = min(self.vmin, cmd.args.vmaddr)
                self.vmax = max(self.vmax, cmd.args.vmaddr + cmd.args.vmsize)
            elif cmd.cmd == MachOLoadCmdType.UNIXTHREAD:
                self.entry = cmd.args[0].data.pc

    def prepare_image(self, load_hook=None):
        memory_size = self.vmax - self.vmin

        image = bytearray(memory_size)

        for cmd in self.get_cmds(MachOLoadCmdType.SEGMENT_64):
            dest = cmd.args.vmaddr - self.vmin
            end = min(self.size, cmd.args.fileoff + cmd.args.filesize)
            size = end - cmd.args.fileoff
            print(f"LOAD: {cmd.args.segname} {size} bytes from {cmd.args.fileoff:x} to {dest:x}")
            self.io.seek(self.off + cmd.args.fileoff)
            data = self.io.read(size)
            if load_hook is not None:
                data = load_hook(data, cmd.args.segname, size, cmd.args.fileoff, dest)
            image[dest:dest + size] = data
            if cmd.args.vmsize > size:
                clearsize = cmd.args.vmsize - size
                if cmd.args.segname == "PYLD":
                    print("SKIP: %d bytes from 0x%x to 0x%x" % (clearsize, dest + size, dest + size + clearsize))
                    memory_size -= clearsize - 4 # leave a payload end marker
                    image = image[:memory_size]
                else:
                    print("ZERO: %d bytes from 0x%x to 0x%x" % (clearsize, dest + size, dest + size + clearsize))
                    image[dest + size:dest + cmd.args.vmsize] = bytes(clearsize)

        return image

    def get_cmds(self, cmdtype):
        for cmd in self.obj.cmds:
            if cmd.cmd == cmdtype:
                yield cmd

    def get_cmd(self, cmdtype):
        cmds = list(self.get_cmds(cmdtype))
        if len(cmds) == 0:
            raise Exception(f"No commands of type {cmdtype}")
        if len(cmds) > 1:
            raise Exception(f"More than one commands of type {cmdtype} (found {len(cmd)})")
        return cmds[0]

    def load_fileset(self):
        self.subfiles = {}

        for fe in self.get_cmds(MachOLoadCmdType.FILESET_ENTRY):
            self.io.seek(self.off + fe.args.offset)
            subfile = MachO(self.io)
            self.subfiles[fe.args.name] = subfile
            for seg in subfile.get_cmds(MachOLoadCmdType.SEGMENT_64):
                self.symbols[f"{fe.args.name}:{seg.args.segname}"] = seg.args.vmaddr

    def add_symbols(self, filename, syms, demangle=False):
        try:
            subfile = self.subfiles[filename]
        except KeyError:
            raise Exception(f"No fileset entry for {filename}")

        sym_segs = {}
        for sym_seg in syms.get_cmds(MachOLoadCmdType.SEGMENT_64):
            sym_segs[sym_seg.args.segname] = sym_seg

        syms.load_symbols(demangle=demangle)
        symtab = [(v, k) for (k, v) in syms.symbols.items()]
        symtab.sort()

        for seg in subfile.get_cmds(MachOLoadCmdType.SEGMENT_64):
            if seg.args.segname not in sym_segs:
                continue

            sym_seg = sym_segs[seg.args.segname]

            start = bisect.bisect_left(symtab, (sym_seg.args.vmaddr, ""))
            end = bisect.bisect_left(symtab, (sym_seg.args.vmaddr + sym_seg.args.vmsize, ""))

            for addr, sym in symtab[start:end]:
                sname = f"{filename}:{sym}"
                self.symbols[sname] = addr - sym_seg.args.vmaddr + seg.args.vmaddr

    def load_symbols(self, demangle=False):
        self.symbols = {}

        cmd = self.get_cmd(MachOLoadCmdType.SYMTAB)

        nsyms = cmd.args.nsyms
        length = NList.sizeof() * nsyms
        self.io.seek(self.off + cmd.args.symoff)
        symdata = self.io.read(length)

        symbols = Array(nsyms, NList).parse(symdata)

        symbols_dict = {}
        for i in symbols:
            off = cmd.args.stroff + i.n_strx
            self.io.seek(self.off + off)
            name = self.io.read(1024).split(b"\x00")[0].decode("ascii")
            symbols_dict[name] = i.n_value

        if demangle:
            names = list(symbols_dict.keys())
            argv = ["c++filt"]
            argv += names

            with subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as proc:
                demangled, _ = proc.communicate()

            demangled = demangled.decode("ascii").split("\n")[:-1]
            for name_mangled, name_demangled in zip(names, demangled):
                self.symbols[name_demangled] = symbols_dict[name_mangled]
        else:
            self.symbols = symbols_dict

if __name__ == "__main__":
    import sys
    macho = MachO(open(sys.argv[1], "rb").read())

    if len(sys.argv) > 2:
        syms = MachO(open(sys.argv[2], "rb").read())
        macho.add_symbols("com.apple.kernel", syms)

        symtab = [(v, k) for (k, v) in macho.symbols.items()]
        symtab.sort()
        for addr, name in symtab:
            print(f"0x{addr:x} {name}")

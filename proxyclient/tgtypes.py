# SPDX-License-Identifier: MIT
from construct import *

BootArgs = Struct(
    "revision"              / Hex(Int16ul),
    "version"               / Hex(Int16ul),
    Padding(4),
    "virt_base"             / Hex(Int64ul),
    "phys_base"             / Hex(Int64ul),
    "mem_size"              / Hex(Int64ul),
    "top_of_kernel_data"    / Hex(Int64ul),
    "video" / Struct(
        "base"      / Hex(Int64ul),
        "display"   / Hex(Int64ul),
        "stride"    / Hex(Int64ul),
        "width"     / Hex(Int64ul),
        "height"    / Hex(Int64ul),
        "depth"     / Hex(Int64ul),
    ),
    "machine_type"          / Hex(Int32ul),
    Padding(4),
    "devtree"               / Hex(Int64ul),
    "devtree_size"          / Hex(Int32ul),
    "cmdline"               / PaddedString(608, "ascii"),
    Padding(4),
    "boot_flags"            / Hex(Int64ul),
    "mem_size_actual"       / Hex(Int64ul),
)

MachOLoadCmdType = "LoadCmdType" / Enum(Int32ul,
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

MachOCmd = Struct(
    "cmd" / Hex(MachOLoadCmdType),
    "args" / Prefixed(ExprAdapter(Int32ul, obj_ - 8, obj_ + 8), Switch(this.cmd, {
        MachOLoadCmdType.UNIXTHREAD: MachOCmdUnixThread,
        MachOLoadCmdType.SEGMENT_64: MachOCmdSegment64,
        MachOLoadCmdType.UUID: Hex(Bytes(16)),
    }, default=GreedyBytes)),
)

MachOFile = Struct(
    "header" / MachOHeader,
    "cmds" / Array(this.header.ncmds, MachOCmd),
    "extradata" / GreedyBytes,
)

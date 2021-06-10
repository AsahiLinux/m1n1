# SPDX-License-Identifier: MIT
from construct import *

__all__ = ["BootArgs"]

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

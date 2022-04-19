from m1n1.utils import *
from m1n1.constructutils import ConstructClass
from construct import *

from .channels import Channels

class InitData_unkptr20(ConstructClass):
    subcon = Struct(
        "unkptr_0" / Int64ul,
        "unkptr_8" / Int64ul,
        Padding(0x70)
    )

    def __init__(self, heap, shared_heap):
        self.unkptr_0 = heap.malloc(0x40)
        self.unkptr_8 = heap.malloc(0x40) # totally guessing the size on this one

class RegionB_unkprt_188(ConstructClass):
    subcon = Struct(
        "unk_0" / Int32ul,
        "unk_4" / Int32ul,
        "unk_8" / Int32ul,
        "unk_c" / Int32ul,
        "unk_10" / Float32l,
        "unk_14" / Int32ul,
        "unk_18" / Int32ul,
        "unk_1c" / Int32ul,
        "unk_20" / Int32ul,
        "unk_24" / Int32ul,
        "unk_28" / Int32ul,
        "unk_2c" / Int32ul,
        "unk_30" / Int32ul,
        "unk_34" / Int32ul,
        "unk_38" / Int32ul,
        "unk_3c" / Int32ul,
        "unk_40" / Int32ul,
        "unk_44" / Int32ul,
        "unk_48" / Int32ul,
        "unk_4c" / Int32ul,
        "padding" / Bytes(0x24),
        "unk_84" / Float32l,
        "unk_88" / Float32l,
        "unk_8c" / Float32l,
        "unk_90" / Float32l,
        "unk_94" / Float32l,
        "unk_98" / Float32l,
        "unk_9c" / Float32l,

    )

    def __init__(self):
        self.unk_0 = 0
        self.unk_4 = 192000
        self.unk_8 = 0
        self.unk_c = 4
        self.unk_10 = 1.0
        self.unk_14 = 0
        self.unk_18 = 0
        self.unk_1c = 0
        self.unk_20 = 0
        self.unk_24 = 0
        self.unk_28 = 1
        self.unk_2c = 1
        self.unk_30 = 0
        self.unk_34 = 0
        self.unk_38 = 0
        self.unk_3c = 100
        self.unk_40 = 1
        self.unk_44 = 600
        self.unk_48 = 0
        self.unk_4c = 100
        self.padding = b"\x00" * 0x24
        self.unk_84 = 1.02
        self.unk_88 = 1.02
        self.unk_8c = 1.02
        self.unk_90 = 1.02
        self.unk_94 = 1.02
        self.unk_98 = 1.02
        self.unk_9c = 1.02


class IOMapping(ConstructClass):
    subcon = Struct(
        "phys_addr" / Int64ul,
        "virt_addr" / Int64ul,
        "size" / Int32ul,
        "range_size" / Int32ul, # Useally the same as size, but for MCC, this is the size of a single MMC register range.
        "readwrite" / Int64ul
    )

    def __init__(self, phys=0, addr=0, size=0, range_size=0, readwrite=0):
        self.phys_addr = phys
        self.virt_addr = addr
        self.size = size
        self.range_size = range_size
        self.readwrite = readwrite

    def __str__(self):
        if self.virt_addr == 0:
            return "\n<IOMapping: Invalid>"

        hv = self._stream.uat.hv
        dev, range = hv.device_addr_tbl.lookup(self.phys_addr)
        offset = self.phys_addr - range.start
        return f"\nIO Mapping: {['RO', 'RW'][self.readwrite]} {self.virt_addr:#x} -> " \
               f"{dev}+{offset:#x} ({self.size:#x} / {self.range_size:#x})"

class RegionB_unkprt_1a0(ConstructClass):
    subcon = Struct(
        "unk_0" / Int32ul,
        "unk_4" / Int32ul,
        "unk_8" / Int32ul, # Number of IO mappings?
        "unk_c" / Int32ul,
        "unk_10" / Int32ul,
        "unk_14" / Int32ul,
        "unk_18" / Int64ul,
        "unk_20" / Int32ul,
        "unk_24" / Int32ul,
        "unk_28" / Int32ul,
        "unk_2c" / Int32ul,
        "unk_30" / Int64ul, # This might be another IO mapping? But it's weird
        "unk_38" / Int64ul,
        Padding(0x20),
        "unk_data" / Bytes(0x170), # Doesn't seem to be necessary
        "io_mappings" / Array(0x14, IOMapping),
    )

    def __init__(self, heap, shared_heap, info):
        self.unk_0 = 0
        self.unk_4 = 0x13
        self.unk_8 = 0
        self.unk_c = 0x14
        self.unk_10 = 0
        self.unk_14 = 1
        self.unk_18 = 0xffc00000
        self.unk_20 = 0
        self.unk_24 = 0x11
        self.unk_28 = 0
        self.unk_2c = 0x11
        self.unk_30 = 0x6f_ffff8000
        self.unk_38 = 0xffffffa0_11800000

        self.unk_data = b"\0"*0x170
        self.io_mappings = info['io_mappings']


class InitData_RegionB(ConstructClass):
    subcon = Struct(
        "channels" / Channels,
        Padding(0x60),
        "unkptr_170" / Int64ul, # size 0xc0, Empty
        "unkptr_178" / Int64ul, # size: 0x1c0, has random negative 1s, Needed for login screen
        "unkptr_180" / Int64ul, # size: 0x140, Empty
        "unkptr_188_addr" / Int64ul, # size: 0x3b80, few floats, few ints, needed for init
        "unkptr_188" / Pointer(this.unkptr_188_addr, RegionB_unkprt_188),
        "unkptr_190" / Int64ul, # size: 0x80, empty
        "unkptr_198_addr" / Int64ul, # size: 0xc0, fw writes timestamps into this
        "unkptr_198" / Pointer(this.unkptr_198_addr, Bytes(0xc0)),
        "unkptr_1a0_addr" / Int64ul, # size: 0xb80, io stuff
        "unkptr_1a0" / Pointer(this.unkptr_1a0_addr, RegionB_unkprt_1a0),
        "unkptr_1a8" / Int64ul, # repeat of 1a0
        "fwlog_ring2" / Int64ul, #
        "unkptr_1b8" / Int64ul, # Unallocated, Size 0x1000
        "unkptr_1c0" / Int64ul, # Unallocated, size 0x300
        "unkptr_1c8" / Int64ul, # Unallocated, unknown size
        Padding(0x44),
        "unkptr_214" / Int64ul, # Size: 0x4000
        "unkptr_21c" / Int64ul, # Size: 0x4000
    )

    def __init__(self, heap, shared_heap, info):
        self.channels = Channels(heap, shared_heap)
        self.unkptr_170 = heap.malloc(0xc0)
        self.unkptr_178 = heap.malloc(0x1c0)
        self.unkptr_180 = heap.malloc(0x140)
        self.unkptr_188_addr = heap.malloc(0x3b80)
        self.unkptr_188 = RegionB_unkprt_188()
        self.unkptr_190 = heap.malloc(0x80)
        self.unkptr_198_addr = heap.malloc(0xc0)
        self.unkptr_198 = b"\x25" + b"\x00"*0xbf
        self.unkptr_1a0_addr = self.unkptr_1a8 = heap.malloc(0xb80)
        self.unkptr_1a0 = RegionB_unkprt_1a0(heap, shared_heap, info)
        self.fwlog_ring2 = shared_heap.malloc(0x1000)
        self.unkptr_1b8 = heap.malloc(0x1000)
        self.unkptr_1c0 = heap.malloc(0x300)
        self.unkptr_1c8 = heap.malloc(0x1000)
        self.unkptr_214 = self.unkptr_21c = shared_heap.malloc(0x4000)

    def mon(self, add_fn):
        add_fn(self.unkptr_170, 0x140, "unkptr_170")
        add_fn(self.unkptr_178, 0x1c0, "unkptr_178")
        add_fn(self.unkptr_180, 0x140, "unkptr_180")
        add_fn(self.unkptr_188_addr, 0x3b80, "unkptr_188")
        add_fn(self.unkptr_190, 0x80, "unkptr_190")
        add_fn(self.unkptr_198_addr, 0xc0, "unkptr_198")
        add_fn(self.unkptr_1a0_addr, 0xb80, "unkptr_1a0")
        add_fn(self.fwlog_ring2, 0x51000, "fwlog_ring2")
        add_fn(self.unkptr_214, 0x4000, "unkptr_214")

        # Unallocated during init
        #add_fn(self.unkptr_1b8, 0x1000, "unkptr_1b8")
        #add_fn(self.unkptr_1c0, 0x300, "unkptr_1c0")
        #add_fn(self.unkptr_1c8, 0x1000, "unkptr_1c8")

class UatLevelInfo(ConstructClass):
    subcon = Struct(
        "index_shift" / Int8ul,
        "unk_1" / Int8ul, # always 14, page bits?
        "unk_2" / Int8ul, # always 14, also page bits?
        "unk_3" / Int8ul, # always 8
        "unk_4" / Int16ul, # 0x4000, Table size?
        "num_entries" / Int16ul,
        "unk_8" / Int64ul, # always 1
        "unk_10" / Int64ul, # Full address mask? the same for all levels. Always 0x3ffffffc000
        "index_mask" / Int64ul,
    )

    def __init__(self, index_shift, num_entries):
        self.index_shift = index_shift
        self.unk_1 = 14
        self.unk_2 = 14
        self.unk_3 = 8
        self.unk_4 = 0x4000 # I doubt anything other than 16k pages is supported
        self.num_entries = num_entries
        self.unk_8 = 1
        self.unk_10 = 0x3ffffffc000
        self.index_mask = ((num_entries * 8) - 1) << index_shift


class InitData(ConstructClass):

    subcon = Struct(
        "unkptr_0" / Int64ul, # allocation size: 0x4000
        "unk_8" / Default(Int32ul, 0),
        "unk_c"/ Default(Int32ul, 0),
        "regionB_addr" / Int64ul, # 0xfa00c338000 allocation size: 0x34000
        "regionB" / Pointer(this.regionB_addr, InitData_RegionB),
        "regionC_addr" / Int64ul, # 0xfa000200000 allocation size: 0x88000, heap?
        "unkptr_20_addr" / Int64ul, # allocation size: 0x4000, but probably only 0x80 bytes long
        "unkptr_20" / Pointer(this.unkptr_20_addr, InitData_unkptr20),
        "uat_num_levels" / Int8ul,
        "uat_page_bits" / Int8ul,
        "uat_page_size" / Int16ul,
        "uat_level_info" / Array(3, UatLevelInfo),
        Padding(0x18),
        "host_mapped_fw_allocations" / Int32ul, # must be 1
        Padding(0x1000) # For safety
    )


    def __init__(self, heap, shared_heap, info):
        self.unkptr_0 = shared_heap.memalign(0x4000, 0x4000)

        self.regionB_addr = heap.malloc(InitData_RegionB.sizeof())
        self.regionB = InitData_RegionB(heap, shared_heap, info)

        self.regionC_addr = shared_heap.malloc(0x88000)


        self.unkptr_20_addr = shared_heap.malloc(InitData_unkptr20.sizeof())
        self.unkptr_20 = InitData_unkptr20(heap, shared_heap)

        # This section seems to be data that would be used by firmware side page allocation
        # But the current firmware doesn't have this functionality enabled, so it's not used?
        self.uat_num_levels = 3
        self.uat_page_bits = 14
        self.uat_page_size = 0x4000

        self.uat_level_info = [
            UatLevelInfo(36, 8),
            UatLevelInfo(25, 2048),
            UatLevelInfo(14, 2048)
        ]

        # Since the current firmware doesn't have this functionality enabled, we must enabled host
        # mapped firmware allocations
        self.host_mapped_fw_allocations = 1


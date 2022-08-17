from m1n1.utils import *
from m1n1.constructutils import ConstructClass, ConstructValueClass, ROPointer, Dec
from construct import *
from construct.lib import hexundump

from .channels import ChannelInfoSet

__all__ = []

class InitData_unkptr20(ConstructClass):
    subcon = Struct(
        "unkptr_0" / Int64ul,
        "unkptr_8" / Int64ul,
        Padding(0x70)
    )

class AGXHWDataA(ConstructClass):
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
        "unk_50" / Int32ul,
        "unk_54" / HexDump(Bytes(0x20)),
        "unk_74" / Array(16, Float32l),
        "unk_b4" / HexDump(Bytes(0x100)),
        "unk_1b4" / Int32ul,
        "unk_1b8" / Int32ul,
        "unk_1bc" / Int32ul,
        "unk_1c0" / Int32ul,
        "unk_1c4" / Int32ul,
        "unk_1c8" / Int32ul,
        "unk_1cc" / HexDump(Bytes(0x644 - 0x1cc)),
        "pad_644" / HexDump(Bytes(8)),

        "unk_64c" / Int32ul,
        "unk_650" / Int32ul,
        "pad_654" / Int32ul,
        "unk_658" / Float32l,
        "pad_65c" / Int32ul,
        "unk_660" / Float32l,
        "pad_664" / Int32ul,
        "unk_668" / Float32l,
        "pad_66c" / Int32ul,
        "unk_670" / Int32ul,
        "unk_674" / Float32l,
        "unk_678" / Float32l,
        "pad_67c" / Int32ul,
        "unk_680" / Int32ul,
        "unk_684" / Int32ul,
        "unk_688" / Int32ul,
        "unk_68c" / Int32ul,
        "pad_690" / Int32ul,
        "unk_694" / Int32ul,
        "unk_698" / Int32ul,

        "pad_69c" / HexDump(Bytes(0x18)),

        "unk_6b4" / Int32ul,
        "unk_6b8" / Int32ul,
        "unk_6bc" / Int32ul,

        "pad_6c0" / HexDump(Bytes(0x14)),

        "unk_6d4" / Int32ul,
        "unk_6d8" / Int32ul,

        "pad_6dc" / Int32ul,

        "unk_6e0" / Float32l,
        "pad_6e4" / Int32ul,
        "unk_6e8" / Float32l,
        "pad_6ec" / Int32ul,
        "unk_7f0" / Float32l,
        "pad_7f4" / Int32ul,
        "unk_7f8" / Int32ul,
        "unk_7fc" / Float32l,
        "unk_700" / Float32l,
        "pad_704" / Int32ul,

        "unk_708" / Int32ul,
        "unk_70c" / Int32ul,
        "unk_710" / Int32ul,
        "unk_714" / Int32ul,

        "pad_718" / Int32ul,

        "unk_71c" / Float32l,
        "unk_720" / Int32ul,

        "pad_724" / Int32ul,

        "unk_728" / Int32ul,
        "unk_72c" / Int32ul,
        "unk_730" / Float32l,
        "unk_734" / Int32ul,

        "unk_738" / Int32ul,
        "unk_73c" / Int32ul,
        "unk_740" / Int32ul,
        "unk_744" / Int32ul,
        "unk_748" / Array(4, Float32l),
        "unk_758" / Int32ul,
        "unk_75c" / Int32ul,
        "pad_760" / Int32ul,
        "unk_764" / Int32ul,
        "unk_768" / Int32ul,
        "unk_76c" / Int32ul,
        "pad_770" / Int32ul,
        "unk_774" / Int32ul,
        "unk_778" / Int32ul,
        "unk_77c" / Int32ul,

        "unk_780" / Float32l,
        "unk_784" / Float32l,
        "unk_788" / Float32l,
        "unk_78c" / Float32l,
        "unk_790" / Float32l,
        "unk_794" / Float32l,
        "unk_798" / Float32l,
        "unk_79c" / Float32l,
        "unk_7a0" / Float32l,
        "unk_7a4" / Float32l,
        "unk_7a8" / Float32l,

        "unk_7ac" / Dec(Int32ul),
        "unk_7b0" / Dec(Int32ul),
        "unk_7b4" / Dec(Int32ul),

        "pad_7b8" / Int32ul,

        "unk_7bc" / Float32l,
        "unk_7c0" / Int32ul,

        "pad_7c4" / HexDump(Bytes(0x18)),

        "unk_7dc" / Int32ul,
        "unk_7e0" / Dec(Int32ul),
        "pad_7e4" / Int32ul,

        "unk_7e8" / HexDump(Bytes(0x14)),

        "unk_7fc" / Float32l,
        "unk_800" / Float32l,
        "unk_804" / Float32l,
        "unk_808" / Int32ul,
        "pad_80c" / Int32ul,
        "unk_810" / Int32ul,
        "pad_814" / Int32ul,
        "unk_818" / Int32ul,
        "unk_81c" / Int32ul,
        "pad_820" / Int32ul,
        "unk_824" / Float32l,
        "unk_828" / Dec(Int32ul),
        "unk_82c" / Int32ul,
        "unk_830" / Float32l,
        "unk_834" / Float32l,
        "unk_838" / Int32ul,
        "unk_83c" / Int32ul,
        "pad_840" / HexDump(Bytes(0x86c - 0x838 - 8)),

        "unk_86c" / Int32ul,
        "unk_870" / Int32ul,
        "unk_874" / Int32ul,
        "unk_878" / Int32ul,
        "unk_87c" / Int32ul,
        "unk_880" / Int32ul,
        "unk_884" / Int32ul,
        "pad_888" / Int32ul,
        "unk_88c" / Int32ul,
        "pad_890" / Int32ul,
        "unk_894" / Float32l,
        "pad_898" / Int32ul,
        "unk_89c" / Float32l,
        "pad_8a0" / Int32ul,
        "unk_8a4" / Int32ul,
        "unk_8a8" / Float32l,
        "unk_8ac" / Float32l,
        "pad_8b0" / Int32ul,
        "unk_8b4" / Int32ul,
        "unk_8b8" / Int32ul,
        "unk_8bc" / Dec(Int32ul),
        "unk_8c0" / Dec(Int32ul),
        "unk_8c4" / Int32ul,
        "unk_8c8" / Int32ul,
        "unk_8cc" / Int32ul,
        "pad_8d0" / HexDump(Bytes(0x14)),
        "unk_8e4" / Int32ul,
        "unk_8e8" / Int32ul,
        "unk_8ec" / Dec(Int32ul),
        "unk_8f0" / Int32ul,
        "unk_8f4" / Int32ul,
        "pad_8f8" / Int32ul,
        "pad_8fc" / Int32ul,
        "unk_900" / HexDump(Bytes(0x294)),
        "unk_b94" / Dec(Int32ul),
        "unk_b98" / Int32ul,
        "unk_b9c" / Int32ul,
        "unk_ba0" / Int64ul,
        "unk_ba8" / Int64ul,
        "unk_bb0" / Int32ul,
        "unk_bb4" / Int32ul,
        "pad_bb8" / HexDump(Bytes(0xc2c - 0xbb8)),

        "unk_c2c" / Int32ul,
        "unk_c30" / Int32ul,
        "unk_c34" / Int32ul,
        "unk_c38" / Int32ul,
        "unk_c3c" / Int32ul,
        "unk_c40" / Int32ul,
        "unk_c44" / Float32l,
        "unk_c48" / Float32l,
        "unk_c4c" / Float32l,
        "unk_c50" / Dec(Int32ul),
        "unk_c54" / Dec(Int32ul),
        "unk_c58" / Float32l,
        "unk_c5c" / Dec(Int32ul),
        "unk_c60" / Dec(Int32ul),
        "unk_c64" / Dec(Int32ul),
        "unk_c68" / Dec(Int32ul),
        "unk_c6c" / Float32l,
        "unk_c70" / Float32l,
        "pad_c74" / Int32ul,
        "unk_c78" / Int32ul,
        "unk_c7c" / Int32ul,
        "unk_c80" / Int32ul,
        "unk_c84" / Int32ul,
        "unk_c88" / Int32ul,
        "unk_c8c" / Int32ul,

        "unk_c90" / HexDump(Bytes(0x60)),
        "unk_cf0" / HexDump(Bytes(0x60)),
        "unk_d50" / HexDump(Bytes(0x20)),
        "unk_d70" / HexDump(Bytes(0x20)),
        "unk_d90" / HexDump(Bytes(0x40)),
        "unk_dd0" / HexDump(Bytes(0x40)),
        "unk_e10" / HexDump(Bytes(0x20)),
        "pad_e30" / HexDump(Bytes(0x7e0)),
        "unk_1610" / HexDump(Bytes(0x30)),
        "unk_1640" / HexDump(Bytes(0x2000)),
        "unk_3640" / HexDump(Bytes(0x50)),
        "unk_3690" / HexDump(Bytes(0x50)),
        "unk_36e0" / HexDump(Bytes(0x50)),
        "unk_3730" / HexDump(Bytes(0x4c0)),
        "unk_3bf0" / HexDump(Bytes(0x10)),
        "unk_3c00" / HexDump(Bytes(0xa0)),
        "unk_3ca0" / Int64ul,
        "unk_3ca8" / Int64ul,
        "unk_3cb0" / Int64ul,
        "unk_3cb8" / Int64ul,
        "unk_3cc0" / Int64ul,
        "unk_3cc8" / Int64ul,
        "unk_3cd0" / Int64ul,
        "unk_3cd8" / Int64ul,
        "unk_3ce0" / HexDump(Bytes(0x40)),
        "unk_3d20" / HexDump(Bytes(0x4c)),
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
        self.unk_3c = 300
        self.unk_40 = 1
        self.unk_44 = 600
        self.unk_48 = 0
        self.unk_4c = 100
        self.unk_50 = 0
        self.unk_54 = bytes(0x20)
        # perf related
        self.unk_74 = [0] * 16

        self.unk_b4 = bytes(0x100)
        self.unk_1b4 = 0
        self.unk_1b8 = 0
        self.unk_1bc = 0
        self.unk_1c0 = 0
        self.unk_1c4 = 0
        self.unk_1c8 = 0
        self.unk_1cc = bytes(0x644 - 0x1cc)

        self.pad_644 = bytes(8)

        self.unk_64c = 0x271
        self.unk_650 = 0x0
        self.pad_654 = 0x0
        self.unk_658 = 0.9968051314353943
        self.pad_65c = 0x0
        self.unk_660 = 0.00319488812237978
        self.pad_664 = 0x0
        self.unk_668 = 0.020212899893522263
        self.pad_66c = 0x0
        self.unk_670 = 0x0
        self.unk_674 = 19551.0
        self.unk_678 = 5.2831854820251465
        self.pad_67c = 0x0
        self.unk_680 = 0xbcfb676e
        self.unk_684 = 0xfffffdd0
        self.unk_688 = 0x0
        self.unk_68c = 0x258
        self.pad_690 = 0x0
        self.unk_694 = 0x0
        self.unk_698 = 0x4c5f
        self.pad_69c = bytes(0x18)
        self.unk_6b4 = 0x0
        self.unk_6b8 = 0x258
        self.unk_6bc = 0x0
        self.pad_6c0 = bytes(0x14)
        self.unk_6d4 = 0x30
        self.unk_6d8 = 0x0
        self.pad_6dc = 0x0
        self.unk_6e0 = 0.9166666865348816
        self.pad_6e4 = 0x0
        self.unk_6e8 = 0.0833333358168602
        self.pad_6ec = 0x0
        self.unk_7f0 = 0.7320000529289246
        self.pad_7f4 = 0x0
        self.unk_7f8 = 0x0
        self.unk_700 = 6.900000095367432
        self.pad_704 = 0x0
        self.unk_708 = 0x0
        self.unk_70c = 0x28
        self.unk_710 = 0x258
        self.unk_714 = 0x0
        self.pad_718 = 0x0
        self.unk_71c = 0.0
        self.unk_720 = 0x4c5f
        self.pad_724 = 0x0
        self.unk_728 = 0x64
        self.unk_72c = 0x0
        self.unk_730 = 0.0
        self.unk_734 = 0x0
        self.unk_738 = 0x0
        self.unk_73c = 0x0
        self.unk_740 = 0x0
        self.unk_744 = 0x0
        self.unk_748 = [0.0, 0.0, 0.0, 0.0]
        self.unk_758 = 0x0
        self.unk_75c = 0x55
        self.pad_760 = 0x0
        self.unk_764 = 0x64
        self.unk_768 = 0x19
        self.unk_76c = 0x6
        self.pad_770 = 0x0
        self.unk_774 = 0x6
        self.unk_778 = 0x1
        self.unk_77c = 0x0
        self.unk_780 = 0.800000011920929
        self.unk_784 = 0.9800000190734863
        self.unk_788 = 0.20000000298023224
        self.unk_78c = 0.019999999552965164
        self.unk_790 = 7.895683288574219
        self.unk_794 = 0.19739200174808502
        self.unk_798 = 0.0
        self.unk_79c = 95.0
        self.unk_7a0 = 14.707962989807129
        self.unk_7a4 = 6.853981018066406
        self.unk_7a8 = 3.1578948497772217
        self.unk_7ac = 300
        self.unk_7b0 = 600
        self.unk_7b4 = 300
        self.pad_7b8 = 0x0
        self.unk_7bc = 0.0
        self.unk_7c0 = 0x55
        self.pad_7c4 = bytes(0x18)
        self.unk_7dc = 0x0
        self.unk_7e0 = 300
        self.pad_7e4 = 0x0
        self.unk_7e8 = bytes(0x14)
        self.unk_7fc = 65536.0
        self.unk_800 = 40.0
        self.unk_804 = 600.0
        self.unk_808 = 0x4fe
        self.pad_80c = 0x0
        self.unk_810 = 0x0
        self.pad_814 = 0x0
        self.unk_818 = 0x28
        self.unk_81c = 0x0
        self.pad_820 = 0x0
        self.unk_824 = 100.0
        self.unk_828 = 600
        self.unk_82c = 0x0
        self.unk_830 = 0.800000011920929
        self.unk_834 = 0.20000000298023224
        self.unk_838 = 0x0
        self.unk_83c = 0x0
        self.pad_840 = bytes(0x2c)
        self.unk_86c = 0x0
        self.unk_870 = 0x12
        self.unk_874 = 0x0
        self.unk_878 = 0x1f40
        self.unk_87c = 0xffffff24
        self.unk_880 = 0x4
        self.unk_884 = 0x0
        self.pad_888 = 0x0
        self.unk_88c = 0x0
        self.pad_890 = 0x0
        self.unk_894 = 1.0
        self.pad_898 = 0x0
        self.unk_89c = 1.600000023841858
        self.pad_8a0 = 0x0
        self.unk_8a4 = 0x0
        self.unk_8a8 = 65536.0
        self.unk_8ac = 5.0
        self.pad_8b0 = 0x0
        self.unk_8b4 = 0x0
        self.unk_8b8 = 0x28
        self.unk_8bc = 600
        self.unk_8c0 = 600
        self.unk_8c4 = 0x0
        self.unk_8c8 = 0x0
        self.unk_8cc = 0x2698
        self.pad_8d0 = bytes(0x14)
        self.unk_8e4 = 0x0
        self.unk_8e8 = 0x0
        self.unk_8ec = 600
        self.unk_8f0 = 0x0
        self.unk_8f4 = 0x0
        self.pad_8f8 = 0x0
        self.pad_8fc = 0x0
        self.unk_900 = bytes(0x294)
        self.unk_b94 = 600
        self.unk_b98 = 0x0
        self.unk_b9c = 0x0
        self.unk_ba0 = 0x0
        self.unk_ba8 = 0x0
        self.unk_bb0 = 0x0
        self.unk_bb4 = 0x0
        self.pad_bb8 = bytes(0x74)
        self.unk_c2c = 0x1
        self.unk_c30 = 0x1
        self.unk_c34 = 0x4c5f
        self.unk_c38 = 0x4c5f
        self.unk_c3c = 0x4c5f
        self.unk_c40 = 0x0
        self.unk_c44 = 0.0
        self.unk_c48 = 0.9919999837875366
        self.unk_c4c = 0.00800000037997961
        self.unk_c50 = 500
        self.unk_c54 = 1000
        self.unk_c58 = 0.0
        self.unk_c5c = 30000
        self.unk_c60 = 29900
        self.unk_c64 = 27500
        self.unk_c68 = 55000
        self.unk_c6c = 0.999854564666748
        self.unk_c70 = 0.00014545454178005457
        self.pad_c74 = 0x0
        self.unk_c78 = 0x0
        self.unk_c7c = 0x0
        self.unk_c80 = 0x0
        self.unk_c84 = 0x0
        self.unk_c88 = 0x0
        self.unk_c8c = 0x0
        self.unk_c90 = bytes(0x60)
        self.unk_cf0 = bytes.fromhex('0000000000000000f40100000000000000000000b6f37d3f000000006f12033c0000000090c2753d0000000000000000000080470000804000000000000000002800000058020000580200000000000000be98465f4c000000000000e8030000')
        self.unk_d50 = bytes.fromhex('0000000000000000000000000000000000000000580200000000000000000000')
        self.unk_d70 = bytes.fromhex('0000000000000000000000000000000000000000000000000000000000000080')
        self.unk_d90 = bytes.fromhex('0400000000000000000000009a99193f00000000cccccc3e00000000e162c53e000000000000000000008047c3f5584100000000000000000000000058020000')
        self.unk_dd0 = bytes(0x40)
        self.unk_e10 = bytes.fromhex('0000000000000000000000001200000000000000700000000100000000000000')
        self.pad_e30 = bytes(0x7e0)
        self.unk_1610 = bytes.fromhex('000000000000000000000000000000000000000000000000000000001200000000000000010000000000000001000000')
        self.unk_1640 = bytes(0x2000)
        self.unk_3640 = bytes.fromhex('00000000ffffffff82720000ea5000000a370000be2500001f1c0000fb160000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff00000000000000000000')
        self.unk_3690 = bytes(0x50)
        self.unk_36e0 = bytes.fromhex('0000000000000000ffff0000000000000008000055150000ffffffffffffffffffffffffffffffffffffffffffffffff0000000000000000ffffffffffffffffffffffffffffffff0000000000000000')
        self.unk_3730 = bytes(0x4c0)
        self.unk_3bf0 = bytes.fromhex('00000000000000000700c00000000000')
        self.unk_3c00 = bytes(0xa0)
        self.unk_3ca0 = 0
        self.unk_3ca8 = 0
        self.unk_3cb0 = 0
        self.unk_3cb8 = 0
        self.unk_3cc0 = 0
        self.unk_3cc8 = 0
        self.unk_3cd0 = 0
        self.unk_3cd8 = 0
        self.unk_3ce0 = bytes.fromhex('000000000000000001000000000000000000000000007a4400000000000000000000000000000000000000000000000000000000000034420000000000000000')
        self.unk_3d20 = bytes(0x4c)

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

        try:
            hv = self._stream.uat.hv
        except AttributeError:
            hv = None

        if hv:
            dev, range = hv.device_addr_tbl.lookup(self.phys_addr)
            offset = self.phys_addr - range.start
            return f"\nIO Mapping: {['RO', 'RW'][self.readwrite]} {self.virt_addr:#x} -> " \
                f"{dev}+{offset:#x} ({self.size:#x} / {self.range_size:#x})"
        else:
            return f"\nIO Mapping: {['RO', 'RW'][self.readwrite]} {self.virt_addr:#x} -> " \
                f"{self.phys_addr:#x} ({self.size:#x} / {self.range_size:#x})"


class AGXHWDataB(ConstructClass):
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
        "unkptr_38" / Int64ul,
        "pad_40" / HexDump(Bytes(0x20)),
        "yuv_matrices" / Array(15, Array(3, Array(4, Int16sl))),
        "pad_1c8" / HexDump(Bytes(8)),
        "io_mappings" / Array(0x14, IOMapping),
        "chip_id" / Int32ul,
        "unk_454" / Int32ul,
        "unk_458" / Int32ul,
        "unk_45c" / Int32ul,
        "unk_460" / Int32ul,
        "unk_464" / Int32ul,
        "unk_468" / Int32ul,
        "unk_46c" / Int32ul,
        "unk_470" / Int32ul,
        "unk_474" / Int32ul,
        "unk_478" / Int32ul,
        "unk_47c" / Int32ul,
        "unk_480" / Int32ul,
        "unk_484" / Int32ul,
        "unk_488" / Int32ul,
        "unk_48c" / Int32ul,
        "unk_490" / Int32ul,
        "unk_494" / Int32ul,
        "pad_498" / Padding(4),

        "unk_49c" / Int32ul,
        "unk_4a0" / Int32ul,
        "unk_4a4" / Int32ul,
        "pad_4a8" / Padding(4),

        "unk_4ac" / Int32ul,
        "pad_4b0" / Padding(8),

        "unk_4b8" / Int32ul,
        "unk_4bc" / Padding(4),

        "unk_4c0" / Int32ul,
        "unk_4c4" / Int32ul,
        "unk_4c8" / Int32ul,
        "unk_4cc" / Int32ul,
        "unk_4d0" / Int32ul,
        "unk_4d4" / Int32ul,
        "unk_4d8" / Padding(4),

        "unk_4dc" / Int32ul,
        "unk_4e0" / Int64ul,
        "unk_4e8" / Int32ul,
        "unk_4ec" / Int32ul,
        "unk_4f0" / Int32ul,
        "unk_4f4" / Int32ul,
        "unk_4f8" / Int32ul,
        "unk_4fc" / Int32ul,
        "unk_500" / Int32ul,
        "unk_504" / Int32ul,
        "unk_508" / Int32ul,
        "unk_50c" / Int32ul,
        "unk_510" / Int32ul,
        "unk_514" / Int32ul,
        "unk_518" / Int32ul,
        "unk_51c" / Int32ul,
        "unk_520" / Int32ul,
        "unk_524" / Int32ul,
        "unk_528" / Int32ul,
        "unk_52c" / Int32ul,
        "unk_530" / Int32ul,
        "unk_534" / Int32ul,
        "unk_538" / Int32ul,
        "unk_53c" / Int32ul,
        "unk_540" / Int32ul,
        "unk_544" / Int32ul,
        "unk_548" / Int32ul,
        "unk_54c" / Int32ul,
        "unk_550" / Int32ul,
        "unk_554" / Int32ul,
        "unk_558" / Int32ul,
        "unk_55c" / Int32ul,
        "unk_560" / Int32ul,
        "unk_564" / Int32ul,
        "unk_568" / Int32ul,
        "unk_56c" / Int32ul,
        "num_pstates" / Int32ul,
        "frequencies" / Array(16, Int32ul),
        "voltages" / Array(16, Array(8, Int32ul)),
        "voltages_sram" / Array(16, Array(8, Int32ul)),
        "unk_9b4" / Array(16, Float32l),
        "unk_9f4" / Array(16, Int32ul),
        "perf_levels" / Array(16, Int32ul),

        "unk_a74" / Int32ul,
        "unk_a78" / Int32ul,
        "unk_a7c" / Int32ul,

        "unk_a80" / Int32ul,
        "unk_a84" / Int32ul,
        "unk_a88" / Int32ul,
        "unk_a8c" / Int32ul,

        "pad_a90" / Padding(0x24),
        "min_volt" / Int32ul,
        "unk_ab8" / Int32ul,
        "unk_abc" / Int32ul,
        "unk_ac0" / Int32ul,
        "pad_ac4" / Padding(8),
        "unk_acc" / Int32ul,
        "unk_ad0" / Int32ul,
        "pad_ad4" / Padding(16),
        "unk_ae4" / Array(4, Int32ul),
        "pad_af4" / Padding(4),
        "unk_af8" / Int32ul,
        "pad_afc" / Padding(8),
        "unk_b04" / Int32ul,
        "unk_b08" / Int32ul,
        "unk_b0c" / Int32ul,
        "unk_b10" / Int32ul,
        "pad_b14" / Padding(8),
        "unk_b1c" / Int32ul,
        "unk_b20" / Int32ul,
        "unk_b24" / Int32ul,
        "unk_b28" / Int32ul,
        "unk_b2c" / Int32ul,
        "unk_b30" / Int32ul,
        "pad_b34" / Padding(4),
        "unk_b38" / Array(6, Int64ul),
        "unk_b68" / Int32ul,
    )

    def __init__(self):
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
        self.pad_40 = bytes(0x20)
        # unmapped?
        self.unkptr_38 = 0xffffffa0_11800000
        self.pad_1c8 = bytes(8)

        # Note: these are rounded poorly, need to recompute.
        self.yuv_matrices = [
            [ # BT.601 full range -> RGB
                [ 0x2000,    -0x8,  0x2cdb, -0x2cd3],
                [ 0x2000,  -0xb00, -0x16da,  0x21da],
                [ 0x2000,  0x38b6,     0x8, -0x38be],
            ],
            [ # BT.709 full range -> RGB
                [ 0x2000,    -0x1,  0x3264, -0x3263],
                [ 0x2000,  -0x5fe,  -0xefb,  0x14f9],
                [ 0x2000,  0x3b61,     0x1, -0x3b62],
            ],
            [ # BT.2020 full range -> RGB
                [ 0x2000,     0x0,  0x2f30, -0x2f30],
                [ 0x2000,  -0x544, -0x1248,  0x178c],
                [ 0x2000,  0x3c34,    -0x1, -0x3c33],
            ],
            [ # BT.601 limited range -> RGB
                [ 0x2568,    -0x9,  0x3343, -0x37e7],
                [ 0x2568,  -0xc92, -0x1a1e,  0x2203],
                [ 0x2568,  0x40cf,     0x9, -0x4585],
            ],
            [ # BT.709 limited range -> RGB
                [ 0x2568,    -0x1,  0x3997, -0x3e43],
                [ 0x2568,  -0x6d9, -0x111f,  0x134b],
                [ 0x2568,  0x43dd,     0x1, -0x488b],
            ],
            [ # BT.2020 limited range -> RGB
                [ 0x2568,     0x0,  0x35ee, -0x3a9b],
                [ 0x2568,  -0x604, -0x14e5,  0x163c],
                [ 0x2568,  0x44ce,    -0x1, -0x497a],
            ],
            [ # Unknown YUV->RGB
                [ 0x24cb,     0x0,  0x2cfa, -0x3676],
                [ 0x24cb,  -0xb0a, -0x16e9,  0x1877],
                [ 0x24cb,  0x38d9,     0x0, -0x4255],
            ],
            [ # null
                [    0x0,     0x0,     0x0,     0x0],
                [    0x0,     0x0,     0x0,     0x0],
                [    0x0,     0x0,     0x0,     0x0],
            ],
            [ # RGB -> BT.601 full range
                [ 0x2645,  0x4b23,   0xe98,     0x0],
                [-0x15a1, -0x2a5e,  0x3fff,  0x4000],
                [ 0x4000, -0x35a2,  -0xa5e,  0x4000],
            ],
            [ # RGB -> BT.709 full range
                [ 0x1b37,  0x5b8c,   0x93d,     0x0],
                [ -0xeac, -0x3155,  0x4000,  0x4000],
                [ 0x4000, -0x3a24,  -0x5dd,  0x4000],
            ],
            [ # RGB -> BT.2020 full range
                [ 0x21a0,  0x56c9,   0x797,     0x0],
                [-0x11de, -0x2e22,  0x4000,  0x4000],
                [ 0x4000, -0x3adb,  -0x526,  0x4000],
            ],
            [ # RGB -> BT.601 limited range
                [ 0x20bd,  0x4047,   0xc7c,   0x800],
                [-0x12ed, -0x2513,  0x3800,  0x4000],
                [ 0x3800, -0x2eee,  -0x912,  0x4000],
            ],
            [ # RGB -> BT.709 limited range
                [ 0x1748,  0x4e51,   0x7e7,   0x800],
                [ -0xcd6, -0x2b2a,  0x3800,  0x4000],
                [ 0x3800, -0x32df,  -0x521,  0x4000],
            ],
            [ # RGB -> BT.2020 limited range
                [ 0x1cc4,  0x4a3e,   0x67e,   0x800],
                [ -0xfa3, -0x285e,  0x3800,  0x4000],
                [ 0x3800, -0x337f,  -0x481,  0x4000],
            ],
            [ # Unknown (identity?)
                [-0x8000,     0x0,     0x0,     0x0],
                [    0x0, -0x8000,     0x0,     0x0],
                [    0x0,     0x0, -0x8000,     0x0],
            ],
        ]

        self.unk_454 = 0x1
        self.unk_458 = 0x1
        self.unk_45c = 0x0
        self.unk_460 = 0x1
        self.unk_464 = 0x1
        self.unk_468 = 0x1
        self.unk_46c = 0x0
        self.unk_470 = 0x0
        self.unk_474 = 0x0
        self.unk_478 = 0x0
        self.unk_47c = 0x1
        self.unk_480 = 0x0
        self.unk_484 = 0x1
        self.unk_488 = 0x0
        self.unk_48c = 0x1
        self.unk_490 = 24000
        self.unk_494 = 0x8
        self.unk_49c = 0x1
        self.unk_4a0 = 0x1
        self.unk_4a4 = 0x1
        self.unk_4ac = 0x0
        self.unk_4b8 = 0x0
        self.unk_4c0 = 0x1f
        self.unk_4c4 = 0x0
        self.unk_4c8 = 0x0
        self.unk_4cc = 0x0
        self.unk_4d0 = 0x0
        self.unk_4d4 = 0x0
        self.unk_4dc = 0x0
        self.unk_4e0 = 0x0
        self.unk_4e8 = 0x0
        self.unk_4ec = 0x0
        self.unk_4f0 = 0x1
        self.unk_4f4 = 0x1
        self.unk_4f8 = 0x0
        self.unk_4fc = 0x0
        self.unk_500 = 0x0
        self.unk_504 = 0x31
        self.unk_508 = 0x0
        self.unk_50c = 0x0
        self.unk_510 = 0x0
        self.unk_514 = 0x0
        self.unk_518 = 0x0
        self.unk_51c = 0x0
        self.unk_520 = 0x0
        self.unk_524 = 0x1
        self.unk_528 = 0x0
        self.unk_52c = 0x0
        self.unk_530 = 0x0
        self.unk_534 = 0x0
        self.unk_538 = 0x0
        self.unk_53c = 0x8
        self.unk_540 = 0x0
        self.unk_544 = 0x0
        self.unk_548 = 0x0
        self.unk_54c = 0x0
        self.unk_550 = 0x0
        self.unk_554 = 0x1
        self.unk_558 = 0xfffb8000
        self.unk_55c = 0x9
        self.unk_560 = 0xb
        self.unk_564 = 0x4
        self.unk_568 = 0x8
        self.unk_56c = 0x6
        self.num_pstates = 0x7

        self.frequencies = [0] * 16
        self.voltages = [[0] * 8 for i in range(16)]
        self.voltages_sram = [[0] * 8 for i in range(16)]
        self.unk_9b4 = [0.] * 16
        self.unk_9f4 = [0] * 16
        self.perf_levels = [0] * 16

        self.unk_a74 = 0x0
        self.unk_a78 = 0x0
        self.unk_a7c = 0x0
        self.unk_a80 = 0x0
        self.unk_a84 = 0x24
        self.unk_a88 = 0x49
        self.unk_a8c = 0x64

        self.min_volt = 850
        self.unk_ab8 = 0x48
        self.unk_abc = 0x8
        self.unk_ac0 = 0x1020
        self.unk_acc = 0x0
        self.unk_ad0 = 0x0
        self.unk_ae4 = [0x0, 0xf, 0x3f, 0x3f]
        self.unk_af8 = 0x0
        self.unk_b04 = 0x0
        self.unk_b08 = 0x0
        self.unk_b0c = 0x0
        self.unk_b10 = 0x1
        self.unk_b1c = 0x0
        self.unk_b20 = 0x0
        self.unk_b24 = 0x1
        self.unk_b28 = 0x1
        self.unk_b2c = 0x1
        self.unk_b30 = 0x0
        self.unk_b38 = [0xffffffffffffffff, 0xffffffffffffffff, 0xffffffffffffffff, 0xffffffffffffffff, 0xffffffffffffffff, 0xffffffffffffffff]
        self.unk_b68 = 0x0

class InitData_BufferMgrCtl(ConstructValueClass):
    subcon = Array(256, Bytes(0x10))

    def __init__(self):
        self.value = [bytes(0x10)] * 256

class InitData_GPUQueueStatsTA(ConstructClass):
    subcon = Struct(
        "busy" / Int32ul,
        "unk_4" / Int32ul,
        "cur_cmdqueue" / Int64ul,
        "cur_count" / Int32ul,
        "unk_14" / Int32ul,
    )
    def __init__(self):
        self.busy = 0
        self.unk_4 = 0
        self.cur_cmdqueue = 0
        self.cur_count = 0
        self.unk_14 = 0

class InitData_GPUStatsTA(ConstructClass):
    subcon = Struct(
        "unk_4" / Int32ul,
        "queues" / Array(4, InitData_GPUQueueStatsTA),
        "unk_68" / Bytes(0x8),
        "unk_70" / Int32ul,
        "unk_74" / Int32ul,
        "unk_timestamp" / Int64ul,
        "unk_80" / Bytes(0x40),
    )

    def __init__(self):
        self.unk_4 = 0
        self.queues = [InitData_GPUQueueStatsTA() for i in range(4)]
        self.unk_68 = bytes(0x8)
        self.unk_70 = 0
        self.unk_74 = 0
        self.unk_timestamp = 0
        self.unk_80 = bytes(0x40)

class InitData_GPUQueueStats3D(ConstructClass):
    subcon = Struct(
        "busy" / Int32ul,
        "cur_cmdqueue" / Int64ul,
        "unk_c" / Int32ul,
        "unk_10" / Int32ul,
        "unk_14" / HexDump(Bytes(0x28 - 0x14)),
    )
    def __init__(self):
        self.busy = 0
        self.cur_cmdqueue = 0
        self.unk_c = 0
        self.unk_10 = 0
        self.unk_14 = 0

class InitData_GPUStats3D(ConstructClass):
    subcon = Struct(
        "unk_0" / Bytes(0x18),
        "queues" / Array(4, InitData_GPUQueueStats3D),
        "unk_68" / Int32ul,
        "cur_cmdqueue" / Int64ul,
        "unk_74" / Bytes(0xf8 - 0x7c),
        "tvb_overflows_1" / Int32ul,
        "tvb_overflows_2" / Int32ul,
        "unk_f8" / Int32ul,
        "unk_fc" / Int32ul,
        "cur_stamp_id" / Int32sl,
        "unk_104" / Bytes(0x14),
        "unk_118" / Int32sl,
        "unk_11c" / Int32ul,
        "unk_120" / Int32ul,
        "unk_124" / Bytes(0x1c),
        "unk_140" / Int32ul,
        "unk_144" / Int32ul,
        "unk_timestamp" / Int64ul,
        "unk_150" / Bytes(0x1c0 - 0x158),
    )

    def __init__(self):
        self.unk_0 = bytes(0x18)
        self.queues = [InitData_GPUQueueStats3D() for i in range(4)]
        self.unk_68 = 0
        self.cur_cmdqueue = 0
        self.unk_74 = 0
        self.tvb_overflows_1 = 0
        self.tvb_overflows_2 = 0
        self.unk_f8 = 0
        self.unk_fc = 0
        self.cur_stamp_id = -1
        self.unk_104 = bytes(0x14)
        self.unk_118 = -1
        self.unk_11c = 0
        self.unk_120 = 0
        self.unk_124 = bytes(0x1c)
        self.unk_140 = 0
        self.unk_144 = 0
        self.unk_timestamp = 0
        self.unk_150 = bytes(0x1c0 - 0x158)

class InitData_GPUGlobalStatsTA(ConstructClass):
    subcon = Struct(
        "total_cmds" / Int32ul,
        "stats" / InitData_GPUStatsTA,
    )

    def __init__(self):
        self.total_cmds = 0
        self.stats = InitData_GPUStatsTA()

class InitData_GPUGlobalStats3D(ConstructClass):
    subcon = Struct(
        "total_cmds" / Int32ul,
        "unk_4" / Int32ul,
        "stats" / InitData_GPUStats3D,
    )

    def __init__(self):
        self.total_cmds = 0
        self.unk_4 = 0
        self.stats = InitData_GPUStats3D()

class InitData_RegionB(ConstructClass):
    subcon = Struct(
        "channels" / ChannelInfoSet,
        "pad_110" / Padding(0x50),
        "unk_160" / Default(Int64ul, 0),
        "unk_168" / Default(Int64ul, 0),
        "stats_ta_addr" / Int64ul,
        "stats_ta" / ROPointer(this.stats_ta_addr, InitData_GPUGlobalStatsTA),
        "stats_3d_addr" / Int64ul,
        "stats_3d" / ROPointer(this.stats_3d_addr, InitData_GPUGlobalStats3D),
        "stats_cp_addr" / Int64ul,
        "stats_cp" / ROPointer(this.stats_cp_addr, Bytes(0x140)),
        "hwdata_a_addr" / Int64ul,
        "hwdata_a" / ROPointer(this.hwdata_a_addr, AGXHWDataA),
        "unkptr_190" / Int64ul, # size: 0x80, empty
        "unk_190" / ROPointer(this.unkptr_190, Bytes(0x80)),
        "unkptr_198" / Int64ul, # size: 0xc0, fw writes timestamps into this
        "unk_198" / ROPointer(this.unkptr_198, Bytes(0xc0)),
        "hwdata_b_addr" / Int64ul, # size: 0xb80, io stuff
        "hwdata_b" / ROPointer(this.hwdata_b_addr, AGXHWDataB),
        "hwdata_b_addr2" / Int64ul, # repeat of 1a0
        "fwlog_ring2" / Int64ul, #
        "unkptr_1b8" / Int64ul, # Unallocated, Size 0x1000
        "unk_1b8" / Lazy(ROPointer(this.unkptr_1b8, Bytes(0x1000))),
        "unkptr_1c0" / Int64ul, # Unallocated, size 0x300
        "unk_1c0" / Lazy(ROPointer(this.unkptr_1c0, Bytes(0x300))),
        "unkptr_1c8" / Int64ul, # Unallocated, unknown size
        "unk_1c8" / Lazy(ROPointer(this.unkptr_1c8, Bytes(0x1000))),
        "pad_1d0" / Padding(0x44),
        "buffer_mgr_ctl_addr" / Int64ul, # Size: 0x4000
        "buffer_mgr_ctl" / ROPointer(this.buffer_mgr_ctl_addr, InitData_BufferMgrCtl),
        "buffer_mgr_ctl_addr2" / Int64ul, # Size: 0x4000
        "pad_224" / HexDump(Bytes(0x685c)),
        "unk_6a80" / Int32ul,
        "unk_6a84" / Int32ul,
        "unkpad_6a88" / HexDump(Bytes(0x14)),
        "unk_6a9c" / Int32ul,
        "unk_6aa0" / Int32ul,
        "unk_6aa4" / Int32ul,
        "unk_6aa8" / Int32ul,
        "unk_6aac" / Int32ul,
        "unk_6ab0" / Int32ul,
        "unk_6ab4" / Int32ul,
        "unk_6ab8" / Int32ul,
        "unk_6abc" / Int32ul,
        "unk_6ac0" / Int32ul,
        "unk_6ac4" / Int32ul,
        "unk_6ac8" / Int32ul,
        "unk_6acc" / Int32ul,
        "unk_6ad0" / Int32ul,
        "unk_6ad4" / Int32ul,
        "unk_6ad8" / Int32ul,
        "unk_6adc" / Int32ul,
        "unk_6ae0" / Int32ul,
        "unk_6ae4" / Int32ul,
        "unk_6ae8" / Int32ul,
        "unk_6aec" / Int32ul,
        "unk_6af0" / Int32ul,
        "unk_6af4" / Int32ul,
        "unk_6af8" / Int32ul,
        "unk_6afc" / Int32ul,
        "pad_6b00" / HexDump(Bytes(0xc0)),
    )

    def __init__(self):
        super().__init__()
        self.pad_224 = bytes(0x685c)
        self.unkpad_6a88 = bytes(0x14)
        self.pad_6b00 = bytes(0xc0)

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

class InitData_RegionC(ConstructClass):
    subcon = Struct(
        "unk_0" / HexDump(Bytes(0x28)),
        "unk_28" / Int32ul,
        "unk_2c" / Int32ul,
        "unk_30" / Int32ul,
        "unk_34" / Int32ul,
        "unk_38" / HexDump(Bytes(0x1c)),
        "unk_54" / Int16ul,
        "unk_56" / Int16ul,
        "unk_58" / Int16ul,
        "unk_5a" / Int32ul,
        "unk_5e" / Int32ul,
        "unk_62" / Int32ul,
        "unk_66" / Int32ul,
        "unk_6a" / HexDump(Bytes(0x16)),
        "unk_80" / HexDump(Bytes(0xf80)),
        "unk_1000" / HexDump(Bytes(0x7000)),
        "unk_8000" / HexDump(Bytes(0x900)),
        "unk_8900" / HexDump(Bytes(0x50)),
        "unk_8950" / HexDump(Bytes(0x6c)),
        "unk_89bc" / Int32ul,
        "unk_89c0" / Int32ul,
        "unk_89c4" / Int32sl,
        "unk_89c8" / Int32ul,
        "unk_89cc" / Float32l,
        "unk_89d0" / Float32l,
        "unk_89d4" / HexDump(Bytes(0xc)),
        "unk_89e0" / Float32l,
        "unk_89e4" / Int32ul,
        "unk_89e8" / Float32l,
        "unk_89ec" / Float32l,
        "unk_89f0" / Int32ul,
        "unk_89f4" / Int32ul,
        "unk_89f8" / Int32ul,
        "unk_89fc" / Int32ul,
        "unk_8a00" / Int32ul,
        "unk_8a04" / Int32ul,
        "unk_8a08" / Int32ul,
        "unk_8a0c" / Int32ul,
        "unk_8a10" / HexDump(Bytes(0x30)),
        "unk_8a40" / HexDump(Bytes(0x50)),
        "unk_8a90" / HexDump(Bytes(0x50)),
        "unk_8ae0" / HexDump(Bytes(0x4c0)),
        "unk_8fa0" / HexDump(Bytes(0x10)),
        "unk_8fb0" / HexDump(Bytes(0x50)),
        "unk_9000" / HexDump(Bytes(0x10)),
        "unk_9010" / HexDump(Bytes(0xff0)),
        "unk_a000" / HexDump(Bytes(0x6000)),
        "unk_10000" / HexDump(Bytes(0xe80)),
        "unk_10e80" / HexDump(Bytes(0x10)),
        "unk_10e90" / HexDump(Bytes(0x190)),
        "unk_11020" / Int32ul,
        "unk_11024" / Int32ul,
        "unk_11028" / Int32ul,
        "unk_1102c" / Int32ul,
        "unk_11030" / Int32ul,
        "unk_11034" / Int32ul,
        "unk_11038" / Int32ul,
        "unk_1103c" / Int32ul,
        "unk_11040" / Int32ul,
        "unk_11044" / HexDump(Bytes(0xbc)),
        "unk_11100" / HexDump(Bytes(0x7e0)),
        "unk_118e0" / Int32ul,
        "unk_118e4" / HexDump(Bytes(0x1c)),
        "unk_11900" / HexDump(Bytes(0x440)),
    )

    def __init__(self):
        self.unk_0 = bytes(0x28)
        self.unk_28 = 1
        self.unk_2c = 1
        self.unk_30 = 1
        self.unk_34 = 0x78
        self.unk_38 = bytes(0x1c)
        self.unk_54 = 0xffff
        self.unk_56 = 0x28
        self.unk_58 = 0xffff
        self.unk_5a = 0
        self.unk_5e = 1
        self.unk_62 = 0
        self.unk_66 = 1
        self.unk_6a = bytes(0x16)
        self.unk_80 = bytes(0xf80)
        self.unk_1000 = bytes(0x7000)
        self.unk_8000 = bytes(0x900)
        self.unk_8900 = bytes.fromhex('01000000000000005f4c0000580200005802000000000000000000005802000000000000010000007d00000090c2753d00008040280000007d00000030750000cc740000db1a00000000000000000000')
        self.unk_8950 = bytes(0x6c)
        self.unk_89bc = 9880
        self.unk_89c0 = 8000
        self.unk_89c4 = -220
        self.unk_89c8 = 0
        self.unk_89cc = 5.0
        self.unk_89d0 = 1.6
        self.unk_89d4 = bytes(0xc)
        self.unk_89e0 = 1
        self.unk_89e4 = 0x4c5f
        self.unk_89e8 = 6.9
        self.unk_89ec = 0.732
        self.unk_89f0 = 0
        self.unk_89f4 = 0
        self.unk_89f8 = 0x7282
        self.unk_89fc = 0x50ea
        self.unk_8a00 = 0x370a
        self.unk_8a04 = 0x25be
        self.unk_8a08 = 0x1c1f
        self.unk_8a0c = 0x16fb
        self.unk_8a10 = bytes.fromhex('ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff00000000000000000000')
        self.unk_8a40 = bytes(0x50)
        self.unk_8a90 = bytes.fromhex('0000000000000000ffff0000000000000008000055150000ffffffffffffffffffffffffffffffffffffffffffffffff0000000000000000ffffffffffffffffffffffffffffffff0000000000000000')
        self.unk_8ae0 = bytes(0x4c0)
        self.unk_8fa0 = bytes.fromhex('00000000000000000700c00000000000')
        self.unk_8fb0 = bytes(0x50)
        self.unk_9000 = bytes.fromhex('00000000000000000000000001000000')
        self.unk_9010 = bytes(0xff0)
        self.unk_a000 = bytes(0x6000)
        self.unk_10000 = bytes(0xe80)
        self.unk_10e80 = bytes.fromhex('0b000000010000000000000000000000')
        self.unk_10e90 = bytes(0x190)
        self.unk_11020 = 40
        self.unk_11024 = 10
        self.unk_11028 = 250
        self.unk_1102c = 0

        self.unk_11030 = 2
        self.unk_11034 = 40
        self.unk_11038 = 5
        self.unk_1103c = 0
        self.unk_11040 = 0
        self.unk_11044 = bytes(0xbc)
        self.unk_11100 = bytes(0x7e0)
        self.unk_118e0 = 40
        self.unk_118e4 = bytes(0x1c)
        self.unk_11900 = bytes(0x440)

class UatLevelInfo(ConstructClass):
    subcon = Struct(
        "unk_3" / Int8ul, # always 8
        "unk_1" / Int8ul, # always 14, page bits?
        "unk_2" / Int8ul, # always 14, also page bits?
        "index_shift" / Int8ul,
        "num_entries" / Int16ul,
        "unk_4" / Int16ul, # 0x4000, Table size?
        "unk_8" / Int64ul, # always 1
        "unk_10" / Int64ul, # Full address mask? the same for all levels. Always 0x3ffffffc000
        "index_mask" / Int64ul,
    )

    def __init__(self, index_shift, num_entries):
        self.index_shift = index_shift
        # t6000
        #self.unk_1 = 14
        #self.unk_2 = 14
        #self.unk_3 = 8
        #self.unk_4 = 0x4000 # I doubt anything other than 16k pages is supported
        #self.num_entries = num_entries
        #self.unk_8 = 1
        #self.unk_10 = 0x3ffffffc000
        #self.index_mask = ((num_entries * 8) - 1) << index_shift

        self.unk_1 = 14
        self.unk_2 = 14
        self.unk_3 = 8
        self.unk_4 = 0x4000 # I doubt anything other than 16k pages is supported
        self.num_entries = num_entries
        self.unk_8 = 1
        self.unk_10 = 0xffffffc000
        self.index_mask = (num_entries - 1) << index_shift

class InitData(ConstructClass):

    subcon = Struct(
        "regionA_addr" / Int64ul, # allocation size: 0x4000
        "regionA" / ROPointer(this.regionA_addr, HexDump(Bytes(0x4000))),
        "unk_8" / Default(Int32ul, 0),
        "unk_c"/ Default(Int32ul, 0),
        "regionB_addr" / Int64ul, # 0xfa00c338000 allocation size: 0x6bc0
        "regionB" / ROPointer(this.regionB_addr, InitData_RegionB),
        "regionC_addr" / Int64ul, # 0xfa000200000 allocation size: 0x11d40, heap?
        "regionC" / ROPointer(this.regionC_addr, InitData_RegionC),
        "unkptr_20_addr" / Int64ul, # allocation size: 0x4000, but probably only 0x80 bytes long
        "unkptr_20" / ROPointer(this.unkptr_20_addr, InitData_unkptr20),
        "uat_page_size" / Int16ul,
        "uat_page_bits" / Int8ul,
        "uat_num_levels" / Int8ul,
        "uat_level_info" / Array(3, UatLevelInfo),
        "pad_8c" / HexDump(Default(Bytes(0x14), bytes(0x14))),
        "host_mapped_fw_allocations" / Int32ul, # must be 1
        Padding(0x1000) # For safety
    )

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)

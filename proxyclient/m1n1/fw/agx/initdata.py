from m1n1.utils import *
from m1n1.constructutils import *
from construct import *
from construct.lib import hexundump

from .channels import ChannelInfoSet, ChannelInfo

__all__ = []

class InitData_FWStatus(ConstructClass):
    subcon = Struct(
        "fwctl_channel" / ChannelInfo,
        "halt_count" / Int32ul,
        ZPadding(0xc),
        "halted" / Int32ul,
        ZPadding(0xc),
        "resume" / Int32ul,
        ZPadding(0xc),
        "unk_40" / Int32ul,
        ZPadding(0xc),
        "unk_ctr" / Int32ul,
        ZPadding(0xc),
        "unk_60" / Int32ul,
        ZPadding(0xc),
        "unk_70" / Int32ul,
        ZPadding(0xc),
    )

    def __init__(self):
        super().__init__()
        self.halt_count = 0
        self.halted = 0
        self.resume = 0
        self.unk_40 = 0
        self.unk_ctr = 0
        self.unk_60 = 0
        self.unk_70 = 0

class AGXHWDataShared1(ConstructClass):
    subcon = Struct(
        "unk_0" / Int32ul,
        "unk_4" / Int32ul,
        "unk_8" / Int32ul,
        "unk_c" / Int32ul,
        "unk_10" / Int32ul,
        "unk_14" / Int32ul,
        "unk_18" / Int32ul,
        "unk_1c" / Int32ul,
        "unk_20" / HexDump(Bytes(0x26)),
        "unk_46" / HexDump(Bytes(0x6)),
        "unk_4c" / HexDump(Bytes(0x58)),
        "unk_a4" / Int32ul,
        "unk_a8" / Int32ul,
    )

    def __init__(self):
        super().__init__()
        self.unk_0 = 0
        self.unk_4 = 0xffffffff
        self.unk_8 = 0x7282
        self.unk_c = 0x50ea
        self.unk_10 = 0x370a
        self.unk_14 = 0x25be
        self.unk_18 = 0x1c1f
        self.unk_1c = 0x16fb
        self.unk_20 = b"\xff" * 0x26
        self.unk_46 = bytes(0x6)
        self.unk_4c = bytes(0x58)
        self.unk_a4 = 0xffff
        self.unk_a8 = 0

class AGXHWDataShared2(ConstructClass):
    subcon = Struct(
        "unk_ac" / Int32ul,
        "unk_b0" / Int32ul,
        "unk_b4" / HexDump(Bytes(0x18)),
        "unk_cc" / HexDump(Bytes(0x8)),
        "unk_d4" / HexDump(Bytes(0x10)),
        "unk_e4" / HexDump(Bytes(0x8)),
        "unk_ec" / HexDump(Bytes(0x4c8)),
        "unk_5b4" / Int32ul,
    )

    def __init__(self):
        super().__init__()
        self.unk_ac = 0x800
        self.unk_b0 = 0x1555
        self.unk_b4 = b"\xff" * 24
        self.unk_cc = bytes(8)
        self.unk_d4 = b"\xff" * 16
        self.unk_e4 = bytes(8)
        self.unk_ec = bytes(0x4c8)
        self.unk_5b4 = 0xc0007

class AGXHWDataA130Extra(ConstructClass):
    subcon = Struct(
        "unk_0" / HexDump(Bytes(0x38)),
        "unk_38" / Dec(Int32ul),
        "unk_3c" / Dec(Int32ul),
        "unk_40" / Dec(Int32ul),
        "unk_44" / Int32ul,
        "unk_48" / Int32ul,
        "unk_4c" / Dec(Int32ul),
        "unk_50" / Int32ul,
        "unk_54" / Dec(Int32ul),
        "unk_58" / Int32ul,
        "unk_5c" / Int32ul,
        "unk_60" / Float32l,
        "unk_64" / Float32l,
        "unk_68" / Float32l,
        "unk_6c" / Float32l,
        "unk_70" / Float32l,
        "unk_74" / Float32l,
        "unk_78" / Float32l,
        "unk_7c" / Float32l,
        "unk_80" / Float32l,
        "unk_84" / Float32l,
        "unk_88" / Int32ul,
        "unk_8c" / Dec(Int32ul),
        "unk_90" / Dec(Int32ul),
        "unk_94" / Int32ul,
        "unk_98" / Int32ul,
        "unk_9c" / Float32l,
        "unk_a0" / Dec(Int32ul),
        "unk_a4" / Int32ul,
        "unk_a8" / Dec(Int32ul),
        "unk_ac" / Dec(Int32ul),
        "unk_b0" / Dec(Int32ul),
        "unk_b4" / Int32ul,
        "unk_b8" / Dec(Int32ul),
        "unk_bc" / Int32ul,
        "unk_c0" / Int32ul,
        "unk_c4" / Float32l,
        "unk_c8" / HexDump(Bytes(0x4c)),
        "unk_114" / Float32l,
        "unk_118" / Int32ul,
        "unk_11c" / Int32ul,
        "unk_120" / Int32ul,
        "unk_124" / Dec(Int32ul),
        "unk_128" / Dec(Int32ul),
        "unk_12c" / HexDump(Bytes(0x8c)),
    )

    def __init__(self):
        super().__init__()
        self.unk_0 = bytes(0x38)
        self.unk_38 = 4
        self.unk_3c = 8000
        self.unk_40 = 2500
        self.unk_44 = 0x0
        self.unk_48 = 0xffffffff
        self.unk_4c = 50
        self.unk_50 = 0x0
        self.unk_54 = 50
        self.unk_58 = 0x1
        self.unk_5c = 0x0
        self.unk_60 = 0.88888888
        self.unk_64 = 0.66666666
        self.unk_68 = 0.111111111
        self.unk_6c = 0.33333333
        self.unk_70 = -0.4
        self.unk_74 = -0.8
        self.unk_78 = 0.0
        self.unk_7c = 65536.0
        self.unk_80 = -5.0
        self.unk_84 = -10.0
        self.unk_88 = 0x0
        self.unk_8c = 40
        self.unk_90 = 600
        self.unk_94 = 0x0
        self.unk_98 = 0x0
        self.unk_9c = 8000.0
        self.unk_a0 = 1400
        self.unk_a4 = 0x0
        self.unk_a8 = 72
        self.unk_ac = 24
        self.unk_b0 = 1728000
        self.unk_b4 = 0x0
        self.unk_b8 = 576000
        self.unk_bc = 0x0
        self.unk_c0 = 0x0
        self.unk_c4 = 65536.0
        self.unk_c8 = bytes(0x4c)
        self.unk_114 = 65536.0
        self.unk_118 = 0x0
        self.unk_11c = 0x0
        self.unk_120 = 0x0
        self.unk_124 = 40
        self.unk_128 = 600
        self.unk_12c = bytes(0x8c)

class AGXHWDataA(ConstructClass):
    subcon = Struct(
        "unk_0" / Int32ul,
        "unk_4" / Int32ul,
        Ver("13.0 beta4", "unk_8_0" / Int32ul),
        "unk_8" / Int32ul,
        "pwr_status" / Int32ul,
        "unk_10" / Float32l,
        "unk_14" / Int32ul,
        "unk_18" / Int32ul,
        "unk_1c" / Int32ul,
        "unk_20" / Int32ul,
        "unk_24" / Int32ul,
        "actual_pstate" / Int32ul,
        "tgt_pstate" / Int32ul,
        "unk_30" / Int32ul,
        "cur_pstate" / Int32ul,
        "unk_38" / Int32ul,
        Ver("13.0 beta4", "unk_3c_0" / Int32ul),
        "unk_3c" / Int32ul,
        "unk_40" / Int32ul,
        "unk_44" / Int32ul,
        "unk_48" / Int32ul,
        "unk_4c" / Int32ul,
        "freq_mhz" / Float32l,
        "unk_54" / HexDump(Bytes(0x20)),
        Ver("13.0 beta4", "unk_74_0" / Int32ul),
        "unk_74" / Array(16, Float32l),
        "unk_b4" / HexDump(Bytes(0x100)),
        "unk_1b4" / Int32ul,
        "temp_c" / Int32ul,
        "avg_power_mw" / Dec(Int32ul),
        "update_ts" / Int64ul,
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
        Ver("13.0 beta4", "unk_6b8_0" / HexDump(Bytes(0x10))),
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
        "unk_6f0" / Float32l,
        "pad_6f4" / Int32ul,
        "unk_6f8" / Int32ul,
        "unk_6fc" / Float32l,
        "unk_700" / Float32l,
        "pad_704" / Int32ul,

        "unk_708" / Int32ul,
        "unk_70c" / Int32ul,
        "unk_710" / Int32ul,
        "unk_714" / Int32ul,

        "pad_718" / Int32ul,

        "unk_71c" / Float32l,
        "unk_720" / Int32ul,

        "cur_power_mw_2" / Int32ul,

        "unk_728" / Int32ul,
        "unk_72c" / Int32ul,
        Ver("13.0 beta4", "unk_730_0" / Int32ul),
        Ver("13.0 beta4", "unk_730_4" / Int32ul),
        Ver("13.0 beta4", "unk_730_8" / Int32ul),
        Ver("13.0 beta4", "unk_730_c" / Int32ul),
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

        "use_percent" / Float32l,
        "unk_7c0" / Int32ul,

        "pad_7c4" / HexDump(Bytes(0x18)),

        "unk_7dc" / Int32ul,
        Ver("13.0 beta4", "unk_7e0_0" / HexDump(Bytes(0x10))),
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
        Ver("13.0 beta4", "unk_8e4_0" / HexDump(Bytes(0x10))),
        "unk_8e4" / Int32ul,
        "unk_8e8" / Int32ul,
        "unk_8ec" / Dec(Int32ul),
        "unk_8f0" / Int32ul,
        "unk_8f4" / Int32ul,
        "pad_8f8" / Int32ul,
        "pad_8fc" / Int32ul,
        "unk_900" / HexDump(Bytes(0x294)),
        "unk_b94" / Dec(Int32ul),
        "freq_with_off" / Int32ul,
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
        Ver("13.0 beta4", "unk_c58_0" / Int32ul),
        Ver("13.0 beta4", "unk_c58_4" / Int32ul),
        "unk_c58" / Float32l,
        "unk_c5c" / Dec(Int32ul),
        "unk_c60" / Dec(Int32ul),
        "unk_c64" / Dec(Int32ul),
        "unk_c68" / Dec(Int32ul),
        Ver("13.0 beta4", "unk_c6c_0" / Dec(Int32ul)),
        Ver("13.0 beta4", "unk_c6c_4" / Dec(Int32ul)),
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
        Ver("13.0 beta4", "unk_cf0_0" / HexDump(Bytes(0x20))),
        "unk_cf0" / Int32ul,
        "unk_cf4" / Int32ul,
        "unk_cf8" / Dec(Int32ul),
        "unk_cfc" / Int32ul,
        "unk_d00" / Int32ul,
        "unk_d04" / Float32l,
        "unk_d08" / Int32ul,
        "unk_d0c" / Float32l,
        "unk_d10" / Int32ul,
        "unk_d14" / Float32l,
        "unk_d18" / Int32ul,
        "unk_d1c" / Int32ul,
        "unk_d20" / Float32l,
        "unk_d24" / Float32l,
        "unk_d28" / Int32ul,
        "unk_d2c" / Int32ul,
        "unk_d30" / Int32ul,
        "unk_d34" / Int32ul,
        "unk_d38" / Int32ul,
        "unk_d3c" / Int32ul,
        "unk_d40" / Float32l,
        "unk_d44" / Int32ul,
        "unk_d48" / Int32ul,
        "unk_d4c" / Int32ul,
        "unk_d50" / Int32ul,
        Ver("13.0 beta4", "unk_d54_0" / Int32ul),
        Ver("13.0 beta4", "unk_d54_4" / HexDump(Bytes(0xc))),
        "unk_d54" / HexDump(Bytes(0x10)),
        "unk_d64" / Int32ul,
        "unk_d68" / Bytes(0x24),
        "unk_d8c" / Int32ul,
        "unk_d90" / Int32ul,
        "unk_d94" / Int32ul,
        "unk_d98" / Int32ul,
        "unk_d9c" / Float32l,
        "unk_da0" / Int32ul,
        "unk_da4" / Float32l,
        "unk_da8" / Int32ul,
        "unk_dac" / Float32l,
        "unk_db0" / Int32ul,
        "unk_db4" / Int32ul,
        "unk_db8" / Float32l,
        "unk_dbc" / Float32l,
        "unk_dc0" / Int32ul,
        "unk_dc4" / Int32ul,
        "unk_dc8" / Int32ul,
        "unk_dcc" / Int32ul,
        "unk_dd0" / HexDump(Bytes(0x40)),
        Ver("13.0 beta4", "unk_e10_0" / AGXHWDataA130Extra),
        "unk_e10" / HexDump(Bytes(0x20)),
        "pad_e30" / HexDump(Bytes(0x7e0)),
        "unk_1610" / HexDump(Bytes(0x28)),
        Ver("..13.0 beta4", "unk_1638" / HexDump(Bytes(0x8))),
        "unk_1640" / HexDump(Bytes(0x2000)),
        "unk_3640" / Int32ul,
        "hws1" / AGXHWDataShared1,
        Ver("13.0 beta4", "unk_pad1" / HexDump(Bytes(0x20))),
        "hws2" / AGXHWDataShared2,
        "unk_3bfc" / Int32ul,
        "unk_3c00" / HexDump(Bytes(0xa0)),
        "unk_3ca0" / Int64ul,
        "unk_3ca8" / Int64ul,
        "unk_3cb0" / Int64ul,
        "ts_last_idle" / Int64ul,
        "ts_last_poweron" / Int64ul,
        "ts_last_poweroff" / Int64ul,
        "unk_3cd0" / Int64ul,
        "unk_3cd8" / Int64ul,
        Ver("13.0 beta4", "unk_3ce0_0" / Int32ul),
        "unk_3ce0" / HexDump(Bytes(0x40)),
        "unk_3d20" / HexDump(Bytes(0x4c)),
        Ver("13.0 beta4", "unk_3d6c" / HexDump(Bytes(0x38))),
    )

    def __init__(self):
        super().__init__()
        self.unk_0 = 0
        self.unk_4 = 192000
        self.unk_8_0 = 192000
        self.unk_8 = 0
        self.pwr_status = 4
        self.unk_10 = 1.0
        self.unk_14 = 0
        self.unk_18 = 0
        self.unk_1c = 0
        self.unk_20 = 0
        self.unk_24 = 0
        self.actual_pstate = 1
        self.tgt_pstate = 1
        self.unk_30 = 0
        self.cur_pstate = 0
        self.unk_38 = 0
        self.unk_3c_0 = 0
        self.unk_3c = 300
        self.unk_40 = 1
        self.unk_44 = 600
        self.unk_48 = 0
        self.unk_4c = 100
        self.freq_mhz = 0.0
        self.unk_54 = bytes(0x20)
        self.unk_74_0 = 0
        # perf related
        self.unk_74 = [0] * 16

        self.unk_b4 = bytes(0x100)
        self.unk_1b4 = 0
        self.temp_c = 0
        self.avg_power_mw = 0
        self.update_ts = 0
        self.unk_1c8 = 0
        self.unk_1cc = bytes(0x644 - 0x1cc)

        self.pad_644 = bytes(8)

        self.unk_64c = 625
        self.unk_650 = 0
        self.pad_654 = 0
        self.unk_658 = 0.9968051314353943
        self.pad_65c = 0
        self.unk_660 = 0.00319488812237978
        self.pad_664 = 0
        # gpu-pwr-integral-gain
        self.unk_668 = 0.0202128999
        self.pad_66c = 0
        self.unk_670 = 0
        self.unk_674 = 19551.0
        # gpu-pwr-proportional-gain
        self.unk_678 = 5.2831854820
        self.pad_67c = 0
        self.unk_680 = 0xbcfb676e
        self.unk_684 = 0xfffffdd0
        self.unk_688 = 0
        self.unk_68c = 600
        self.pad_690 = 0
        self.unk_694 = 0
        self.unk_698 = 19551
        self.pad_69c = bytes(0x18)
        self.unk_6b4 = 0
        self.unk_6b8_0 = bytes(0x10)
        self.unk_6b8 = 600
        self.unk_6bc = 0
        self.pad_6c0 = bytes(0x14)
        self.unk_6d4 = 48
        self.unk_6d8 = 0
        self.pad_6dc = 0
        self.unk_6e0 = 0.9166666865348816
        self.pad_6e4 = 0
        self.unk_6e8 = 0.0833333358168602
        self.pad_6ec = 0
        # gpu-ppm-ki / gpu-avg-power-target-filter-tc?
        self.unk_6f0 = 0.732
        self.pad_6f4 = 0
        self.unk_6f8 = 0
        if Ver.check("13.0 beta4"):
            self.unk_6fc = 65536.0
        else:
            self.unk_6fc = 0
        # gpu-ppm-kp
        self.unk_700 = 6.9
        self.pad_704 = 0
        self.unk_708 = 0
        # gpu-pwr-min-duty-cycle?
        self.unk_70c = 40
        self.unk_710 = 600
        self.unk_714 = 0
        self.pad_718 = 0
        self.unk_71c = 0.0
        self.unk_720 = 19551
        self.cur_power_mw_2 = 0x0
        self.unk_728 = 100
        self.unk_72c = 0
        self.unk_730_0 = 0x232800
        self.unk_730_4 = 0
        self.unk_730_8 = 0
        self.unk_730_c = 0
        self.unk_730 = 0.0
        self.unk_734 = 0
        self.unk_738 = 0
        self.unk_73c = 0
        self.unk_740 = 0
        self.unk_744 = 0
        self.unk_748 = [0.0, 0.0, 0.0, 0.0]
        self.unk_758 = 0
        # gpu-perf-tgt-utilization
        self.unk_75c = 85
        self.pad_760 = 0
        self.unk_764 = 100
        self.unk_768 = 25
        self.unk_76c = 6
        self.pad_770 = 0x0
        self.unk_774 = 6
        self.unk_778 = 1
        self.unk_77c = 0x0
        self.unk_780 = 0.8
        self.unk_784 = 0.98
        self.unk_788 = 0.2
        self.unk_78c = 0.02
        self.unk_790 = 7.895683288574219
        # gpu-perf-integral-gain2
        self.unk_794 = 0.19739200174808502
        self.unk_798 = 0.0
        self.unk_79c = 95.0
        self.unk_7a0 = 14.707962989807129
        # gpu-perf-proportional-gain2
        self.unk_7a4 = 6.853981018066406
        self.unk_7a8 = 3.1578948497772217
        self.unk_7ac = 300
        self.unk_7b0 = 600
        self.unk_7b4 = 300
        self.pad_7b8 = 0x0
        self.use_percent = 0.0
        self.unk_7c0 = 0x55
        self.pad_7c4 = bytes(0x18)
        self.unk_7dc = 0x0
        self.unk_7e0_0 = bytes(0x10)
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
        # gpu-pwr-min-duty-cycle?
        self.unk_818 = 40
        self.unk_81c = 0x0
        self.pad_820 = 0x0
        self.unk_824 = 100.0
        self.unk_828 = 600
        self.unk_82c = 0x0
        self.unk_830 = 0.8
        self.unk_834 = 0.2
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
        self.unk_89c = 1.6
        self.pad_8a0 = 0x0
        self.unk_8a4 = 0x0
        self.unk_8a8 = 65536.0
        # gpu-fast-die0-proportional-gain?
        self.unk_8ac = 5.0
        self.pad_8b0 = 0x0
        self.unk_8b4 = 0x0
        # gpu-pwr-min-duty-cycle?
        self.unk_8b8 = 40
        self.unk_8bc = 600
        self.unk_8c0 = 600
        self.unk_8c4 = 0
        self.unk_8c8 = 0
        self.unk_8cc = 9880
        self.pad_8d0 = bytes(0x14)
        self.unk_8e4_0 = bytes(0x10)
        self.unk_8e4 = 0
        self.unk_8e8 = 0
        self.unk_8ec = 600
        self.unk_8f0 = 0
        self.unk_8f4 = 0
        self.pad_8f8 = 0
        self.pad_8fc = 0
        self.unk_900 = bytes(0x294)
        self.unk_b94 = 600
        self.freq_with_off = 0x0
        self.unk_b9c = 0
        self.unk_ba0 = 0
        self.unk_ba8 = 0
        self.unk_bb0 = 0
        self.unk_bb4 = 0
        self.pad_bb8 = bytes(0x74)
        self.unk_c2c = 1
        self.unk_c30 = 1
        self.unk_c34 = 19551
        self.unk_c38 = 19551
        self.unk_c3c = 19551
        self.unk_c40 = 0
        self.unk_c44 = 0.0
        self.unk_c48 = 0.992
        self.unk_c4c = 0.008
        self.unk_c50 = 500
        # gpu-avg-power-filter-tc-ms
        self.unk_c54 = 1000
        self.unk_c58_0 = 24000000
        self.unk_c58_4 = 0
        self.unk_c58 = 0.0
        # gpu-power-zone-target-0
        self.unk_c5c = 30000
        # above minus gpu-power-zone-target-offset-0?
        self.unk_c60 = 29900
        self.unk_c64 = 27500
        self.unk_c68 = 55000
        self.unk_c6c_0 = 1320000000
        self.unk_c6c_4 = 0
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
        self.unk_cf0_0 = bytes(0x20)
        self.unk_cf0 = 0
        self.unk_cf4 = 0
        self.unk_cf8 = 500
        self.unk_cfc = 0
        self.unk_d00 = 0
        self.unk_d04 = 0.992
        self.unk_d08 = 0
        self.unk_d0c = 0.008
        self.unk_d10 = 0
        self.unk_d14 = 0.06
        self.unk_d18 = 0
        self.unk_d1c = 0
        self.unk_d20 = 65536.0
        self.unk_d24 = 4.0
        self.unk_d28 = 0
        self.unk_d2c = 0
        self.unk_d30 = 0x28
        self.unk_d34 = 600
        self.unk_d38 = 600
        self.unk_d3c = 0
        self.unk_d40 = 19551.0
        self.unk_d44 = 19551
        self.unk_d48 = 0
        self.unk_d4c = 1000
        self.unk_d50 = 0
        self.unk_d54_0 = 24000000
        self.unk_d54_4 = bytes(0xc)
        self.unk_d54 = bytes(0x10)
        self.unk_d64 = 600
        self.unk_d68 = bytes(0x24)
        self.unk_d8c = 0x80000000
        self.unk_d90 = 4
        self.unk_d94 = 0
        self.unk_d98 = 0
        self.unk_d9c = 0.6
        self.unk_da0 = 0
        self.unk_da4 = 0.4
        self.unk_da8 = 0
        self.unk_dac = 0.38552
        self.unk_db0 = 0
        self.unk_db4 = 0
        self.unk_db8 = 65536.0
        self.unk_dbc = 13.56
        self.unk_dc0 = 0
        self.unk_dc4 = 0
        self.unk_dc8 = 0
        self.unk_dcc = 600
        self.unk_dd0 = bytes(0x40)

        self.unk_e10_0 = AGXHWDataA130Extra()
        self.unk_e10 = bytes.fromhex('0000000000000000000000001200000000000000700000000100000000000000')
        self.pad_e30 = bytes(0x7e0)
        self.unk_1610 = bytes.fromhex('00000000000000000000000000000000000000000000000000000000120000000000000001000000')
        self.unk_1638 = bytes.fromhex('0000000001000000')
        self.unk_1640 = bytes(0x2000)
        self.unk_3640 = 0
        self.hws1 = AGXHWDataShared1()
        self.unk_pad1 = bytes(0x20)
        self.hws2 = AGXHWDataShared2()
        self.unk_3bfc = 0
        self.unk_3c00 = bytes(0xa0)
        self.unk_3ca0 = 0 # timestamp?
        self.unk_3ca8 = 0
        self.unk_3cb0 = 0
        self.ts_last_idle = 0
        self.ts_last_poweron = 0
        self.ts_last_poweroff = 0
        self.unk_3cd0 = 0
        self.unk_3cd8 = 0
        self.unk_3ce0_0 = 0
        self.unk_3ce0 = bytes.fromhex('000000000000000001000000000000000000000000007a4400000000000000000000000000000000000000000000000000000000000034420000000000000000')
        self.unk_3d20 = bytes(0x4c)
        self.unk_3d6c = bytes(0x38)

class IOMapping(ConstructClass):
    _MAPTYPE = {
        0: "RO",
        1: "RW",
    }

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
            return f"\nIO Mapping: {self._MAPTYPE.get(self.readwrite, self.readwrite)} {self.virt_addr:#x} -> " \
                f"{dev}+{offset:#x} ({self.size:#x} / {self.range_size:#x})"
        else:
            return f"\nIO Mapping: {self._MAPTYPE.get(self.readwrite, self.readwrite)} {self.virt_addr:#x} -> " \
                f"{self.phys_addr:#x} ({self.size:#x} / {self.range_size:#x})"


class AGXHWDataB(ConstructClass):
    subcon = Struct(
        Ver("..13.0 beta4", "unk_0" / Int64ul),
        "unk_8" / Int64ul,
        Ver("..13.0 beta4", "unk_10" / Int64ul),
        "unk_18" / Int64ul,
        "unk_20" / Int64ul,
        "unk_28" / Int64ul,
        "unk_30" / Int64ul,
        "unkptr_38" / Int64ul,
        "pad_40" / HexDump(Bytes(0x20)),
        Ver("..13.0 beta4", "yuv_matrices" / Array(15, Array(3, Array(4, Int16sl)))),
        Ver("13.0 beta4", "yuv_matrices" / Array(63, Array(3, Array(4, Int16sl)))),
        "pad_1c8" / HexDump(Bytes(8)),
        "io_mappings" / Array(0x14, IOMapping),
        Ver("13.0 beta4", "unk_450_0" / HexDump(Bytes(0x68))),
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
        "pad_498" / ZPadding(4),

        "unk_49c" / Int32ul,
        "unk_4a0" / Int32ul,
        "unk_4a4" / Int32ul,
        "pad_4a8" / ZPadding(4),

        "unk_4ac" / Int32ul,
        "pad_4b0" / ZPadding(8),

        "unk_4b8" / Int32ul,
        "unk_4bc" / ZPadding(4),

        "unk_4c0" / Int32ul,
        "unk_4c4" / Int32ul,
        "unk_4c8" / Int32ul,
        "unk_4cc" / Int32ul,
        "unk_4d0" / Int32ul,
        "unk_4d4" / Int32ul,
        "unk_4d8" / ZPadding(4),

        "unk_4dc" / Int32ul,
        "unk_4e0" / Int64ul,
        "unk_4e8" / Int32ul,
        "unk_4ec" / Int32ul,
        "unk_4f0" / Int32ul,
        "unk_4f4" / Int32ul,
        "unk_4f8" / Int32ul,
        "unk_4fc" / Int32ul,
        "unk_500" / Int32ul,
        Ver("13.0 beta4", "unk_504_0" / Int32ul),
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
        Ver("13.0 beta4", "unk_53c_0" / Int32ul),
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
        "max_pstate" / Int32ul,
        Ver("..13.0 beta4", "num_pstates" / Int32ul),
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
        "pad_a90" / ZPadding(0x24),
        Ver("..13.0 beta4", "min_volt" / Int32ul),
        Ver("..13.0 beta4", "unk_ab8" / Int32ul),
        Ver("..13.0 beta4", "unk_abc" / Int32ul),
        Ver("..13.0 beta4", "unk_ac0" / Int32ul),

        Ver("13.0 beta4", "unk_ac4_0" / HexDump(Bytes(0x1f0))),

        "pad_ac4" / ZPadding(8),
        "unk_acc" / Int32ul,
        "unk_ad0" / Int32ul,
        "pad_ad4" / ZPadding(16),
        "unk_ae4" / Array(4, Int32ul),
        "pad_af4" / ZPadding(4),
        "unk_af8" / Int32ul,
        "pad_afc" / ZPadding(8),
        "unk_b04" / Int32ul,
        "unk_b08" / Int32ul,
        "unk_b0c" / Int32ul,
        "unk_b10" / Int32ul,
        "pad_b14" / ZPadding(8),
        "unk_b1c" / Int32ul,
        "unk_b20" / Int32ul,
        "unk_b24" / Int32ul,
        "unk_b28" / Int32ul,
        "unk_b2c" / Int32ul,
        "unk_b30" / Int32ul,
        "unk_b34" / Int32ul,
        Ver("13.0 beta4", "unk_b38_0" / Int32ul),
        Ver("13.0 beta4", "unk_b38_4" / Int32ul),
        "unk_b38" / Array(6, Int64ul),
        "unk_b68" / Int32ul,
        Ver("13.0 beta4", "unk_b6c" / HexDump(Bytes(0xd0))),
        Ver("13.0 beta4", "unk_c3c" / Int32ul),
    )

    def __init__(self):
        # Userspace VA map related
        self.unk_0 = 0x13_00000000
        self.unk_8 = 0x14_00000000
        self.unk_10 = 0x1_00000000
        self.unk_18 = 0xffc00000
        self.unk_20 = 0x11_00000000
        self.unk_28 = 0x11_00000000
        # userspace address?
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
        if Ver.check("13.0 beta4"):
            self.yuv_matrices = [
                *self.yuv_matrices[:8],
                *(24 * [[[0,0,0,0]]*3]),
                *self.yuv_matrices[8:],
                *(24 * [[[0,0,0,0]]*3]),
            ]

        self.unk_450_0 = bytes(0x68)

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
        self.unk_504_0 = 0
        self.unk_504 = 0x31
        self.unk_508 = 0x0
        self.unk_50c = 0x0
        self.unk_510 = 0x0
        self.unk_514 = 0x0
        self.unk_518 = 0x0
        self.unk_51c = 0x0
        self.unk_520 = 0x0
        self.unk_524 = 0x1 # use_secure_cache_flush
        self.unk_528 = 0x0
        self.unk_52c = 0x0
        self.unk_530 = 0x0
        self.unk_534 = 0x0
        self.unk_538 = 0x0
        self.unk_53c_0 = 0
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
        self.max_pstate = 0x4
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
        if Ver.check("13.0 beta4"):
            self.unk_a84 = 0x24
        else:
            self.unk_a84 = 27
        self.unk_a88 = 73
        self.unk_a8c = 100

        self.min_volt = 850
        self.unk_ab8 = 72
        self.unk_abc = 8
        self.unk_ac0 = 0x1020
        self.unk_ac4_0 = bytes(0x1f0)
        self.unk_acc = 0x0
        self.unk_ad0 = 0x0
        if Ver.check("13.0 beta4"):
            self.unk_ae4 = [0x0, 0x3, 0x7, 0x7]
        else:
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
        self.unk_b34 = 0x0
        self.unk_b38_0 = 1
        self.unk_b38_4 = 1
        self.unk_b38 = [0xffffffffffffffff, 0xffffffffffffffff, 0xffffffffffffffff, 0xffffffffffffffff, 0xffffffffffffffff, 0xffffffffffffffff]
        self.unk_b68 = 0x0
        self.unk_b6c = bytes(0xd0)
        self.unk_c3c = 0x19

class InitData_BufferMgrCtl(ConstructValueClass):
    subcon = Array(126, Bytes(0x10))

    def __init__(self):
        self.value = [bytes(0x10)] * 126

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
        "unk_80" / HexDump(Bytes(0x40)),
        Ver("13.0 beta4", "unk_c0" / HexDump(Bytes(0x800))),
    )

    def __init__(self):
        self.unk_4 = 0
        self.queues = [InitData_GPUQueueStatsTA() for i in range(4)]
        self.unk_68 = bytes(0x8)
        self.unk_70 = 0
        self.unk_74 = 0
        self.unk_timestamp = 0
        self.unk_80 = bytes(0x40)
        self.unk_c0 = bytes(0x800)

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
        self.unk_14 = bytes(0x14)

class InitData_GPUStats3D(ConstructClass):
    subcon = Struct(
        "unk_0" / Bytes(0x18),
        "queues" / Array(4, InitData_GPUQueueStats3D),
        "unk_d0" / HexDump(Bytes(0x38)),
        "tvb_overflows_1" / Int32ul,
        "tvb_overflows_2" / Int32ul,
        "unk_f8" / Int32ul,
        "unk_fc" / Int32ul,
        "cur_stamp_id" / Int32sl,
        "unk_104" / Bytes(0x14),
        "unk_118" / Int32sl,
        "unk_11c" / Int32ul,
        "unk_120" / Int32ul,
        "unk_124" / Int32ul,
        "unk_128" / Int32ul,
        "unk_12c" / Int32ul,
        "unk_timestamp" / Int64ul,
        "unk_134" / Bytes(0x1c0 - 0x134),
        Ver("13.0 beta4", "unk_1c0" / HexDump(Bytes(0x800))),
    )

    def __init__(self):
        self.unk_0 = bytes(0x18)
        self.queues = [InitData_GPUQueueStats3D() for i in range(4)]
        self.unk_68 = 0
        self.cur_cmdqueue = 0
        self.unk_d0 = bytes(0x38)
        self.tvb_overflows_1 = 0
        self.tvb_overflows_2 = 0
        self.unk_f8 = 0
        self.unk_fc = 0
        self.cur_stamp_id = -1
        self.unk_104 = bytes(0x14)
        self.unk_118 = -1
        self.unk_11c = 0
        self.unk_120 = 0
        self.unk_124 = 0
        self.unk_128 = 0
        self.unk_12c = 0
        self.unk_timestamp = 0
        self.unk_134 = bytes(0x1c0 - 0x134)
        self.unk_1c0 = bytes(0x800)

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
        "pad_110" / ZPadding(0x50),
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
        "unk_1d0" / Int32ul,
        "unk_1d4" / Int32ul,
        "unk_1d8" / HexDump(Bytes(0x3c)),
        "buffer_mgr_ctl_addr" / Int64ul, # Size: 0x4000
        "buffer_mgr_ctl" / ROPointer(this.buffer_mgr_ctl_addr, InitData_BufferMgrCtl),
        "buffer_mgr_ctl_addr2" / Int64ul, # Size: 0x4000
        # Written to by DC_09
        "unk_224" / HexDump(Bytes(0x685c)),
        "unk_6a80" / Int32ul,
        "gpu_idle" / Int32ul,
        "unkpad_6a88" / HexDump(Bytes(0x14)),
        "unk_6a9c" / Int32ul,
        "unk_ctr0" / Int32ul,
        "unk_ctr1" / Int32ul,
        "unk_6aa8" / Int32ul,
        "unk_6aac" / Int32ul,
        "unk_ctr2" / Int32ul,
        "unk_6ab4" / Int32ul,
        "unk_6ab8" / Int32ul,
        "unk_6abc" / Int32ul,
        "unk_6ac0" / Int32ul,
        "unk_6ac4" / Int32ul,
        "unk_ctr3" / Int32ul,
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
        "unk_ctr4" / Int32ul,
        "unk_ctr5" / Int32ul,
        "unk_6afc" / Int32ul,
        "pad_6b00" / HexDump(Bytes(0x38)),
        "unk_6b38" / Int32ul,
        "pad_6b3c" / HexDump(Bytes(0x84)),
    )

    def __init__(self):
        super().__init__()
        self.unk_1d0 = 0
        self.unk_1d4 = 0
        self.unk_1d8 = bytes(0x3c)
        self.unk_224 = bytes(0x685c)
        self.unkpad_6a88 = bytes(0x14)
        self.pad_6b00 = bytes(0x38)
        self.unk_6b38 = 0xff
        self.pad_6b3c = bytes(0x84)

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

class InitData_PendingStamp(ConstructClass):
    subcon = Struct(
        "info" / Int32ul,
        "wait_value" / Int32ul,
    )

    def __init__(self):
        super().__init__()
        self.info = 0
        self.wait_value = 0

    def __bool__(self):
        return bool(self.info or self.wait_value)

class InitData_FaultInfo(ConstructClass):
    subcon = Struct(
        "unk_0" / Int32ul,
        "unk_4" / Int32ul,
        "queue_uuid" / Int32ul,
        "unk_c" / Int32ul,
        "unk_10" / Int32ul,
        "unk_14" / Int32ul,
    )

    def __init__(self):
        super().__init__()
        self.unk_0 = 0
        self.unk_4 = 0
        self.queue_uuid = 0
        self.unk_c = 0
        self.unk_10 = 0
        self.unk_14 = 0

class InitData_RegionC(ConstructClass):
    subcon = Struct(
        "ktrace_enable" / Int32ul,
        "unk_4" / HexDump(Bytes(0x24)),
        Ver("13.0 beta4", "unk_28_0" / Int32ul),
        "unk_28" / Int32ul,
        Ver("13.0 beta4", "unk_2c_0" / Int32ul),
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
        Ver("13.0 beta4", "unk_66_0" / HexDump(Bytes(0xc))),
        "unk_66" / Int32ul,
        "unk_6a" / HexDump(Bytes(0x16)),
        "unk_80" / HexDump(Bytes(0xf80)),
        "unk_1000" / HexDump(Bytes(0x7000)),
        "unk_8000" / HexDump(Bytes(0x900)),
        Ver("13.0 beta4", "unk_8900_0" / Int32ul),
        "unk_8900" / Int32ul,
        "unk_atomic" / Int32ul,
        "unk_8908" / Int32ul,
        "unk_890c" / Int32ul,
        "unk_8910" / Int32ul,
        "unk_8914" / Int32ul,
        "unk_8918" / Int32ul,
        "unk_891c" / Int32ul,
        "unk_8920" / Int32ul,
        "unk_8924" / Int32ul,
        "unk_8928" / Int32ul,
        "unk_892c" / Float32l,
        "unk_8930" / Float32l,
        "unk_8934" / Int32ul,
        "unk_8938" / Int32ul,
        "unk_893c" / Int32ul,
        "unk_8940" / Int32ul,
        "unk_8944" / Int32ul,
        "unk_8948" / Int32ul,
        "unk_894c" / Int32ul,
        "unk_8950" / HexDump(Bytes(0x6c)),
        Ver("13.0 beta4", "unk_89bc_0" / HexDump(Bytes(0x3c))),
        "unk_89bc" / Int32ul,
        "unk_89c0" / Int32ul,
        "unk_89c4" / Int32sl,
        "unk_89c8" / Int32ul,
        "unk_89cc" / Float32l,
        "unk_89d0" / Float32l,
        "unk_89d4" / HexDump(Bytes(0xc)),
        "unk_89e0" / Int32ul,
        "unk_89e4" / Int32ul,
        "unk_89e8" / Float32l,
        "unk_89ec" / Float32l,
        "unk_89f0" / Int32ul,
        Ver("13.0 beta4", "unk_89f4_0" / HexDump(Bytes(0x8))),
        Ver("13.0 beta4", "unk_89f4_8" / Int32ul),
        Ver("13.0 beta4", "unk_89f4_c" / HexDump(Bytes(0x50))),
        "hws1" / AGXHWDataShared1,
        "hws2" / AGXHWDataShared2,
        "unk_8fac" / HexDump(Bytes(0x60)),
        Ver("13.0 beta4", "unk_900c_0" / HexDump(Bytes(0x28))),
        "unk_900c" / Int32ul,
        Ver("13.0 beta4", "unk_9010_0" / Int32ul),
        Ver("13.0 beta4", "unk_9010_4" / HexDump(Bytes(0x14))),
        "unk_9010" / HexDump(Bytes(0x2c)),
        "unk_903c" / Int32ul,
        "unk_9040" / HexDump(Bytes(0xc0)),
        "unk_9100" / HexDump(Bytes(0x6f00)),
        "unk_10000" / HexDump(Bytes(0xe50)),
        "unk_10e50" / Int32ul,
        "unk_10e54" / HexDump(Bytes(0x2c)),
        "unk_10e80" / Int32ul,
        "do_init" / Int32ul,
        "unk_10e88" / HexDump(Bytes(0x188)),
        "idle_ts" / Int64ul,
        "idle_unk" / Int64ul,
        "unk_11020" / Int32ul,
        "unk_11024" / Int32ul,
        "unk_11028" / Int32ul,
        Ver("13.0 beta4", "unk_1102c_0" / Int32ul),
        Ver("13.0 beta4", "unk_1102c_4" / Int32ul),
        Ver("13.0 beta4", "unk_1102c_8" / Dec(Int32ul)),
        Ver("13.0 beta4", "unk_1102c_c" / Int32ul),
        Ver("13.0 beta4", "unk_1102c_10" / Int32ul),
        "unk_1102c" / Int32ul,
        "idle_to_off_timeout_ms" / Int32ul,
        "unk_11034" / Int32ul,
        "unk_11038" / Int32ul,
        "pending_stamps" / Array(0x110, InitData_PendingStamp),
        "unk_117bc" / Int32ul,
        "fault_info" / InitData_FaultInfo,
        "counter" / Int32ul,
        "unk_118dc" / Int32ul,
        Ver("13.0 beta4", "unk_118e0_0" / HexDump(Bytes(0x9c))),
        "unk_118e0" / Dec(Int32ul),
        Ver("13.0 beta4", "unk_118e4_0" / Dec(Int32ul)),
        "unk_118e4" / HexDump(Bytes(0x1c)),
        "unk_11900" / HexDump(Bytes(0x440)),
        Ver("13.0 beta4", "unk_11d40" / HexDump(Bytes(0x19c))),
        Ver("13.0 beta4", "unk_11edc" / Int32ul),
        Ver("13.0 beta4", "unk_11ee0" / HexDump(Bytes(0x1c))),
        Ver("13.0 beta4", "unk_11efc" / Int32ul),
    )

    def __init__(self):
        self.ktrace_enable = 0# 0xffffffff
        self.unk_4 = bytes(0x24)
        self.unk_28_0 = 1 # debug
        self.unk_28 = 1
        self.unk_2c_0 = 0
        self.unk_2c = 1
        if Ver.check("13.0 beta4"):
            self.unk_30 = 0
        else:
            self.unk_30 = 1
        self.unk_34 = 120
        self.unk_38 = bytes(0x1c)
        self.unk_54 = 0xffff
        self.unk_56 = 40
        self.unk_58 = 0xffff
        self.unk_5a = 0
        self.unk_5e = 1
        self.unk_62 = 0
        self.unk_66_0 = bytes(0xc)
        self.unk_66 = 1
        self.unk_6a = bytes(0x16)
        self.unk_80 = bytes(0xf80)
        self.unk_1000 = bytes(0x7000)
        self.unk_8000 = bytes(0x900)
        self.unk_8900_0 = 0
        self.unk_8900 = 1
        # Accessed with OSIncrementAtomic/OSDecrementAtomic
        self.unk_atomic = 0
        self.unk_8908 = 19551
        self.unk_890c = 600
        self.unk_8910 = 600
        self.unk_8914 = 0
        self.unk_8918 = 0
        self.unk_891c = 600
        self.unk_8920 = 0
        self.unk_8924 = 1
        # gpu-avg-power-target-filter-tc?
        self.unk_8928 = 125
        # gpu-avg-power-ki-only / gpu-avg-power-target-filter-tc?
        self.unk_892c = 0.06
        # gpu-avg-power-kp
        self.unk_8930 = 4.0
        # gpu-avg-power-min-duty-cycle
        self.unk_8934 = 40
        # gpu-avg-power-target-filter-tc
        self.unk_8938 = 125
        if Ver.check("13.0 beta4"):
            self.unk_893c = 30000
        else:
            self.unk_893c = 29520
        # gpu-power-zone-target-0 - gpu-power-zone-target-offset-0
        self.unk_8940 = 29900
        # gpu-power-zone-filter-tc-0
        self.unk_8944 = 6875
        self.unk_8948 = 0
        self.unk_894c = 0
        self.unk_8950 = bytes(0x6c)
        self.unk_89bc_0 = bytes(0x3c)
        self.unk_89bc = 9880
        self.unk_89c0 = 8000
        self.unk_89c4 = -220
        self.unk_89c8 = 0
        # gpu-fast-die0-proportional-gain?
        self.unk_89cc = 5.0
        self.unk_89d0 = 1.6
        self.unk_89d4 = bytes(0xc)
        self.unk_89e0 = 1
        self.unk_89e4 = 19551
        # gpu-ppm-kp
        self.unk_89e8 = 6.9
        # gpu-ppm-ki / gpu-avg-power-target-filter-tc?
        self.unk_89ec = 0.732
        self.unk_89f0 = 0
        self.unk_89f4_0 = bytes(8)
        self.unk_89f4_8 = 1
        self.unk_89f4_c = bytes(0x50)
        self.hws1 = AGXHWDataShared1()
        self.hws2 = AGXHWDataShared2()
        self.unk_8fac = bytes(0x60)
        self.unk_900c_0 = bytes(0x28)
        self.unk_900c = 1
        self.unk_9010_0 = 1
        self.unk_9010_4 = bytes(0x14)
        self.unk_9010 = bytes(0x2c)
        if Ver.check("13.0 beta4"):
            self.unk_903c = 1
        else:
            self.unk_903c = 0
        self.unk_9040 = bytes(0xc0)
        self.unk_9100 = bytes(0x6f00)
        self.unk_10000 = bytes(0xe50)
        self.unk_10e50 = 0
        self.unk_10e54 = bytes(0x2c)
        self.unk_10e80_0 = bytes(0xed4)
        self.unk_10e80_ed0 = 0
        self.unk_10e80_ed4 = bytes(0x2c)
        self.unk_10e80 = 11
        self.do_init = 1
        self.unk_10e88 = bytes(0x188)
        self.idle_ts = 0
        self.idle_unk = 0
        self.unk_11020 = 40
        self.unk_11024 = 10
        self.unk_11028 = 250
        self.unk_1102c_0 = 1
        self.unk_1102c_4 = 1
        self.unk_1102c_8 = 100
        self.unk_1102c_c = 1
        self.unk_1102c_10 = 0
        self.unk_1102c = 0
        self.idle_to_off_timeout_ms = 2
        self.unk_11034 = 40
        self.unk_11038 = 5
        self.pending_stamps = [InitData_PendingStamp() for i in range(0x110)]
        self.unk_117bc = 0
        self.fault_info = InitData_FaultInfo()
        self.counter = 0
        self.unk_118dc = 0
        self.unk_118e0_0 = bytes(0x9c)
        self.unk_118e0 = 40
        self.unk_118e4_0 = 50
        self.unk_118e4 = bytes(0x1c)
        self.unk_11900 = bytes(0x440)

        self.unk_11d40 = bytes(0x19c)
        self.unk_11edc = 8
        self.unk_11ee0 = bytes(0x1c)
        self.unk_11efc = 8

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
        Ver("13.0 beta4", "ver_info" / Array(4, Int16ul)),
        "regionA_addr" / Int64ul, # allocation size: 0x4000
        "regionA" / ROPointer(this.regionA_addr, HexDump(Bytes(0x4000))),
        "unk_8" / Default(Int32ul, 0),
        "unk_c"/ Default(Int32ul, 0),
        "regionB_addr" / Int64ul, # 0xfa00c338000 allocation size: 0x6bc0
        "regionB" / ROPointer(this.regionB_addr, InitData_RegionB),
        "regionC_addr" / Int64ul, # 0xfa000200000 allocation size: 0x11d40, heap?
        "regionC" / ROPointer(this.regionC_addr, InitData_RegionC),
        "fw_status_addr" / Int64ul, # allocation size: 0x4000, but probably only 0x80 bytes long
        "fw_status" / ROPointer(this.fw_status_addr, InitData_FWStatus),
        "uat_page_size" / Int16ul,
        "uat_page_bits" / Int8ul,
        "uat_num_levels" / Int8ul,
        "uat_level_info" / Array(3, UatLevelInfo),
        "pad_8c" / HexDump(Default(Bytes(0x14), bytes(0x14))),
        "host_mapped_fw_allocations" / Int32ul, # must be 1
        "unk_ac" / Int32ul,
        "unk_b0" / Int32ul,
        "unk_b4" / Int32ul,
        "unk_b8" / Int32ul,
    )

    def __init__(self):
        super().__init__()
        self.unk_ac = 0
        self.unk_b0 = 0
        self.unk_b4 = 0
        self.unk_b8 = 0

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)

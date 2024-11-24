# SPDX-License-Identifier: MIT
from ..fw.agx.initdata import *
from ..fw.agx.channels import ChannelInfo
from ..hw.uat import MemoryAttr

from construct import Container
from m1n1.constructutils import Ver

def build_iomappings(agx, chip_id):
    def iomap(phys, size, range_size, rw):
        off = phys & 0x3fff
        virt = agx.io_allocator.malloc(size + 0x4000 + off)
        agx.uat.iomap_at(0, virt, phys - off, size + off, AttrIndex=MemoryAttr.Device)
        return IOMapping(phys, virt + off, size, range_size, rw)

    # for t8103
    if chip_id == 0x8103:
        return [
            iomap(0x204d00000, 0x1c000, 0x1c000, 1), # Fender
            iomap(0x20e100000, 0x4000, 0x4000, 0), # AICTimer
            iomap(0x23b104000, 0x4000, 0x4000, 1), # AICSWInt
            iomap(0x204000000, 0x20000, 0x20000, 1), # RGX
            IOMapping(), # UVD
            IOMapping(), # unused
            IOMapping(), # DisplayUnderrunWA
            iomap(0x23b2e8000, 0x1000, 0x1000, 0), # AnalogTempSensorControllerRegs
            iomap(0x23bc00000, 0x1000, 0x1000, 1), # PMPDoorbell
            iomap(0x204d80000, 0x5000, 0x5000, 1), # MetrologySensorRegs
            iomap(0x204d61000, 0x1000, 0x1000, 1), # GMGIFAFRegs
            iomap(0x200000000, 0xd6400, 0xd6400, 1), # MCache registers
            IOMapping(), # AICBankedRegisters
            iomap(0x23b738000, 0x1000, 0x1000, 1), # PMGRScratch
            IOMapping(), # NIA Special agent idle register die 0
            IOMapping(), # NIA Special agent idle register die 1
            IOMapping(), # CRE registers
            IOMapping(), # Streaming codec registers
            IOMapping(), #
            IOMapping(), #
            IOMapping(),
            IOMapping(),
            IOMapping(),
            IOMapping(),
            IOMapping(),
        ]
    elif chip_id == 0x8112:
        return [
            iomap(0x204d00000, 0x14000, 0x14000, 1), # Fender
            iomap(0x20e100000, 0x4000, 0x4000, 0), # AICTimer
            iomap(0x23b0c4000, 0x4000, 0x4000, 1), # AICSWInt
            iomap(0x204000000, 0x20000, 0x20000, 1), # RGX
            IOMapping(), # UVD
            IOMapping(), # unused
            IOMapping(), # DisplayUnderrunWA
            iomap(0x23b2c0000, 0x1000, 0x1000, 0), # AnalogTempSensorControllerRegs
            IOMapping(), # PMPDoorbell
            iomap(0x204d80000, 0x8000, 0x8000, 1), # MetrologySensorRegs
            iomap(0x204d61000, 0x1000, 0x1000, 1), # GMGIFAFRegs
            iomap(0x200000000, 0xd6400, 0xd6400, 1), # MCache registers
            IOMapping(), # AICBankedRegisters
            IOMapping(), # PMGRScratch
            IOMapping(), # NIA Special agent idle register die 0
            IOMapping(), # NIA Special agent idle register die 1
            iomap(0x204e00000, 0x10000, 0x10000, 0), # CRE registers
            iomap(0x27d050000, 0x4000, 0x4000, 0), # Streaming codec registers
            iomap(0x23b3d0000, 0x1000, 0x1000, 0), #
            iomap(0x23b3c0000, 0x1000, 0x1000, 0), #
            IOMapping(),
            IOMapping(),
            IOMapping(),
            IOMapping(),
            IOMapping(),
        ]
    elif chip_id in (0x6000, 0x6001, 0x6002):
        mcc_cnt = {0x6002: 16, 0x6001: 8, 0x6000: 4}
        return [
            iomap(0x404d00000, 0x1c000, 0x1c000, 1), # Fender
            iomap(0x20e100000, 0x4000, 0x4000, 0), # AICTimer
            iomap(0x28e104000, 0x4000, 0x4000, 1), # AICSWInt
            iomap(0x404000000, 0x20000, 0x20000, 1), # RGX
            IOMapping(), # UVD
            IOMapping(), # unused
            IOMapping(), # DisplayUnderrunWA
            iomap(0x28e494000, 0x1000, 0x1000, 0), # AnalogTempSensorControllerRegs
            IOMapping(), # PMPDoorbell
            iomap(0x404d80000, 0x8000, 0x8000, 1), # MetrologySensorRegs
            iomap(0x204d61000, 0x1000, 0x1000, 1), # GMGIFAFRegs
            iomap(0x200000000, mcc_cnt[chip_id] * 0xd8000, 0xd8000, 1), # MCache registers
            IOMapping(), # AICBankedRegisters
            IOMapping(), # PMGRScratch
            iomap(0x2643c4000, 0x1000, 0x1000, 1), # NIA Special agent idle register die 0
            iomap(0x22643c4000, 0x1000, 0x1000, 1) if chip_id == 0x6002 else IOMapping(), # NIA Special agent idle register die 1
            IOMapping(), # CRE registers
            IOMapping(), # Streaming codec registers
            iomap(0x28e3d0000, 0x1000, 0x1000, 1),
            iomap(0x28e3c0000, 0x2000, 0x2000, 0),
        ]
    elif chip_id in (0x6020, 0x6021, 0x6022):
        mcc_cnt = {0x6022: 16, 0x6021: 8, 0x6020: 4}
        return [
            iomap(0x404d00000, 0x144000, 0x144000, 1), # Fender
            iomap(0x20e100000, 0x4000, 0x4000, 0), # AICTimer
            iomap(0x28e106000, 0x4000, 0x4000, 1), # AICSWInt
            iomap(0x404000000, 0x20000, 0x20000, 1), # RGX
            IOMapping(), # UVD
            IOMapping(), # unused
            IOMapping(), # DisplayUnderrunWA
            iomap(0x28e478000, 0x4000, 0x4000, 0), # AnalogTempSensorControllerRegs
            IOMapping(), # PMPDoorbell
            iomap(0x404e08000, 0x8000, 0x8000, 1), # MetrologySensorRegs
            IOMapping(), # GMGIFAFRegs
            iomap(0x200000000, mcc_cnt[chip_id] * 0xd8000, 0xd8000, 1), # MCache registers
            iomap(0x28e118000, 0x4000, 0x4000, 0), # AICBankedRegisters
            IOMapping(), # PMGRScratch
            IOMapping(), # NIA Special agent idle register die 0
            IOMapping(), # NIA Special agent idle register die 1
            IOMapping(), # CRE registers
            IOMapping(), # Streaming codec registers
            iomap(0x28e3d0000, 0x4000, 0x4000, 1),
            iomap(0x28e3c0000, 0x4000, 0x4000, 0),
            iomap(0x28e3d8000, 0x4000, 0x4000, 1),
            iomap(0x404eac000, 0x4000, 0x4000, 1),
            IOMapping(),
            IOMapping(),
            IOMapping(),
        ]

CHIP_INFO = {
    0x8103: Container(
        chip_id = 0x8103,
        min_sram_volt = 850,
        max_power = 19551,
        max_freq_mhz = 1278,
        unk_87c = -220,
        unk_8cc = 9880,
        unk_924 = [[0] * 8] * 8,
        unk_e48 = [[0] * 8] * 8,
        unk_e24 = 112,
        gpu_fast_die0_sensor_mask64 = 0x12,
        gpu_fast_die1_sensor_mask64 = 0,
        gpu_fast_die0_sensor_mask64_alt = 0x12,
        gpu_fast_die1_sensor_mask64_alt = 0,
        gpu_fast_die0_sensor_present = 0x01,
        shared1_tab = [
            -1, 0x7282, 0x50ea, 0x370a, 0x25be, 0x1c1f, 0x16fb
        ] + ([-1] * 9),
        shared1_a4 = 0xffff,
        shared2_tab = [0x800, 0x1555, -1, -1, -1, -1, -1, -1, 0, 0],
        shared2_unk_508 = 0xc00007,
        unk_3cf4 = [1000.0, 0, 0, 0, 0, 0, 0, 0],
        unk_3d14 = [45.0, 0, 0, 0, 0, 0, 0, 0],
        unk_3d34_0 = [0, 0, 0, 0, 0, 0, 0, 0],
        unk_118ec = None,
        hwdb_4e0 = 0,
        hwdb_534 = 0,
        num_cores = 8,
        gpu_core = 11,
        gpu_rev = 4,
        hwdb_ab8 = 0x48,
        hwdb_abc = 0x8,
        hwdb_b30 = 0,
        rel_max_powers = [0, 19, 26, 38, 60, 87, 100],
        shared2_t1_coef = None,
        shared3_tab = [0] * 16,
        shared3_unk = 0,
        sram_base = 0,
        sram_size = 0,
        rc_unk_54 = 0xffff,
        unk_hws2_0 = 0,
        unk_hws2_4 = [0] * 8,
        unk_hws2_24 = 0,
        tiling_control = 0xa041,
    ),
    0x6001: Container(
        chip_id = 0x6001,
        min_sram_volt = 790,
        max_power = 81415,
        max_freq_mhz = 1296,
        unk_87c = 900,
        unk_8cc = 11000,
        unk_924 = [[i, *([0] * 7)] for i in [
            9.838, 9.819, 9.826, 9.799,
            0, 0, 0, 0,
        ]],
        unk_e48 = [[i, *([0] * 7)] for i in [
            13, 13, 13, 13, 0, 0, 0, 0,
        ]],
        unk_e24 = 125,
        gpu_fast_die0_sensor_mask64 = 0x80808080,
        gpu_fast_die1_sensor_mask64 = 0,
        gpu_fast_die0_sensor_mask64_alt = 0x90909090,
        gpu_fast_die1_sensor_mask64_alt = 0,
        gpu_fast_die0_sensor_present = 0x0f,
        shared1_tab = [0xffff] * 16,
        shared1_a4 = 0xffff,
        shared2_tab = [-1, -1, -1, -1, 0x2aa, 0xaaa, -1, -1, 0, 0],
        shared2_unk_508 = 0xcc00001,
        unk_3cf4 = [1314.0, 1330.0, 1314.0, 1288.0, 0, 0, 0, 0],
        unk_3d14 = [21.0, 21.0, 22.0, 21.0, 0, 0, 0, 0],
        unk_3d34_0 = [0, 0, 0, 0, 0, 0, 0, 0],
        unk_118ec = [
            0, 1, 2,
            1, 1, 90, 75, 1, 1,
            1, 2, 90, 75, 1, 1,
            1, 1, 90, 75, 1, 1
        ],
        hwdb_4e0 = 4,
        hwdb_534 = 1,
        num_cores = 32,
        gpu_core = 13,
        gpu_rev = 5,
        hwdb_ab8 = 0x2084,
        hwdb_abc = 0x80,
        hwdb_b30 = 0,
        rel_max_powers = [0, 15, 20, 27, 36, 52, 100],
        shared2_t1_coef = None,
        shared3_tab = [0] * 16,
        shared3_unk = 0,
        sram_base = 0,
        sram_size = 0,
        rc_unk_54 = 0xffff,
        unk_hws2_0 = 0,
        unk_hws2_4 = [0] * 8,
        unk_hws2_24 = 0,
        tiling_control = 0xa540,
    ),
    0x6002: Container(
        chip_id = 0x6002,
        min_sram_volt = 790,
        max_power = 166743,
        max_freq_mhz = 1296,
        unk_87c = 900,
        unk_8cc = 11000,
        unk_924 = [[i, *([0] * 7)] for i in [
            9.838, 9.819, 9.826, 9.799,
            9.799, 9.826, 9.819, 9.838,
        ]],
        unk_c30 = 0,
        unk_e48 = [[i, *([0] * 7)] for i in [
            13, 13, 13, 13, 13, 13, 13, 13,
        ]],
        unk_e24 = 125,
        gpu_fast_die0_sensor_mask64 = 0x8080808080808080,
        gpu_fast_die1_sensor_mask64 = 0,
        gpu_fast_die0_sensor_mask64_alt = 0x9090909090909090,
        gpu_fast_die1_sensor_mask64_alt = 0,
        gpu_fast_die0_sensor_present = 0xff,
        shared1_tab = [0xffff] * 16,
        shared1_a4 = 0xffff,
        shared2_tab = [-1, -1, -1, -1, 0x2aa, 0xaaa, -1, -1, 0, 0],
        shared2_unk_508 = 0xcc00001,
        unk_3cf4 = [1244.0, 1260.0, 1242.0, 1214.0,
                    1072.0, 1066.0, 1044.0, 1042.0],
        unk_3d14 = [18.0, 18.0, 18.0, 17.0, 15.0, 15.0, 15.0, 14.0],
        unk_3d34_0 = [0, 0, 0, 0, 0, 0, 0, 0],
        unk_8924 = 0,
        unk_118ec = [
            0, 1, 2,
            1, 1, 90, 75, 1, 1,
            1, 2, 90, 75, 1, 1,
            1, 1, 90, 75, 1, 1
        ],
        hwdb_4e0 = 4,
        hwdb_534 = 1,
        num_cores = 64,
        gpu_core = 13,
        gpu_rev = 5,
        hwdb_ab8 = 0x2084,
        hwdb_abc = 0x80,
        hwdb_b30 = 0,
        rel_max_powers = [0, 15, 19, 25, 34, 50, 100],
        shared2_t1_coef = None,
        shared3_tab = [0] * 16,
        shared3_unk = 0,
        sram_base = 0,
        sram_size = 0,
        rc_unk_54 = 0xffff,
        unk_hws2_0 = 0,
        unk_hws2_4 = [0] * 8,
        unk_hws2_24 = 0,
        tiling_control = 0xa540,
    ),
    0x8112: Container(
        chip_id = 0x8112,
        min_sram_volt = 780,
        max_power = 22800,
        max_freq_mhz = 1398,
        unk_87c = 900,
        unk_8cc = 11000,
        unk_924 = [[
            0.0, 0.0, 0.0, 0.0,
            5.3, 0.0, 5.3, 5.3,
        ]] + ([[0] * 8] * 7),
        unk_e48 = [[
            0.0, 0.0, 0.0, 0.0,
            5.3, 0.0, 5.3, 5.3,
        ]] + ([[0] * 8] * 7),
        unk_e24 = 125,
        gpu_fast_die0_sensor_mask64 = 0x6800,
        gpu_fast_die1_sensor_mask64 = 0,
        gpu_fast_die0_sensor_mask64_alt = 0x6800,
        gpu_fast_die1_sensor_mask64_alt = 0,
        gpu_fast_die0_sensor_present = 0x02,
        shared1_tab = [0xffff] * 16,
        shared1_a4 = 0,
        shared2_tab = [-1, -1, -1, -1, -1, -1, -1, -1, 0xaa5aa, 0],
        shared2_unk_508 = 0xc00000,
        unk_3cf4 = [1920.0, 0, 0, 0, 0, 0, 0, 0],
        unk_3d14 = [74.0, 0, 0, 0, 0, 0, 0, 0],
        unk_3d34_0 = [0, 0, 0, 0, 0, 0, 0, 0],
        unk_118ec = None,
        hwdb_4e0 = 4,
        hwdb_534 = 0,
        num_cores = 10,
        gpu_core = 15,
        gpu_rev = 3,
        hwdb_ab8 = 0x2048,
        hwdb_abc = 0x4000,
        hwdb_b30 = 1,
        rel_max_powers = [0, 18, 27, 37, 52, 66, 82, 96, 100],
        shared2_t1_coef = 7200,
        shared2_t2 = [0xf07, 0x4c0, 0x6c0, 0x8c0, 0xac0, 0xc40, 0xdc0, 0xec0, 0xf80],
        shared2_t3_coefs = [None, 20.0, 28.0, 36.0, 44.0, 50.0, 56.0, 60.0, 63.0],
        shared2_t3_scales = [9, 3209, 10400],
        unk_hws2_0 = 0,
        unk_hws2_4 = [0] * 8,
        unk_hws2_24 = 0,
        sram_base = 0,
        sram_size = 0,
        shared3_unk = 5,
        shared3_tab = [
            10700, 10700, 10700, 10700,
            10700, 6000, 1000, 1000,
            1000, 10700, 10700, 10700,
            10700, 10700, 10700, 10700,
        ],
        rc_unk_54 = 0xffff,
        tiling_control = 0xa041,
    ),
    0x6021: Container(
        chip_id = 0x6021,
        min_sram_volt = 790,
        max_power = 95892,
        max_freq_mhz = 1398,
        unk_87c = 500,
        unk_8cc = 11000,
        unk_924 = [
            [0.0, 8.2, 0.0, 6.9, 6.9] + [0] * 11,
            [0.0, 0.0, 0.0, 6.9, 6.9] + [0] * 11,
            [0.0, 8.2, 0.0, 6.9, 0.0] + [0] * 11,
            [0.0, 0.0, 0.0, 6.9, 0.0] + [0] * 11,
        ] + ([[0] * 16] * 4),
        unk_e48 = [
            [0.0, 9.0, 0.0, 8.0, 8.0] + [0] * 11,
            [0.0, 0.0, 0.0, 8.0, 8.0] + [0] * 11,
            [0.0, 9.0, 0.0, 8.0, 0.0] + [0] * 11,
            [0.0, 0.0, 0.0, 8.0, 0.0] + [0] * 11,
        ] + ([[0] * 16] * 4),
        unk_e24 = 125,
        gpu_fast_die0_sensor_mask64 = 0x40005000c000d00,
        gpu_fast_die1_sensor_mask64 = 0,
        gpu_fast_die0_sensor_mask64_alt = 0x140015001d001d00,
        gpu_fast_die1_sensor_mask64_alt = 0,
        gpu_fast_die0_sensor_present = None,
        shared1_tab = [0xffff] * 16,
        shared1_a4 = 0,
        shared2_tab = [0x800, 0x1555, -1, -1, -1, -1, -1, -1, 0xaaaaa, 0],
        shared2_unk_508 = 0xc00007,
        unk_3cf4 = [1564.0, 1416.0, 1428.0, 1614.0, 0, 0, 0, 0],
        unk_3d14 = [42.0, 39.0, 39.0, 44.0, 0, 0, 0, 0],
        unk_3d34_0 = [547.0, 0.0, 293.0, 0.0, 547.0, 0.0, 293.0, 0.0],
        unk_118ec = [
            0, 2, 2,
            1, 1, 90, 75, 1, 1,
            1, 2, 90, 75, 1, 1,
            1, 2, 90, 75, 1, 1,
            1, 1, 90, 75, 1, 1,
        ],
        hwdb_4e0 = 4,
        hwdb_534 = 0,
        num_cores = 40,
        gpu_core = 17,
        gpu_rev = 3,
        hwdb_ab8 = None,
        hwdb_abc = None,
        hwdb_b30 = 0,
        rel_max_powers = [0, 19, 26, 36, 48, 63, 79, 91, 100],
        shared2_t1_coef = 11000,
        shared2_t2 = [0xf07, 0x4c0, 0x680, 0x8c0, 0xa80, 0xc40, 0xd80, 0xec0, 0xf40],
        shared2_t3_coefs = [None, 20.0, 27.0, 36.0, 43.0, 50.0, 55.0, 60.0, 62.0],
        shared2_t3_scales = [9, 3209, 10400],
        unk_hws2_0 = 700,
        unk_hws2_4 = [1.0, 0.8, 0.2, 0.9, 0.1, 0.25, 0.7, 0.9],
        unk_hws2_24 = 6,
        sram_base = 0x404d60000,
        sram_size = 0x20000,
        shared3_unk = 8,
        shared3_tab = [
            125, 125, 125, 125, 125, 125, 125, 125,
            7500, 125, 125, 125, 125, 125, 125, 125
        ],
        rc_unk_54 = 4000,
        tiling_control = 0x180340,
    ),
    0x6020: Container(
        chip_id = 0x6020,
        min_sram_volt = 790,
        max_power = 95892,
        max_freq_mhz = 1398,
        unk_87c = 500,
        unk_8cc = 11000,
        unk_924 = [
            [0.0, 8.2, 0.0, 6.9, 6.9] + [0] * 11,
            [0.0, 0.0, 0.0, 6.9, 6.9] + [0] * 11,
            [0.0, 8.2, 0.0, 6.9, 0.0] + [0] * 11,
            [0.0, 0.0, 0.0, 6.9, 0.0] + [0] * 11,
        ] + ([[0] * 16] * 4),
        unk_e48 = [
            [0.0, 9.0, 0.0, 8.0, 8.0] + [0] * 11,
            [0.0, 0.0, 0.0, 8.0, 8.0] + [0] * 11,
            [0.0, 9.0, 0.0, 8.0, 0.0] + [0] * 11,
            [0.0, 0.0, 0.0, 8.0, 0.0] + [0] * 11,
        ] + ([[0] * 16] * 4),
        unk_e24 = 125,
        gpu_fast_die0_sensor_mask64 = 0xc000d00,
        gpu_fast_die1_sensor_mask64 = 0,
        gpu_fast_die0_sensor_mask64_alt = 0x1d001d00,
        gpu_fast_die1_sensor_mask64_alt = 0,
        gpu_fast_die0_sensor_present = None,
        shared1_tab = [0xffff] * 16,
        shared1_a4 = 0,
        shared2_tab = [0x800, 0x1555, -1, -1, -1, -1, -1, -1, 0xaaaaa, 0],
        shared2_unk_508 = 0xc00007,
        unk_3cf4 = [1564.0, 1416.0, 1428.0, 1614.0, 0, 0, 0, 0],
        unk_3d14 = [42.0, 39.0, 39.0, 44.0, 0, 0, 0, 0],
        unk_3d34_0 = [547.0, 0.0, 293.0, 0.0, 547.0, 0.0, 293.0, 0.0],
        unk_118ec = [
            0, 2, 2,
            1, 1, 90, 75, 1, 1,
            1, 2, 90, 75, 1, 1,
            1, 2, 90, 75, 1, 1,
            1, 1, 90, 75, 1, 1,
        ],
        hwdb_4e0 = 4,
        hwdb_534 = 0,
        num_cores = 20,
        gpu_core = 16,
        gpu_rev = 3,
        hwdb_ab8 = None,
        hwdb_abc = None,
        hwdb_b30 = 0,
        rel_max_powers = [0, 19, 26, 36, 48, 63, 79, 91, 100],
        shared2_t1_coef = 11000,
        shared2_t2 = [0xf07, 0x4c0, 0x680, 0x8c0, 0xa80, 0xc40, 0xd80, 0xec0, 0xf40],
        shared2_t3_coefs = [None, 20.0, 27.0, 36.0, 43.0, 50.0, 55.0, 60.0, 62.0],
        shared2_t3_scales = [9, 3209, 10400],
        unk_hws2_0 = 700,
        unk_hws2_4 = [1.0, 0.8, 0.2, 0.9, 0.1, 0.25, 0.7, 0.9],
        unk_hws2_24 = 6,
        sram_base = 0x404d60000,
        sram_size = 0x20000,
        shared3_unk = 8,
        shared3_tab = [
            125, 125, 125, 125, 125, 125, 125, 125,
            7500, 125, 125, 125, 125, 125, 125, 125
        ],
        rc_unk_54 = 4000,
        tiling_control = 0x180340,
    ),
}
def build_initdata(agx):
    sgx = agx.u.adt["/arm-io/sgx"]
    chosen = agx.u.adt["/chosen"]
    chip_info = CHIP_INFO[chosen.chip_id]
    agx.chip_info = chip_info

    initdata = agx.kshared.new(InitData)

    if Ver.check("V >= V13_3 && G == G14X"):
        initdata.ver_info = (0xb390, 0x70f8, 0x601, 0xb0)
    elif Ver.check("V >= V13_3 && G != G14X"):
        initdata.ver_info = (0x6ba0, 0x1f28, 0x601, 0xb0)

    initdata.regionA = agx.kshared.new_buf(0x4000, "InitData_RegionA").push()

    regionB = agx.kobj.new(InitData_RegionB)

    regionB.channels = agx.ch_info

    regionB.stats_ta = agx.kobj.new(InitData_GPUGlobalStatsTA).push()
    regionB.stats_3d = agx.kobj.new(InitData_GPUGlobalStats3D).push()

    # size: 0x180, Empty
    # 13.0: grew
    # 13.3: grew again
    #regionB.stats_cp = agx.kobj.new_buf(0x180, "RegionB.unkptr_180").push()
    regionB.stats_cp = agx.kobj.new_buf(0x980 + 0x800, "RegionB.stats_cp").push()

    # size: 0x3b80, few floats, few ints, needed for init
    regionB.hwdata_a = agx.kobj.new(AGXHWDataA(sgx, chip_info), track=False)

    # size: 0x80, empty
    regionB.fault_info = agx.kshared.new(AGXFaultInfo).push()

    # size: 0xc0, fw writes timestamps into this
    regionB.unk_198 = agx.kobj.new_buf(0xc0, "RegionB.unkptr_198").push()

    # size: 0xb80, io stuff
    hwdata = agx.kobj.new(AGXHWDataB(sgx, chip_info), track=False)
    hwdata.timestamp_region_base = agx.ktimestamp.start
    hwdata.io_mappings = build_iomappings(agx, chosen.chip_id)

    if chip_info.sram_base:
        virt = agx.io_allocator.malloc(chip_info.sram_size)
        hwdata.sgx_sram_ptr = virt
        agx.uat.iomap_at(0, virt, chip_info.sram_base, chip_info.sram_size,
                         AttrIndex=MemoryAttr.Shared)
    else:
        hwdata.sgx_sram_ptr = 0

    k = 1.02 #?
    count = sgx.perf_state_count
    table_count = sgx.perf_state_table_count
    base_pstate = sgx.getprop("gpu-perf-base-pstate", 3)
    base_freq = sgx.perf_states[base_pstate].freq
    max_freq = sgx.perf_states[count - 1].freq
    for i in range(count):
        ps = sgx.perf_states[i]
        hwdata.frequencies[i] = ps.freq // 1000000

        volt = [ps.volt] * 8
        for j in range(1, table_count):
            volt[j] = sgx.perf_states[count * j + i].volt
        sram_volt = [max(chip_info.min_sram_volt, i) for i in volt]

        hwdata.voltages[i] = volt
        hwdata.voltages_sram[i] = sram_volt

        regionB.hwdata_a.unk_74[i] = k
        hwdata.unk_9b4[i] = k
        hwdata.rel_max_powers[i] = chip_info.rel_max_powers[i]
        hwdata.rel_boost_freqs[i] = max(0, int((ps.freq - base_freq) / (max_freq - base_freq) * 100))

    cs_pstates = sgx.getprop("cs-perf-states", None)
    if cs_pstates:
        hwdata.cs_max_pstate = cs_pstates.count - 1
        hwdata.cs_frequencies = [(ps.freq // 1000000)
                                 for ps in cs_pstates.states[0]] + [0] * (16 - cs_pstates.count)
        hwdata.cs_voltages = [[(ps.volt // 1000), 0]
                              for ps in cs_pstates.states[0]] + [[0, 0]] * (16 - cs_pstates.count)
        hwdata.cs_voltages_sram = [[max(i[0], cs_pstates.min_sram_volt[0] // 1000) if i[0] else 0, 0] for i in hwdata.cs_voltages]
    else:
        hwdata.cs_max_pstate = 0
        hwdata.cs_frequencies = [0] * 16
        hwdata.cs_voltages = [[0, 0]] * 16
        hwdata.cs_voltages_sram = [[0, 0]] * 16

    afr_pstates = sgx.getprop("afr-perf-states", None)
    if afr_pstates:
        hwdata.afr_max_pstate = afr_pstates.count - 1
        hwdata.afr_frequencies = [(ps.freq // 1000000)
                                 for ps in afr_pstates.states[0]] + [0] * (8 - afr_pstates.count)
        hwdata.afr_voltages = [[(ps.volt // 1000), 0]
                              for ps in afr_pstates.states[0]] + [[0, 0]] * (8 - afr_pstates.count)
        hwdata.afr_voltages_sram = [[max(i[0], afr_pstates.min_sram_volt[0] // 1000) if i[0] else 0, 0] for i in hwdata.afr_voltages]
    else:
        hwdata.afr_max_pstate = 0
        hwdata.afr_frequencies = [0] * 8
        hwdata.afr_voltages = [[0, 0]] * 8
        hwdata.afr_voltages_sram = [[0, 0]] * 8

    regionB.hwdata_a.push()

    regionB.hwdata_b = hwdata.push()
    regionB.hwdata_b_addr2 = hwdata._addr

    regionB.fwlog_ring2 = agx.fwlog_ring

    # Unallocated, Size 0x1000
    regionB.unk_1b8 = agx.kobj.new_buf(0x1000, "RegionB.unkptr_1b8").push()

    # Unallocated, size 0x300
    regionB.unk_1c0 = agx.kobj.new_buf(0x300, "RegionB.unkptr_1c0").push()

    # Unallocated, unknown size
    regionB.unk_1c8 = agx.kobj.new_buf(0x1000, "RegionB.unkptr_1c8").push()

    # Size: 0x4000
    regionB.buffer_mgr_ctl = agx.kshared.new(InitData_BufferMgrCtl, track=True).push()

    agx.uat.iomap_at(0, 0x420000000, regionB.buffer_mgr_ctl._paddr_align, 0x4000,
                     AttrIndex=MemoryAttr.Shared, AP=0, UXN=1, PXN=1)

    regionB.buffer_mgr_ctl_gpu_addr = 0x420000000 + (regionB.buffer_mgr_ctl._addr & 0x3fff)

    regionB.unk_6a80 = 0
    regionB.gpu_idle = 0
    regionB.unk_6a9c = 0
    regionB.unk_ctr0 = 0
    regionB.unk_ctr1 = 0
    regionB.unk_6aa8 = 0
    regionB.unk_6aac = 0
    regionB.unk_ctr2 = 0
    regionB.unk_6ab4 = 0
    regionB.unk_6ab8 = 0
    regionB.unk_6abc = 0
    regionB.unk_6ac0 = 0
    regionB.unk_6ac4 = 0
    regionB.unk_ctr3 = 0
    regionB.unk_6acc = 0
    regionB.unk_6ad0 = 0
    regionB.unk_6ad4 = 0
    regionB.unk_6ad8 = 0
    regionB.unk_6adc = 0
    regionB.unk_6ae0 = 0
    regionB.unk_6ae4 = 0
    regionB.unk_6ae8 = 0
    regionB.unk_6aec = 0
    regionB.unk_6af0 = 0
    regionB.unk_ctr4 = 0
    regionB.unk_ctr5 = 0
    regionB.unk_6afc = 0

    initdata.regionB = regionB.push()

    initdata.regionC = agx.kshared.new(InitData_RegionC(sgx, chip_info), track=False).push()

    #self.regionC_addr = agx.ksharedshared_heap.malloc(0x88000)

    initdata.fw_status = agx.kobj.new(InitData_FWStatus)
    initdata.fw_status.fwctl_channel = agx.fwctl_chinfo
    initdata.fw_status.push()

    ## This section seems to be data that would be used by firmware side page allocation
    ## But the current firmware doesn't have this functionality enabled, so it's not used?
    initdata.uat_num_levels = 3
    initdata.uat_page_bits = 14
    initdata.uat_page_size = 0x4000

    if chip_info.chip_id in (0x8103, 0x8112):
        phys_mask = 0xffffffc000
    else:
        phys_mask = 0x3ffffffc000

    initdata.uat_level_info = [
        UatLevelInfo(36, 8, phys_mask),
        UatLevelInfo(25, 2048, phys_mask),
        UatLevelInfo(14, 2048, phys_mask),
    ]

    # Host handles FW allocations for existing firmware versions
    initdata.host_mapped_fw_allocations = 1


    #initdata.regionC.idle_ts = agx.u.mrs("CNTPCT_EL0") + 24000000
    #initdata.regionC.idle_unk = 0x5b2e8
    #initdata.regionC.idle_to_off_timeout_ms = 20000

    initdata.regionC.push()
    initdata.push()

    #print(InitData.parse_stream(agx.uat.iostream(0, initdata._addr)))
    return initdata

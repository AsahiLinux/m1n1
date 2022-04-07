# SPDX-License-Identifier: MIT
from ..utils import *
from collections import namedtuple
from enum import IntEnum


EncodeNotRawDescriptor = namedtuple('EncodeNotRawDescriptor', [
    'flags',                                # +0x000
        # [31:16] ?????
        # 13 ?????
        # 12 ?????
        # [11:9] ?????
        # 8 - enable alpha
        # 7 - alpha channel bpp
        #   0 -> 8bpp
        #   1 -> 16bpp
        # 6 - something unknown about tiling
        # [5:4] ?????
        # [3:2] - chroma subsampling
        #   00 -> broken?
        #   01 -> broken?
        #   10 -> 4:2:2
        #   11 -> 4:4:4
        # [1:0] - input bpp
        #   00 -> 8bpp
        #   01 -> 16bpp?
        #   10 -> 16bpp?
        #   11 -> 16bpp?
        #       the last three all produce slightly differnet outputs
        #       so might be 10/12/14/16?????
    'flags2',                               # +0x004
    'output_iova',                          # +0x008
    'max_out_sz',                           # +0x010
    'offset_x',                             # +0x014
    'offset_y',                             # +0x016
    'pix_surface_w_2_',                     # +0x018
    'pix_surface_h_2_',                     # +0x01a
    'pix_surface_w',                        # +0x01c
    'pix_surface_h',                        # +0x01e
    'luma_stride',                          # +0x020
    'chroma_stride',                        # +0x022
    'alpha_stride',                         # +0x024
    'unk_pad_0x26_',                        # +0x026
    'luma_iova',                            # +0x028
    'pix_plane0_tileheader_thing_',         # +0x030
    'chroma_iova',                          # +0x038
    'pix_plane1_tileheader_thing_',         # +0x040
    'alpha_iova',                           # +0x048
    'pix_plane2_tileheader_thing_',         # +0x050
    'frame_header_sz',                      # +0x058
    'unk_pad_0x5a_',                        # +0x05a
    'bitstream_version',                    # +0x05b
    'encoder_identifier',                   # +0x05c
    'pix_surface_w_byteswap_',              # +0x060
    'pix_surface_h_byteswap_',              # +0x062
    'chroma_format_interlace_mode',         # +0x064
    'aspect_ratio_frame_rate',              # +0x065
    'color_primaries',                      # +0x066
    'transfer_characteristic',              # +0x067
    'matrix_coefficients',                  # +0x068
    'alpha_channel_type',                   # +0x069
    'frame_hdr_reserved14',                 # +0x06a
    'unk_pad_0x6c_',                        # +0x06c
    'deprecated_number_of_slices',          # +0x0ec
    'log2_desired_slice_size_in_mb',        # +0x0ee
    'quantization_index',                   # +0x0ef
    'unk_0xf0_',                            # +0x0f0
    'unk_0xf2_',                            # +0x0f2
    'unk_0xf4_',                            # +0x0f4
    'unk_0xfc_',                            # +0x0fc
    'unk_0x100_0_',                         # +0x100
    'unk_0x100_1_',                         # +0x104
    'unk_0x100_2_',                         # +0x108
    'unk_0x100_3_',                         # +0x10c
    'unk_0x110_0_',                         # +0x110
    'unk_0x110_1_',                         # +0x114
    'unk_0x110_2_',                         # +0x118
    'unk_0x110_3_',                         # +0x11c
    'unk_0x110_4_',                         # +0x120
    'unk_0x110_5_',                         # +0x124
    'unk_0x110_6_',                         # +0x128
    'unk_0x110_7_',                         # +0x12c
    'unk_0x110_8_',                         # +0x130
    'unk_0x110_9_',                         # +0x134
    'unk_0x110_10_',                        # +0x138
    'unk_0x110_11_',                        # +0x13c
    'unk_0x110_12_',                        # +0x140
    'unk_0x110_13_',                        # +0x144
    'unk_0x110_14_',                        # +0x148
    'unk_0x110_15_',                        # +0x14c
    'quant_table_sel',                      # +0x150
        # upper nibble: quality / table index
        # lower nibble UNKNOWN!
    'unk_pad_0x154_',                       # +0x154
])
ENCODE_NOT_RAW_STRUCT = "<IIQIHHHHHHHHH2sQQQQQQH1sBIHHBBBBBB2s128sHBBHHQIIIIIIIIIIIIIIIIIIIIII44s"


class ProResRegs(RegMap):
    # something reads
    REG_0x0     = 0x000, Register32
    MODE        = 0x008, Register32     # 4 bits
    IRQ_ENABLE  = 0x00c, Register32     # 2 bits
    IRQ_STATUS  = 0x010, Register32

    ST0         = 0x014, Register32     # interrupt handler reads
    ST1         = 0x018, Register32     # interrupt handler reads
    REG_0x1c    = 0x01c, Register32     # interrupt handler reads
    REG_0x38    = 0x038, Register32     # exists, maybe RO
    REG_0x3c    = 0x03c, Register32     # interrupt handler reads
    REG_0x40    = 0x040, Register32     # exists, maybe RO, looks like 0x44
    REG_0x44    = 0x044, Register32     # interrupt handler reads
    REG_0x48    = 0x048, Register32     # exists, maybe RO, looks like 0x44
    REG_0x4c    = 0x04c, Register32     # exists, maybe RO, looks like 0x44
    REG_0x50    = 0x050, Register32     # exists, maybe RO, looks like 0x44
    REG_0x54    = 0x054, Register32     # exists, maybe RO, looks like 0x44

    DR_SIZE     = 0x100, Register32
    DR_ADDR_LO  = 0x104, Register32
    DR_ADDR_HI  = 0x108, Register32
    DR_HEAD     = 0x10c, Register32     # bit24 is special, something about wrapping around?
    DR_TAIL     = 0x110, Register32

    # This giant block may or may not be touched by tunables
    # Function is all unknown
    REG_0x114   = 0x114, Register32     # can set bits 0000FFFF
    REG_0x118   = 0x118, Register32     # can set bits 07FF07FF

    REG_0x134   = 0x134, Register32     # can set bits 00000003

    REG_0x144   = 0x144, Register32     # can set bits 00000001
    REG_0x148   = 0x148, Register32     # can set bits 00000001

    REG_0x160   = 0x160, Register32     # can set bits BFFF3FFF
    REG_0x164   = 0x164, Register32     # can set bits 07FF07FF

    REG_0x170   = 0x170, Register32     # can set bits BFFF3FFF
    REG_0x174   = 0x174, Register32     # can set bits 07FF07FF

    REG_0x180   = 0x180, Register32     # can set bits BFFF3FFF
    REG_0x184   = 0x184, Register32     # can set bits 07FF07FF

    REG_0x190   = 0x190, Register32     # can set bits BFFF3FFF
    REG_0x194   = 0x194, Register32     # can set bits 000000FF
    REG_0x198   = 0x198, Register32     # RO? init value 07FB066F

    REG_0x1a0   = 0x1a0, Register32     # can set bits BFFF3FFF
    REG_0x1a4   = 0x1a4, Register32     # can set bits 000000FF
    REG_0x1a8   = 0x1a8, Register32     # RO? init value 037C03EE

    REG_0x1b0   = 0x1b0, Register32     # can set bits BFFF3FFF
    REG_0x1b4   = 0x1b4, Register32     # can set bits 000000FF
    REG_0x1b8   = 0x1b8, Register32     # RO? init value 04E00377

    REG_0x1c0   = 0x1c0, Register32     # can set bits BFFF3FFF
    REG_0x1c4   = 0x1c4, Register32     # can set bits 000000FF
    REG_0x1c8   = 0x1c8, Register32     # RO? init value 051C00DA

    REG_0x1d0   = 0x1d0, Register32     # can set bits BFFF3FFF
    REG_0x1d4   = 0x1d4, Register32     # can set bits 000000FF
    REG_0x1d8   = 0x1d8, Register32     # can set bits 000000FF
    REG_0x1dc   = 0x1dc, Register32     # can set bits 00FFFFFF

    REG_0x1ec   = 0x1ec, Register32     # can set bits FFFFFFFF

    REG_0x270   = 0x270, Register32     # can set bits BFFF3FFF
    REG_0x274   = 0x274, Register32     # can set bits 07FF07FF
    REG_0x278   = 0x278, Register32     # can set bits FFFFFFC0
    REG_0x27c   = 0x27c, Register32     # can set bits 000003FF
    REG_0x280   = 0x280, Register32     # can set bits FFFFFFC0
    REG_0x284   = 0x284, Register32     # can set bits FFFFFFC0
    REG_0x28c   = 0x28c, Register32     # can set bits FFFFFFC0

    REG_0x290   = 0x290, Register32     # can set bits BFFF3FFF
    REG_0x294   = 0x294, Register32     # can set bits 000000FF
    REG_0x298   = 0x298, Register32     # RO? init value 07FB066F

    REG_0x2a0   = 0x2a0, Register32     # can set bits BFFF3FFF
    REG_0x2a4   = 0x2a4, Register32     # can set bits 000000FF
    REG_0x2a8   = 0x2a8, Register32     # RO? init value 037C03EE

    REG_0x2b0   = 0x2b0, Register32     # can set bits BFFF3FFF
    REG_0x2b4   = 0x2b4, Register32     # can set bits 000000FF
    REG_0x2b8   = 0x2b8, Register32     # RO? init value 04E00377

    REG_0x2c0   = 0x2c0, Register32     # can set bits BFFF3FFF
    REG_0x2c4   = 0x2c4, Register32     # can set bits 000000FF
    REG_0x2c8   = 0x2c8, Register32     # RO? init value 051C00DA

    REG_0x2d0   = 0x2d0, Register32     # can set bits FFFFFFFD, CANNOT clear 00000011
    REG_0x2d4   = 0x2d4, Register32     # can set bits 00000001
    REG_0x2d8   = 0x2d8, Register32     # can set bits FFFF0007
    REG_0x2dc   = 0x2dc, Register32     # RO? init value 07FB066F
    REG_0x2e0   = 0x2e0, Register32     # can set bits 07FF07FF

    REG_0x2f0   = 0x2f0, Register32     # can set bits FFFFFFFF

    REG_0x2f8   = 0x2f8, Register32     # can set bits FFFFFFFD, CANNOT clear 00000011
    REG_0x2fc   = 0x2fc, Register32     # can set bits 00000001
    REG_0x300   = 0x300, Register32     # can set bits FFFF0007
    REG_0x304   = 0x304, Register32     # RO? init value 037C03EE
    REG_0x308   = 0x308, Register32     # can set bits 07FF07FF

    REG_0x318   = 0x318, Register32     # can set bits FFFFFFFF

    REG_0x320   = 0x320, Register32     # can set bits FFFFFFFD, CANNOT clear 00000011
    REG_0x324   = 0x324, Register32     # can set bits 00000001
    REG_0x328   = 0x328, Register32     # can set bits FFFF0007
    REG_0x32c   = 0x32c, Register32     # RO? init value 04E00377
    REG_0x330   = 0x330, Register32     # can set bits 07FF07FF

    REG_0x340   = 0x340, Register32     # can set bits FFFFFFFF

    REG_0x350   = 0x350, Register32     # can set bits BFFF3FFF
    REG_0x354   = 0x354, Register32     # can set bits 07FF07FF
    REG_0x358   = 0x358, Register32     # can set bits FFFFFFC0
    REG_0x35c   = 0x35c, Register32     # can set bits 000003FF
    REG_0x360   = 0x360, Register32     # can set bits FFFFFFC0
    REG_0x364   = 0x364, Register32     # can set bits FFFFFFC0
    REG_0x368   = 0x368, Register32     # can set bits FFFFFFC0

    REG_0x370   = 0x370, Register32     # can set bits BFFF3FFF
    REG_0x374   = 0x374, Register32     # can set bits 07FF07FF


    QUANT_LUMA_EHQ      = irange(0x0800, 32, 4), Register32
    QUANT_LUMA_HQ       = irange(0x0880, 32, 4), Register32
    QUANT_LUMA_NQ       = irange(0x0900, 32, 4), Register32
    QUANT_LUMA_LT       = irange(0x0980, 32, 4), Register32
    QUANT_LUMA_PROXY    = irange(0x0A00, 32, 4), Register32
    QUANT_CHROMA_EHQ    = irange(0x1000, 32, 4), Register32
    QUANT_CHROMA_HQ     = irange(0x1080, 32, 4), Register32
    QUANT_CHROMA_NQ     = irange(0x1100, 32, 4), Register32
    QUANT_CHROMA_LT     = irange(0x1180, 32, 4), Register32
    QUANT_CHROMA_PROXY  = irange(0x1200, 32, 4), Register32

    # wtf, writing to this doesn't actually work? do we have to enable it?
    DC_QUANT_SCALE      = irange(0x1800, 112, 4), Register32

    REG_0x19c0  = 0x19c0, Register32    # unknown, all 1s, RO?
    REG_0x19c4  = 0x19c4, Register32    # unknown, all 1s, RO?
    REG_0x19c8  = 0x19c8, Register32    # unknown, all 1s, RO?
    REG_0x19cc  = 0x19cc, Register32    # unknown, all 1s, RO?
    REG_0x19d0  = 0x19d0, Register32    # unknown, all 1s, RO?
    REG_0x19d4  = 0x19d4, Register32    # unknown, all 1s, RO?
    REG_0x19d8  = 0x19d8, Register32    # unknown, all 1s, RO?
    REG_0x19dc  = 0x19dc, Register32    # unknown, can set bits 00000001

    # Unknown, inits to 0x12345678, can R/W
    REG_0x1A00  = 0x1a00, Register32

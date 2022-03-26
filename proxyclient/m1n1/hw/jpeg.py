# SPDX-License-Identifier: MIT
from ..utils import *
from enum import IntEnum


class R_STATUS(Register32):
    DONE = 0
    TIMEOUT = 1
    RD_BUF_OVERFLOW = 2
    WR_BUF_OVERFLOW = 3
    CODEC_BUF_OVERFLOW = 4
    SOME_KIND_OF_MACROBLOCK_SIZE_ERROR = 5
    AXI_ERROR = 6
    UNKNOWN_FLAG = 7


class E_CODEC(IntEnum):
    _444 = 0
    _422 = 1
    _411 = 2
    _420 = 3
    _400 = 4


class R_CODEC(Register32):
    CODEC = 2, 0, E_CODEC


class E_ENCODE_PIXEL_FORMAT(IntEnum):
    RGB101010 = 0
    YUV10_linear = 1
    RGB888 = 2
    RGB565 = 3
    YUV_planar = 4      # partially tested, details not understood
    YUV_linear = 5      # partially tested, details not understood


class R_ENCODE_PIXEL_FORMAT(Register32):
    FORMAT = 4, 0, E_ENCODE_PIXEL_FORMAT


class E_SCALE(IntEnum):
    DIV1 = 0
    DIV2 = 1
    DIV4 = 2
    DIV8 = 3


class R_SCALE_FACTOR(Register32):
    SCALE = 1, 0, E_SCALE


class E_DECODE_PIXEL_FORMAT(IntEnum):
    YUV444_planar = 0
    YUV422_planar = 1
    YUV420_planar = 2
    YUV422_linear = 3
    _YUV10_broken_doesnt_work = 4
    RGBA8888 = 5
    RGB565 = 6
    _RGB101010_broken_doesnt_work = 7


class R_DECODE_PIXEL_FORMAT(Register32):
    FORMAT = 3, 0, E_DECODE_PIXEL_FORMAT


class E_JPEG_IO_FLAGS_SUBSAMPLING(IntEnum):
    _444 = 0
    _422 = 1
    _420 = 2
    _400 = 3
    FOUR_COMPONENTS_MODE = 4
    _411_BROKEN = 6


class R_JPEG_IO_FLAGS(Register32):
    SUBSAMPLING_MODE = 2, 0, E_JPEG_IO_FLAGS_SUBSAMPLING
    # not sure what this is supposed to do
    MAKE_DECODE_WORK_BREAK_ENCODE = 3
    OUTPUT_MACROBLOCKS_UNFLIPPED_H = 4
    OUTPUT_8BYTE_CHUNKS_CORRECTLY = 5


class R_JPEG_OUTPUT_FLAGS(Register32):
    # bit0 doesn't seem to do anything
    SKIP_HEADERS = 1            # output only SOS/EOI, no SOI/DQT/SOF0/DHT
    OUTPUT_SOF0_AFTER_DHT = 2   # output SOF0 after DHT instead of before it
    # bit3 doesn't seem to do anything
    COMPRESS_WORSE = 4          # not sure exactly what this does


class R_QTBL_SEL(Register32):
    COMPONENT0 = 1, 0
    COMPONENT1 = 3, 2
    COMPONENT2 = 5, 4
    COMPONENT3 = 7, 6     # guessed


class JPEGRegs(RegMap):
    REG_0x0 = 0x0, Register32
    REG_0x4 = 0x4, Register32
    MODE = 0x8, Register32
    REG_0xc = 0xc, Register32

    REG_0x10 = 0x10, Register32
    REG_0x14 = 0x14, Register32
    REG_0x18 = 0x18, Register32
    # REG_0x1c = 0x1c, Register32

    REG_0x20 = 0x20, Register32
    STATUS = 0x24, R_STATUS

    CODEC = 0x28, R_CODEC

    REG_0x2c = 0x2c, Register32
    REG_0x30 = 0x30, Register32
    REG_0x34 = 0x34, Register32
    # this changes the output drastically if set to 1 for decode
    # breaks encode if not set to 1
    REG_0x38 = 0x38, Register32

    # not sure what the difference is. siting? type2 seems to win over type1
    CHROMA_HALVE_H_TYPE1 = 0x3c, Register32
    CHROMA_HALVE_H_TYPE2 = 0x40, Register32
    CHROMA_HALVE_V_TYPE1 = 0x44, Register32
    CHROMA_HALVE_V_TYPE2 = 0x48, Register32

    # if double and quadruple both set --> double
    CHROMA_DOUBLE_H = 0x4c, Register32
    CHROMA_QUADRUPLE_H = 0x50, Register32
    CHROMA_DOUBLE_V = 0x54, Register32

    # details not fully understood yet
    PX_USE_PLANE1 = 0x58, Register32
    PX_TILES_W = 0x5c, Register32
    PX_TILES_H = 0x60, Register32
    PX_PLANE0_WIDTH = 0x64, Register32
    PX_PLANE0_HEIGHT = 0x68, Register32
    PX_PLANE0_TILING_H = 0x6c, Register32
    PX_PLANE0_TILING_V = 0x70, Register32
    PX_PLANE0_STRIDE = 0x74, Register32
    PX_PLANE1_WIDTH = 0x78, Register32
    PX_PLANE1_HEIGHT = 0x7c, Register32
    PX_PLANE1_TILING_H = 0x80, Register32
    PX_PLANE1_TILING_V = 0x84, Register32
    PX_PLANE1_STRIDE = 0x88, Register32

    INPUT_START1 = 0x8c, Register32
    INPUT_START2 = 0x90, Register32
    REG_0x94 = 0x94, Register32
    REG_0x98 = 0x98, Register32
    INPUT_END = 0x9c, Register32

    OUTPUT_START1 = 0xa0, Register32
    OUTPUT_START2 = 0xa4, Register32
    OUTPUT_END = 0xa8, Register32

    MATRIX_MULT = irange(0xAC, 11, 4), Register32
    DITHER = irange(0xD8, 10, 4), Register32

    ENCODE_PIXEL_FORMAT = 0x100, R_ENCODE_PIXEL_FORMAT
    # RGB888: R, G, B = byte pos
    # RGB101010: R, G, B = 0/1/2 = low/mid/high bits
    # RGB565: R, G, B = 0/1/2 = low/mid/high bits
    # YUV10: Y, U, V = 0/1/2 = low/mid/high bits
    # YUV linear: Y0 Cb Cr Y1 = byte pos
    # YUV planar: Y U V = 0 for Y, 0/1 for U/V indicating position somehow
    ENCODE_COMPONENT0_POS = 0x104, Register32
    ENCODE_COMPONENT1_POS = 0x108, Register32
    ENCODE_COMPONENT2_POS = 0x10c, Register32
    ENCODE_COMPONENT3_POS = 0x110, Register32

    CONVERT_COLOR_SPACE = 0x114, Register32

    REG_0x118 = 0x118, Register32
    REG_0x11c = 0x11c, Register32

    REG_0x120 = 0x120, Register32

    # details not understood yet
    TILING_ENABLE = 0x124, Register32
    TILING_PLANE0 = 0x128, Register32
    TILING_PLANE1 = 0x12c, Register32

    DECODE_MACROBLOCKS_W = 0x130, Register32
    DECODE_MACROBLOCKS_H = 0x134, Register32
    RIGHT_EDGE_PIXELS = 0x138, Register32
    BOTTOM_EDGE_PIXELS = 0x13c, Register32
    RIGHT_EDGE_SAMPLES = 0x140, Register32
    BOTTOM_EDGE_SAMPLES = 0x144, Register32

    SCALE_FACTOR = 0x148, R_SCALE_FACTOR

    DECODE_PIXEL_FORMAT = 0x14c, R_DECODE_PIXEL_FORMAT
    # 0 = Cb Y'0 Cr Y'1     1 = Y'0 Cb Y'1 Cr
    YUV422_ORDER = 0x150, Register32
    # 0 = BGRA              1 = RGBA
    RGBA_ORDER = 0x154, Register32
    RGBA_ALPHA = 0x158, Register32

    PLANAR_CHROMA_HALVING = 0x15c, Register32

    REG_0x160 = 0x160, Register32
    REG_0x164 = 0x164, Register32
    # REG_0x168 = 0x168, Register32
    REG_0x16c = 0x16c, Register32

    REG_0x170 = 0x170, Register32
    # REG_0x174 = 0x174, Register32
    PERFCOUNTER = 0x178, Register32
    # REG_0x17c = 0x17c, Register32

    # REG_0x180 = 0x180, Register32
    TIMEOUT = 0x184, Register32
    HWREV = 0x188, Register32

    REG_0x18c = 0x18c, Register32
    REG_0x190 = 0x190, Register32
    REG_0x194 = 0x194, Register32
    REG_0x198 = 0x198, Register32
    REG_0x19c = 0x19c, Register32

    ENABLE_RST_LOGGING = 0x1a0, Register32
    RST_LOG_ENTRIES = 0x1a4, Register32

    REG_0x1a8 = 0x1a8, Register32
    REG_0x1ac = 0x1ac, Register32
    REG_0x1b0 = 0x1b0, Register32

    REG_0x1b4 = 0x1b4, Register32
    REG_0x1b8 = 0x1b8, Register32
    REG_0x1bc = 0x1bc, Register32

    REG_0x1c0 = 0x1c0, Register32
    REG_0x1c4 = 0x1c4, Register32

    REG_0x1c8 = 0x1c8, Register32

    REG_0x1cc = 0x1cc, Register32
    REG_0x1d0 = 0x1d0, Register32
    REG_0x1d4 = 0x1d4, Register32
    REG_0x1d8 = 0x1d8, Register32

    REG_0x1dc = 0x1dc, Register32
    REG_0x1e0 = 0x1e0, Register32
    REG_0x1e4 = 0x1e4, Register32
    REG_0x1e8 = 0x1e8, Register32

    REG_0x1ec = 0x1ec, Register32
    REG_0x1f0 = 0x1f0, Register32
    REG_0x1f4 = 0x1f4, Register32
    REG_0x1f8 = 0x1f8, Register32

    REG_0x1fc = 0x1fc, Register32
    REG_0x200 = 0x200, Register32

    REG_0x204 = 0x204, Register32
    REG_0x208 = 0x208, Register32

    REG_0x20c = 0x20c, Register32
    REG_0x210 = 0x210, Register32
    REG_0x214 = 0x214, Register32
    REG_0x218 = 0x218, Register32

    REG_0x21c = 0x21c, Register32
    REG_0x220 = 0x220, Register32

    REG_0x224 = 0x224, Register32
    REG_0x228 = 0x228, Register32

    REG_0x22c = 0x22c, Register32
    REG_0x230 = 0x230, Register32
    REG_0x234 = 0x234, Register32

    REG_0x238 = 0x238, Register32
    REG_0x23c = 0x23c, Register32
    REG_0x240 = 0x240, Register32
    REG_0x244 = 0x244, Register32
    REG_0x248 = 0x248, Register32

    REG_0x24c = 0x24c, Register32
    REG_0x250 = 0x250, Register32
    REG_0x254 = 0x254, Register32
    REG_0x258 = 0x258, Register32
    REG_0x25c = 0x25c, Register32

    REG_0x260 = 0x260, Register32
    REG_0x264 = 0x264, Register32
    REG_0x268 = 0x268, Register32
    REG_0x26c = 0x26c, Register32

    REG_0x280 = 0x280, Register32

    JPEG_IO_FLAGS = 0x1000, R_JPEG_IO_FLAGS
    REG_0x1004 = 0x1004, Register32
    REG_0x1008 = 0x1008, Register32
    QTBL_SEL = 0x100c, R_QTBL_SEL

    # fixme what _exactly_ does this control
    HUFFMAN_TABLE = 0x1010, Register32
    RST_INTERVAL = 0x1014, Register32     # 16 bits effective
    JPEG_HEIGHT = 0x1018, Register32
    JPEG_WIDTH = 0x101c, Register32

    COMPRESSED_BYTES = 0x1020, Register32
    JPEG_OUTPUT_FLAGS = 0x1024, R_JPEG_OUTPUT_FLAGS
    REG_0x1028 = 0x1028, Register32
    REG_0x102c = 0x102c, Register32

    BITSTREAM_CORRUPTION = 0x1030, Register32
    # REG_0x1034 = 0x1034, Register32
    # REG_0x1038 = 0x1038, Register32
    # REG_0x103c = 0x103c, Register32

    REG_0x1080 = 0x1080, Register32
    REG_0x1084 = 0x1084, Register32
    # REG_0x1088 = 0x1088, Register32
    REG_0x108c = 0x108c, Register32
    REG_0x1090 = 0x1090, Register32

    SHIKINO_VERSION_MAGIC0 = 0x10e0, Register32
    SHIKINO_VERSION_MAGIC1 = 0x10e4, Register32
    SHIKINO_VERSION_MAGIC2 = 0x10e8, Register32
    SHIKINO_VERSION_MAGIC3 = 0x10ec, Register32
    SHIKINO_VERSION_MAGIC4 = 0x10f0, Register32
    # REG_0x10f4 = 0x10f4, Register32
    # REG_0x10f8 = 0x10f8, Register32
    # REG_0x10fc = 0x10fc, Register32

    QTBL = irange(0x1100, 64, 4), Register32

    # todo what's the format?
    RSTLOG = irange(0x2000, 1024, 4), Register32

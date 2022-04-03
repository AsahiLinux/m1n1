# SPDX-License-Identifier: MIT
from ..utils import *
from enum import IntEnum


class ProResRegs(RegMap):
    # something reads
    REG_0x0     = 0x000, Register32
    # activate writes
    REG_0x8     = 0x008, Register32
    # timer handler reads
    REG_0xc     = 0x00c, Register32
    # interrupt handler reads
    REG_0x10    = 0x010, Register32
    REG_0x14    = 0x014, Register32
    REG_0x18    = 0x018, Register32
    REG_0x1c    = 0x01c, Register32
    REG_0x3c    = 0x03c, Register32
    REG_0x44    = 0x044, Register32

    # activate writes
    REG_0x100   = 0x100, Register32
    REG_0x104   = 0x104, Register32
    REG_0x108   = 0x108, Register32

    DR_HEAD     = 0x10c, Register32     # bit20 is special
    DR_TAIL     = 0x110, Register32

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

    DC_QUANT_SCALE      = irange(0x1800, 112, 4), Register32

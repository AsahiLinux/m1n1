# SPDX-License-Identifier: MIT

import struct

from ..utils import *

__all__ = ["SPIRegs"]

class R_CTRL(Register32):
    RX_FIFO_RESET   = 3
    TX_FIFO_RESET   = 2
    RUN             = 0

class R_PIN(Register32):
    CS              = 1
    KEEP_MOSI       = 0

class R_CONFIG(Register32):
    # impl: 002fb1e6
    IE_TX_COMPLETE  = 21
    b19             = 19
    FIFO_THRESH     = 18, 17
        # 0 = 8 bytes
        # 1 = 4 bytes
        # 2 = 1 byte
        # 3 = disabled
    WORD_SIZE       = 16, 15
        # 0 = 8bit
        # 1 = 16bit
        # 2 = 32bit
    LSB_FIRST       = 13
    b12             = 12
    IE_RX_THRESH    = 8
    IE_RX_COMPLETE  = 7
    MODE            = 6, 5
        # 0 = polled
        # 1 = irq
    CPOL            = 2
    CPHA            = 1

class R_STATUS(Register32):
    TX_COMPLETE     = 22
    TXRX_THRESH     = 1     # updated if MODE == 1
    RX_COMPLETE     = 0

class R_FIFO_STAT(Register32):
    LEVEL_RX        = 31, 24
    RX_EMPTY        = 20
    LEVEL_TX        = 15, 8
    TX_FULL         = 4

class R_ISTATUS1(Register32):
    TX_XFER_DONE    = 1
    RX_XFER_DONE    = 0

class R_ISTATUS2(Register32):
    TX_OVERFLOW     = 17
    RX_UNDERRUN     = 16
    TX_EMPTY        = 9
    RX_FULL         = 8
    TX_THRESH       = 5
    RX_THRESH       = 4

class R_CLKDIV(Register32):
    DIVIDER         = 10, 0 # SPI freq = CLK / (DIVIDER + 1)

class R_INTER_DLY(Register32):
    DELAY           = 15, 0

# FIFO size: 16 bytes
# backend FIFO: TX 2 bytes, RX 1 byte?

class R_XFSTATUS(Register32):
    SR_FULL         = 26
    SHIFTING        = 20
    STATE           = 17, 16
    UNK             = 0

class R_DIVSTATUS(Register32):
    COUNT2          = 31, 16
    COUNT1          = 15, 0

class R_SHIFTCONFIG(Register32):
    OVERRIDE_CS     = 24
    BITS            = 21, 16
    RX_ENABLE       = 11
    TX_ENABLE       = 10
    CS_AS_DATA      = 9
    AND_CLK_DATA    = 8
    #?              = 2  # needs to be 1 for RX to not break
    CS_ENABLE       = 1
    CLK_ENABLE      = 0

class R_PINCONFIG(Register32):
    MOSI_INIT_VAL   = 10
    CS_INIT_VAL     = 9
    CLK_INIT_VAL    = 8
    KEEP_MOSI       = 2
    KEEP_CS         = 1
    KEEP_CLK        = 0

class R_DELAY(Register32):
    DELAY           = 31, 16
    MOSI_VAL        = 12
    CS_VAL          = 10
    SCK_VAL         = 8
    SET_MOSI        = 6
    SET_CS          = 5
    SET_SCK         = 4
    NO_INTERBYTE    = 1
    ENABLE          = 0

class R_SCK_CONFIG(Register32):
    PERIOD          = 31, 16
    PHASE1          = 9
    PHASE0          = 8
    RESET_TO_IDLE   = 4

class R_SCK_PHASES(Register32):
    PHASE1_START   = 31, 16
    PHASE0_START   = 15, 0

class SPIRegs(RegMap):
    CTRL        = 0x00, R_CTRL
    CONFIG      = 0x04, R_CONFIG
    STATUS      = 0x08, R_STATUS
    PIN         = 0x0C, R_PIN
    TXDATA      = 0x10, Register32
    RXDATA      = 0x20, Register32
    CLKDIV      = 0x30, R_CLKDIV
    RXCNT       = 0x34, Register32
    INTER_DLY   = 0x38, R_INTER_DLY
    TXCNT       = 0x4C, Register32
    FIFO_STAT   = 0x10C, R_FIFO_STAT

    IMASK1      = 0x130, R_ISTATUS1
    ISTATUS1    = 0x134, R_ISTATUS1
    IMASK2      = 0x138, R_ISTATUS2
    ISTATUS2    = 0x13c, R_ISTATUS2

    SHIFTCONFIG = 0x150, R_SHIFTCONFIG
    PINCONFIG   = 0x154, R_PINCONFIG

    PRE_DLY     = 0x160, R_DELAY
    SCK_CONFIG  = 0x164, R_SCK_CONFIG
    POST_DLY    = 0x168, R_DELAY

    SCK_PHASES  = 0x180, R_SCK_PHASES

    UNK_PHASE   = 0x18c, Register32 # probably MISO sample point

    XFSTATUS    = 0x1c0, R_XFSTATUS
    DIVSTATUS   = 0x1e0, R_DIVSTATUS

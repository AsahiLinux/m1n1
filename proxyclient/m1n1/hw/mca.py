# SPDX-License-Identifier: MIT
from ..utils import *
from enum import IntEnum

class R_STATUS(Register32):
    EN  = 0
    RST = 1

class R_MCLK_CONF(Register32):
    SEL = 3, 0

class R_PORT_ENABLES(Register32):
    CLOCK1 = 1
    CLOCK2 = 2
    DATA   = 3

class R_PORT_CLKSEL(Register32):
    SEL = 11, 8

class R_PORT_DATASEL(Register32):
    TXA0 = 0
    TXA1 = 2
    TXA2 = 4
    TXA3 = 6
    TXA4 = 8
    TXA5 = 10

    TXB0 = 1
    TXB1 = 3
    TXB2 = 5
    TXB3 = 7
    TXB4 = 9
    TXB5 = 11

class E_SLOT_WIDTH(IntEnum):
    NONE = 0

    W_16BIT =  0x4
    W_20BIT =  0x8
    W_24BIT =  0xc
    W_32BIT = 0x10

class R_SERDES_CONF(Register32):
    NSLOTS     = 3, 0
    SLOT_WIDTH = 8, 4, E_SLOT_WIDTH

    BCLK_POL  = 10
    LSB_FIRST = 11

    UNK1 = 12
    UNK2 = 13
    IDLE_UNDRIVEN = 14 # TX only
    NO_DATA_FEEDBACK = 15 # RX only

    SYNC_SEL = 18, 16

class R_INTMASK(Register32):
    # macOS interested in 0x823c
    UNK1 = 2 # m
    UNK2 = 3 # m
    UNK3 = 4 # m
    TX_UNDERFLOW = 5 # m

    UNK4 = 9 # m
    READ_SENSITIVE_UNK1 = 11
    READ_SENSITIVE_UNK2 = 15 # m

class MCAClusterRegs(RegMap):
    MCLK_STATUS = 0x0, R_STATUS
    MCLK_CONF   = 0x4, R_MCLK_CONF

    SYNCGEN_STATUS    = 0x100, R_STATUS
    SYNCGEN_MCLK_SEL  = 0x104, Register32
    SYNCGEN_HI_PERIOD = 0x108, Register32
    SYNCGEN_LO_PERIOD = 0x10c, Register32

    PORT_ENABLES   = 0x600, R_PORT_ENABLES
    PORT_CLK_SEL   = 0x604, R_PORT_CLKSEL
    PORT_DATA_SEL  = 0x608, R_PORT_DATASEL

    INTSTATE = 0x700, R_INTMASK
    INTMASK  = 0x704, R_INTMASK

class MCATXSerdesRegs(RegMap):
    STATUS   = 0x0, R_STATUS
    CONF     = 0x4, R_SERDES_CONF
    BITDELAY = 0x8, Register32
    CHANMASK = irange(0xc, 4, 4), Register32

class MCARXSerdesRegs(RegMap):
    STATUS   = 0x0, R_STATUS
    UNK1     = 0x4, Register32
    CONF     = 0x8, R_SERDES_CONF
    BITDELAY = 0xc, Register32
    CHANMASK = irange(0x10, 4, 4), Register32


class MCACluster:
    def __init__(self, u, base):
        self.regs = MCAClusterRegs(u, base)
        self.txa = MCATXSerdesRegs(u, base + 0x300)
        self.txb = MCATXSerdesRegs(u, base + 0x500)
        self.rxa = MCARXSerdesRegs(u, base + 0x200)
        self.rxb = MCARXSerdesRegs(u, base + 0x400)
        self.all_regs = [
            self.regs,
            self.txa, self.txb,
            self.rxa, self.rxb
        ]


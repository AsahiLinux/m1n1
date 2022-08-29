from m1n1.utils import RegMap, Register8
from enum import IntEnum
from .cs42l84 import *

class E_PWR_MODE(IntEnum):
    ACTIVE   = 0
    MUTE     = 1
    SHUTDOWN = 2

class R_PWR_CTL(Register8):
    ISNS_PD = 3
    VSNS_PD = 2
    MODE    = 1, 0, E_PWR_MODE

class R_PB_CFG0(Register8):
    PDM_MAP    = 7
    PB_PDM_SRC = 6
    PB_SRC     = 5
    AMP_LEVEL  = 4, 0

class R_PB_CFG2(Register8):
    DVC_PCM = 7, 0

class R_PB_CFG3(Register8):
    DVC_PDM = 7, 0

class E_RX_SCFG(IntEnum):
    I2C_OFFSET = 0b00
    LEFT       = 0b01
    RIGHT      = 0b10
    DOWNMIX    = 0b11

class E_RX_WLEN(IntEnum):
    W_16BIT = 0b00
    W_20BIT = 0b01
    W_24BIT = 0b10
    W_32BIT = 0b11

class E_RX_SLEN(IntEnum):
    W_16BIT = 0b00
    W_24BIT = 0b01
    W_32BIT = 0b10

class R_TDM_CFG2(Register8):
    RX_SCFG = 5, 4, E_RX_SCFG
    RX_WLEN = 3, 2, E_RX_WLEN
    RX_SLEN = 1, 0, E_RX_SLEN

class R_TDM_CFG3(Register8):
    RX_SLOT_R = 7, 4
    RX_SLOT_L = 3, 0

class TAS5770Regs(RegMap):
    PWR_CTL  = 0x002, R_PWR_CTL
    PB_CFG0  = 0x003, R_PB_CFG0
    PB_CFG2  = 0x005, R_PB_CFG2
    PB_CFG3  = 0x006, R_PB_CFG3
    TDM_CFG2 = 0x00c, R_TDM_CFG2
    TDM_CFG3 = 0x00d, R_TDM_CFG3

class R_MODE_CTRL(Register8):
    BOP_SRC = 7
    ISNS_PD = 3
    VSNS_PD = 2
    MODE    = 1, 0, E_PWR_MODE

class R_CHNL_0(Register8):
    CDS_MODE  = 7, 6
    AMP_LEVEL = 5, 1

class R_DVC(Register8):
    DVC_LVL = 7, 0

class R_INT_MASK0(Register8):
    BOPM  = 7
    BOPIH = 6
    LIMMA = 5
    PBIP  = 4
    LIMA  = 3
    TDMCE = 2
    OC    = 1
    OT    = 0

class R_INT_CLK_CFG(Register8):
    CLK_ERR_PWR_EN = 7
    DIS_CLK_HAT    = 6
    CLK_HALT_TIMER = 5, 3
    IRQZ_CLR       = 2
    IRQZ_PIN_CFG   = 1, 0

class SN012776Regs(RegMap):
    MODE_CTRL = 0x002, R_MODE_CTRL
    CHNL_0    = 0x003, R_CHNL_0
    DVC       = 0x01a, R_DVC

    INT_MASK0 = 0x03b, R_INT_MASK0
    INT_MASK1 = 0x03c, Register8
    INT_MASK2 = 0x040, Register8
    INT_MASK3 = 0x041, Register8
    INT_MASK4 = 0x03d, Register8

    INT_LTCH0   = 0x049, R_INT_MASK0
    INT_LTCH1   = 0x04a, Register8
    INT_LTCH1_0 = 0x04b, Register8
    INT_LTCH2   = 0x04f, Register8
    INT_LTCH3   = 0x050, Register8
    INT_LTCH4   = 0x051, Register8

    INT_CLK_CFG = 0x05c, R_INT_CLK_CFG

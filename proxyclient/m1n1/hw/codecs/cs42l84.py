from m1n1.utils import Register8, Register32, RegMap, irange
from enum import IntEnum

class R_IRQ_MASK1(Register8):
    RING_PLUG   = 0
    RING_UNPLUG = 1
    TIP_PLUG    = 2
    TIP_UNPLUG  = 3

class E_DCID_GND_SEL(IntEnum):
    NONE = 0
    HS3  = 1
    HS4  = 2

class E_DCID_Z_RANGE(IntEnum):
    NONE = 0
    UNK2 = 2
    UNK3 = 3

class R_DCID_CTRL1(Register8):
    Z_RANGE = 2, 0, E_DCID_Z_RANGE

class R_DCID_CTRL2(Register8):
    GND_SEL = 6, 4, E_DCID_GND_SEL

class R_DCID_CTRL3(Register8):
    START = 0

class R_DCID_STATUS(Register32):
    OVERALL = 9, 0
    DONE    = 10
    U       = 20, 11
    D       = 30, 21

class E_DEBOUNCE_TIME(IntEnum):
    T_0MS   = 0b000
    T_125MS = 0b001
    T_250MS = 0b010
    T_500MS = 0b011
    T_750MS = 0b100
    T_1S    = 0b101

class R_TR_SENSE_CTRL(Register8):
    INV      = 7
    UNK1     = 6
    FALLTIME = 5, 3, E_DEBOUNCE_TIME
    RISETIME = 2, 0, E_DEBOUNCE_TIME

class R_TR_SENSE_STATUS(Register8):
    RING_PLUG   = 0
    RING_UNPLUG = 1
    TIP_PLUG    = 2
    TIP_UNPLUG  = 3

class R_MSM_BLOCK_EN3(Register8):
    TR_SENSE_EN = 3
    DCID_EN     = 4

class R_HS_CLAMP_DISABLE(Register8):
    HS_CLAMP_DISABLE = 0

class E_SAMP_RATE(IntEnum):
    S_16KHZ   = 1
    S_24KHZ   = 2
    S_32KHZ   = 3
    S_48KHZ   = 4
    S_96KHZ   = 5
    S_192KHZ  = 6
    S_22K05HZ = 10
    S_44K1HZ  = 12
    S_88K2HZ  = 13
    S_176K4HZ = 14

class R_CCM_SAMP_RATE(Register8):
    RATE = 7, 0, E_SAMP_RATE

class R_DAC_CTRL1(Register8):
    HP_LOAD = 2 # maybe
    UNK2    = 4
    UNK3    = 5 # always set
    HIGH_V  = 6

class E_PULLDOWN_R(IntEnum):
    NONE      = 0x0
    R_UNK8    = 0x8
    R_1K1OHMS = 0xc

class R_DAC_CTRL2(Register8):
    PULLDOWN_R = 3, 0, E_PULLDOWN_R

class R_HSBIAS_SC_AUTOCTL(Register8):
    TIP_SENSE_EN = 5

class E_TIP_SENSE_CTRL(IntEnum):
    DISABLED  = 0b00
    DIG_INPUT = 0b01
    SHORT_DET = 0b11

class R_TIP_SENSE_CTRL2(Register8):
    CTRL = 7, 6, E_TIP_SENSE_CTRL
    INV  = 5

class E_HSBIAS_CTRL(IntEnum):
    HI_Z  = 0b00
    U_0V0 = 0b01
    U_2V0 = 0b10
    U_2V7 = 0b11

class R_MISC_DET_CTRL(Register8):
    HSBIAS_CTRL = 2, 1, E_HSBIAS_CTRL

class E_S0_DEBOUNCE_TIME(IntEnum):
    T_10MS = 0b000
    T_20MS = 0b001
    T_30MS = 0b010
    T_40MS = 0b011
    T_50MS = 0b100
    T_60MS = 0b101
    T_70MS = 0b110
    T_80MS = 0b111

class R_MIC_DET_CTRL2(Register8):
    DEBOUNCE_TIME = 7, 5, E_S0_DEBOUNCE_TIME

class R_MIC_DET_CTRL4(Register8):
    LATCH_TO_VP = 1

class R_HS_SWITCH_CTRL(Register8):
    REF_HS3      = 7
    REF_HS4      = 6
    HSB_FILT_HS3 = 5
    HSB_FILT_HS4 = 4
    HSB_HS3      = 3
    HSB_HS4      = 2
    GNDHS_HS3    = 1
    GNDHS_HS4    = 0

class CS42L84Regs(RegMap):
    DEVID  = irange(0x0, 5), Register8
    FREEZE = 0x6, Register8

    SW_RESET = 0x203, Register8

    IRQ_STATUS = irange(0x400, 3), Register8
    IRQ_MASK1  = 0x418, R_IRQ_MASK1
    IRQ_MASK2  = 0x419, Register8
    IRQ_MASK3  = 0x41a, Register8

    CCM_CTRL         = irange(0x600, 4), Register8
    CCM_SAMP_RATE    = 0x601, R_CCM_SAMP_RATE
    CCM_ASP_CLK_CTRL = 0x608, Register8

    PLL_CTRL     = 0x800, Register8
    PLL_DIV_FRAC = irange(0x804, 3), Register8
    PLL_DIV_INT  = 0x807, Register8
    PLL_DIVOUT   = 0x808, Register8

    DCID_CTRL1          = 0x1200, R_DCID_CTRL1
    DCID_CTRL2          = 0x1201, R_DCID_CTRL2
    DCID_CTRL3          = 0x1202, R_DCID_CTRL3
    DCID_TRIM_OFFSET    = 0x1207, Register8
    DCID_TRIM_SLOPE     = 0x120a, Register8

    # R_pull = 1100 - (regval - 128)*2
    DCID_PULLDOWN_TRIM  = 0x120b, Register8
    DCID_STATUS         = 0x120c, R_DCID_STATUS

    # tip/ring sense
    TR_SENSE_CTRL1  = 0x1280, Register8
    TR_SENSE_CTRL2  = 0x1281, Register8
    RING_SENSE_CTRL = 0x1282, R_TR_SENSE_CTRL
    TIP_SENSE_CTRL  = 0x1283, R_TR_SENSE_CTRL
    TR_SENSE_STATUS = 0x1288, R_TR_SENSE_STATUS

    HSBIAS_SC_AUTOCTL = 0x1470, R_HSBIAS_SC_AUTOCTL
    WAKE_CTRL         = 0x1471, Register8 # guess (cs42l42)
    TIP_SENSE_CTRL2   = 0x1473, R_TIP_SENSE_CTRL2 # guess (cs42l42)
    MISC_DET_CTRL     = 0x1474, R_MISC_DET_CTRL # guess (cs42l42)
    MIC_DET_CTRL2     = 0x1478, R_MIC_DET_CTRL2
    MIC_DET_CTRL4     = 0x1477, R_MIC_DET_CTRL4

    MIKEY_DET_STATUS     = irange(0x147c, 2), Register8
    MIKEY_DET_IRQ_MASK   = irange(0x1480, 2), Register8
    MIKEY_DET_IRQ_STATUS = irange(0x1484, 2), Register8

    MSM_BLOCK_EN3    = 0x1802, R_MSM_BLOCK_EN3
    HS_SWITCH_CTRL   = 0x1812, R_HS_SWITCH_CTRL
    HS_CLAMP_DISABLE = 0x1813, R_HS_CLAMP_DISABLE
    ADC_CTRL     = irange(0x2000, 4), Register8

    DAC_CTRL1     = 0x3000, R_DAC_CTRL1
    DAC_CTRL2     = 0x3001, R_DAC_CTRL2
    DACA_VOL_LSB  = 0x3004, Register8
    DACA_VOL_MSB  = 0x3005, Register8 # sign bit
    DACB_VOL_LSB  = 0x3006, Register8
    DACB_VOL_MSB  = 0x3007, Register8 # sign bit
    HP_VOL_CTRL   = 0x3020, Register8
    HP_CLAMP_CTRL = 0x3123, Register8

    ASP_CTRL       = 0x5000, Register8
    ASP_FSYNC_CTRL = irange(0x500f, 3), Register8
    ASP_DATA_CTRL  = 0x5018, Register8

    ASP_RX_EN = 0x5020, Register8
    ASP_TX_EN = 0x5024, Register8

    ASP_RXSLOT_CH1_LSB = 0x5028, Register8
    ASP_RXSLOT_CH1_MSB = 0x5029, Register8

    ASP_RXSLOT_CH2_LSB = 0x502c, Register8
    ASP_RXSLOT_CH2_MSB = 0x502d, Register8

    ASP_TXSLOT_CH1_LSB = 0x5068, Register8
    ASP_TXSLOT_CH1_MSB = 0x5068, Register8

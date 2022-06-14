from m1n1.utils import Register8, Register16, Register32, RegMap, irange
from enum import IntEnum

class R_IRQ_MASK1(Register8):
    RING_PLUG   = 0
    RING_UNPLUG = 1
    TIP_PLUG    = 2
    TIP_UNPLUG  = 3

class R_IRQ_MASK3(Register8):
    HSDET_AUTO_DONE = 7

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

class R_HS_DET_STATUS2(Register8):
    HS_TRUE    = 1
    SHORT_TRUE = 0

class R_MSM_BLOCK_EN1(Register8):
    pass

class R_MSM_BLOCK_EN2(Register8):
    ASP_EN = 6
    BUS_EN = 5
    DAC_EN = 4
    ADC_EN = 3

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

class E_MCLK_SRC(IntEnum):
    RCO      = 0b00
    MCLK_PIN = 0b01
    BCLK     = 0b10
    PLL      = 0b11

class E_MCLK_FREQ(IntEnum):
    F_12MHZ     = 0b00
    F_24MHZ     = 0b01
    F_12_288KHZ = 0b10
    F_24_576KHZ = 0b11

class R_CCM_CTRL1(Register8):
    MCLK_SRC  = 1, 0, E_MCLK_SRC
    MCLK_FREQ = 3, 2, E_MCLK_FREQ

class E_REFCLK_DIV(IntEnum):
    DIV1 = 0b00
    DIV2 = 0b01
    DIV4 = 0b10
    DIV8 = 0b11

class R_CCM_CTRL3(Register8):
    REFCLK_DIV     = 2, 1, E_REFCLK_DIV
    REFCLK_IS_MCLK = 0 # BLCK otherwise

class R_CCM_CTRL4(Register8):
    REFCLK_EN = 0

class R_CCM_SAMP_RATE(Register8):
    RATE = 7, 0, E_SAMP_RATE

class E_PLL_MODE(IntEnum):
    UNSUPP      = 0b00
    BYPASS_512  = 0b01
    BYPASS_1024 = 0b10
    BYPASS_BOTH = 0b11

class R_PLL_CTRL(Register8):
    MODE = 2, 1, E_PLL_MODE
    EN   = 0

class E_WNF_CF(IntEnum):
    F_UNK   = 0b00
    F_300HZ = 0b11

class R_ADC_CTRL1(Register8):
    PREAMP_GAIN = 7, 6
    PGA_GAIN    = 5, 0

class R_ADC_CTRL4(Register8): # maybe
    WNF_CF = 5, 4, E_WNF_CF
    WNF_EN = 3

class R_DAC_CTRL1(Register8):
    UNMUTE  = 0

    HP_LOAD = 2 # maybe
    UNK1    = 3
    UNK2    = 4
    UNK3    = 5
    HIGH_V  = 6

class E_PULLDOWN_R(IntEnum):
    NONE      = 0x0
    R_UNK8    = 0x8
    R_1K1OHMS = 0xc

class R_DAC_CTRL2(Register8):
    PULLDOWN_R = 3, 0, E_PULLDOWN_R

class R_HP_VOL_CTRL(Register8):
    ZERO_CROSS  = 1
    SOFT        = 0

class E_BUS_SOURCE(IntEnum):
    EMPTY      = 0b0000
    ADC        = 0b0111
    ASP_RX_CH1 = 0b1101
    ASP_RX_CH2 = 0b1110

class R_BUS_DAC_SRC(Register8):
    CHB = 7, 4, E_BUS_SOURCE
    CHA = 3, 0, E_BUS_SOURCE

class R_BUS_ASP_TX_SRC(Register8):
    CH2 = 7, 4, E_BUS_SOURCE
    CH1 = 3, 0, E_BUS_SOURCE

class E_HSBIAS_SENSE_TRIP(IntEnum):
    C_12UA  = 0b000
    C_23UA  = 0b001
    C_41UA  = 0b010
    C_52UA  = 0b011
    C_64UA  = 0b100
    C_75UA  = 0b101
    C_93UA  = 0b110
    C_104UA = 0b111

class R_HSBIAS_SC_AUTOCTL(Register8):
    HSBIAS_SENSE_EN = 7
    AUTO_HSBIAS_HIZ = 6
    TIP_SENSE_EN    = 5
    SENSE_TRIP      = 2, 0, E_HSBIAS_SENSE_TRIP

class E_TIP_SENSE_CTRL(IntEnum):
    DISABLED  = 0b00
    DIG_INPUT = 0b01
    SHORT_DET = 0b11

class R_TIP_SENSE_CTRL2(Register8):
    CTRL = 7, 6, E_TIP_SENSE_CTRL
    INV  = 5

class E_HSBIAS_DET_MODE(IntEnum):
    DISABLED  = 0b00
    SHORT_DET = 0b01
    NORMAL    = 0b11

class E_HSBIAS_CTRL(IntEnum):
    HI_Z  = 0b00
    U_0V0 = 0b01
    U_2V0 = 0b10
    U_2V7 = 0b11

class R_MISC_DET_CTRL(Register8):
    UNK1            = 7
    DETECT_MODE     = 4, 3, E_HSBIAS_DET_MODE
    HSBIAS_CTRL     = 2, 1, E_HSBIAS_CTRL
    PDN_MIC_LVL_DET = 0

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

class R_HS_DET_CTRL2(Register8):
    CTRL      = 7, 6
    SET       = 5, 4
    REF       = 3
    AUTO_TIME = 1, 0

class R_HS_SWITCH_CTRL(Register8):
    REF_HS3      = 7
    REF_HS4      = 6
    HSB_FILT_HS3 = 5
    HSB_FILT_HS4 = 4
    HSB_HS3      = 3
    HSB_HS4      = 2
    GNDHS_HS3    = 1
    GNDHS_HS4    = 0

class R_ASP_CTRL(Register8):
    TDM_MODE = 2
    BCLK_EN  = 1

class R_ASP_FSYNC_CTRL23(Register16):
    BCLK_PERIOD = 12, 1

class R_ASP_TX_HIZ_DLY_CTRL(Register8):
    DRV_Z     = 5, 4
    HIZ_DELAY = 3, 2
    FS        = 1
    UNK1      = 0

class R_ASP_RX_EN(Register8):
    CH2_EN = 1
    CH1_EN = 0

class R_ASP_CH_CTRL(Register32):
    WIDTH      = 23, 16
    SLOT_START = 10, 1
    EDGE       = 0 # set for rising edge

class CS42L84Regs(RegMap):
    DEVID  = irange(0x0, 5), Register8
    FREEZE = 0x6, Register8

    SW_RESET = 0x203, Register8

    IRQ_STATUS1     = 0x400, R_IRQ_MASK1
    IRQ_STATUS2     = 0x401, Register8
    IRQ_STATUS3     = 0x402, R_IRQ_MASK3
    PLL_LOCK_STATUS = 0x40e, Register8 # bit 0x10

    IRQ_MASK1  = 0x418, R_IRQ_MASK1
    IRQ_MASK2  = 0x419, Register8
    IRQ_MASK3  = 0x41a, R_IRQ_MASK3

    CCM_CTRL1        = 0x600, R_CCM_CTRL1
    CCM_SAMP_RATE    = 0x601, R_CCM_SAMP_RATE
    CCM_CTRL3        = 0x602, R_CCM_CTRL3
    CCM_CTRL4        = 0x603, R_CCM_CTRL4
    CCM_ASP_CLK_CTRL = 0x608, Register8

    PLL_CTRL     = 0x800, R_PLL_CTRL
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
    WAKE_CTRL         = 0x1471, Register8
    TIP_SENSE_CTRL2   = 0x1473, R_TIP_SENSE_CTRL2
    MISC_DET_CTRL     = 0x1474, R_MISC_DET_CTRL
    MIC_DET_CTRL2     = 0x1478, R_MIC_DET_CTRL2
    MIC_DET_CTRL4     = 0x1477, R_MIC_DET_CTRL4

    HS_DET_STATUS1    = 0x147c, Register8
    HS_DET_STATUS2    = 0x147d, R_HS_DET_STATUS2
    HS_DET_IRQ_MASK   = irange(0x1480, 2), Register8
    HS_DET_IRQ_STATUS = irange(0x1484, 2), Register8

    MSM_BLOCK_EN1    = 0x1800, R_MSM_BLOCK_EN1
    MSM_BLOCK_EN2    = 0x1801, R_MSM_BLOCK_EN2
    MSM_BLOCK_EN3    = 0x1802, R_MSM_BLOCK_EN3

    HS_DET_CTRL1     = 0x1810, Register8
    HS_DET_CTRL2     = 0x1811, R_HS_DET_CTRL2
    HS_SWITCH_CTRL   = 0x1812, R_HS_SWITCH_CTRL
    HS_CLAMP_DISABLE = 0x1813, R_HS_CLAMP_DISABLE
    ADC_CTRL1        = 0x2000, R_ADC_CTRL1
    ADC_CTRL2        = 0x2001, Register8 # volume
    ADC_CTRL3        = 0x2002, Register8
    ADC_CTRL4        = 0x2003, R_ADC_CTRL4

    DAC_CTRL1     = 0x3000, R_DAC_CTRL1
    DAC_CTRL2     = 0x3001, R_DAC_CTRL2
    DACA_VOL_LSB  = 0x3004, Register8
    DACA_VOL_MSB  = 0x3005, Register8 # sign bit
    DACB_VOL_LSB  = 0x3006, Register8
    DACB_VOL_MSB  = 0x3007, Register8 # sign bit
    HP_VOL_CTRL   = 0x3020, R_HP_VOL_CTRL
    HP_CLAMP_CTRL = 0x3123, Register8

    BUS_ASP_TX_SRC = 0x4000, R_BUS_ASP_TX_SRC
    BUS_DAC_SRC    = 0x4001, R_BUS_DAC_SRC

    ASP_CTRL         = 0x5000, R_ASP_CTRL
    ASP_FSYNC_CTRL23 = 0x5010, R_ASP_FSYNC_CTRL23
    ASP_DATA_CTRL    = 0x5018, R_ASP_TX_HIZ_DLY_CTRL

    ASP_RX_EN = 0x5020, R_ASP_RX_EN
    ASP_TX_EN = 0x5024, Register8

    ASP_RX1_CTRL     = 0x5028, R_ASP_CH_CTRL # 32bit
    ASP_RX2_CTRL     = 0x502c, R_ASP_CH_CTRL # 32bit
    ASP_TX1_CTRL     = 0x5068, R_ASP_CH_CTRL
    ASP_TX2_CTRL     = 0x506c, R_ASP_CH_CTRL

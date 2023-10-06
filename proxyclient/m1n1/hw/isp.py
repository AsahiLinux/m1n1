# SPDX-License-Identifier: MIT
from ..utils import *

class ISP_REVISION(Register32):
    REVISION = 15, 0

class ISPRegs(RegMap):
    ISP_PMGR_0 = 0x738, Register32
    ISP_PMGR_1 = 0x798, Register32
    ISP_PMGR_2 = 0x7f8, Register32
    ISP_PMGR_3 = 0x858, Register32

    ISP_ASC_RVBAR   = 0x1050000, Register64
    ISP_ASC_EDPRCR  = 0x1010310, Register32
    ISP_ASC_CONTROL = 0x1400044, Register32
    ISP_ASC_STATUS  = 0x1400048, Register32

    ISP_ASC_POWER_CYCLE_0 = 0x1400a00, Register32
    ISP_ASC_POWER_CYCLE_1 = 0x1400a04, Register32
    ISP_ASC_POWER_CYCLE_2 = 0x1400a08, Register32
    ISP_ASC_POWER_CYCLE_3 = 0x1400a0c, Register32
    ISP_ASC_POWER_CYCLE_4 = 0x1400a10, Register32
    ISP_ASC_POWER_CYCLE_5 = 0x1400a14, Register32

    ISP_REVISION = 0x1800000, ISP_REVISION

    ISP_POWER_UNK_0 = 0x20e0080, Register32
    ISP_POWER_UNK_1 = 0x20f0020, Register32
    ISP_POWER_UNK_2 = 0x20f8020, Register32

    ISP_GPIO_0 = 0x2104170, Register32
    ISP_GPIO_1 = 0x2104174, Register32
    ISP_GPIO_2 = 0x2104178, Register32
    ISP_GPIO_3 = 0x210417c, Register32
    ISP_GPIO_4 = 0x2104180, Register32
    ISP_GPIO_5 = 0x2104184, Register32
    ISP_GPIO_6 = 0x2104188, Register32
    ISP_GPIO_7 = 0x210418c, Register32

    ISP_GPIO_0_T8112 = 0x24c41b0, Register32
    ISP_GPIO_1_T8112 = 0x24c41b4, Register32
    ISP_GPIO_2_T8112 = 0x24c41b8, Register32
    ISP_GPIO_3_T8112 = 0x24c41bc, Register32
    ISP_GPIO_4_T8112 = 0x24c41c0, Register32
    ISP_GPIO_5_T8112 = 0x24c41c4, Register32
    ISP_GPIO_6_T8112 = 0x24c41c8, Register32
    ISP_GPIO_7_T8112 = 0x24c41cc, Register32

    ISP_SENSOR_CLOCK_0_EN = 0x2104190, Register32
    ISP_SENSOR_CLOCK_1_EN = 0x2104194, Register32
    ISP_SENSOR_CLOCK_2_EN = 0x2104198, Register32

    ISP_IRQ_INTERRUPT   = 0x2104000, Register32
    ISP_IRQ_ENABLE      = 0x2104004, Register32
    ISP_IRQ_DOORBELL    = 0x21043f0, Register32
    ISP_IRQ_ACK         = 0x21043fc, Register32
    ISP_IRQ_INTERRUPT_T8112 = 0x24c4000, Register32
    ISP_IRQ_DOORBELL_T8112 = 0x24c4430, Register32
    ISP_IRQ_ACK_T8112   = 0x24c443c, Register32

    ISP_IRQ_INTERRUPT_1 = 0x2104008, Register32
    ISP_IRQ_INTERRUPT_2 = 0x2104010, Register32
    ISP_IRQ_INTERRUPT_3 = 0x2104018, Register32
    ISP_IRQ_INTERRUPT_4 = 0x21043f8, Register32
    ISP_IRQ_INTERRUPT_4_T8112 = 0x24c4438, Register32

    ISP_DPE_UNK_0 = 0x2504000, Register32
    ISP_DPE_UNK_1 = 0x2508000, Register32

class ISPPSRegs(RegMap):  # This doesn't really make sense
    ISP_PS_00 = 0x4000, Register32
    ISP_PS_08 = 0x4008, Register32
    ISP_PS_10 = 0x4010, Register32
    ISP_PS_18 = 0x4018, Register32
    ISP_PS_20 = 0x4020, Register32
    ISP_PS_28 = 0x4028, Register32
    ISP_PS_30 = 0x4030, Register32
    ISP_PS_38 = 0x4038, Register32
    ISP_PS_40 = 0x4040, Register32
    ISP_PS_48 = 0x4048, Register32
    ISP_PS_50 = 0x4050, Register32
    ISP_PS_58 = 0x4058, Register32
    ISP_PS_60 = 0x4060, Register32

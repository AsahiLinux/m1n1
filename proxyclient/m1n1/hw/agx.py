# SPDX-License-Identifier: MIT
from ..utils import *
from enum import IntEnum

__all__ = ["SGXRegs", "SGXRegsT602X", "SGXInfoRegs", "agx_decode_unit", "R_FAULT_INFO"]

class FAULT_REASON(IntEnum):
    INVALID = 0
    AF_FAULT = 1
    WRITE_ONLY = 2
    READ_ONLY = 3
    NO_ACCESS = 4
    UNK = 5

class R_FAULT_INFO(Register64):
    ADDR        = 63, 30
    SIDEBAND    = 29, 23
    CONTEXT     = 22, 17
    UNIT        = 16, 9
    LEVEL       = 8, 7
    UNK_5       = 6, 5
    READ        = 4
    REASON      = 3, 1, FAULT_REASON
    FAULTED     = 0

class SGXRegs(RegMap):
    FAULT_INFO      = 0x17030, R_FAULT_INFO

class SGXRegsT602X(RegMap):
    FAULT_INFO      = 0xd8c0, R_FAULT_INFO
    FAULT_ADDR      = 0xd8c8, Register64

class SGXInfoRegs(RegMap):
    CORE_MASK_0     = 0x1500, Register32,
    CORE_MASK_1     = 0x1514, Register32,

    ID_00           = 0x4000, Register32,
    ID_04           = 0x4004, Register32,
    ID_08           = 0x4008, Register32,
    ID_0c           = 0x400c, Register32,
    ID_10           = 0x4010, Register32,
    ID_14           = 0x4014, Register32,
    ID_18           = 0x4018, Register32,
    ID_1c           = 0x401c, Register32,

    ID_8024         = 0x8024, Register32,

class UNIT_00(IntEnum):
    DCMPn           = 0x00 # VDM/PDM/CDM
    UL1Cn           = 0x01 # VDM/PDM/CDM
    CMPn            = 0x02 # VDM/PDM/CDM
    GSL1_n          = 0x03 # VDM/PDM/CDM
    IAPn            = 0x04 # VDM/PDM/CDM
    VCEn            = 0x05 # VDM
    TEn             = 0x06 # VDM
    RASn            = 0x07 # VDM
    VDMn            = 0x08 # VDM
    PPPn            = 0x09 # VDM
    IPFn            = 0x0a # PDM
    IPF_CPFn        = 0x0b # PDM
    VFn             = 0x0c # PDM
    VF_CPFn         = 0x0d # PDM
    ZLSn            = 0x0e # PDM

class UNIT_A0(IntEnum):
    dPM             = 0xa1 # VDM/PDM/CDM
    dCDM_KS0        = 0xa2 # CDM
    dCDM_KS1        = 0xa3 # CDM
    dCDM_KS2        = 0xa4 # CDM
    dIPP            = 0xa5 # PDM
    dIPP_CS         = 0xa6 # PDM
    dVDM_CSD        = 0xa7 # VDM
    dVDM_SSD        = 0xa8 # VDM
    dVDM_ILF        = 0xa9 # VDM
    dVDM_ILD        = 0xaa # VDM
    dRDE0           = 0xab # VDM/PDM/CDM
    dRDE1           = 0xac # VDM/PDM/CDM
    FC              = 0xad # VDM/PDM/CDM
    GSL2            = 0xae # VDM/PDM/CDM

    GL2CC_META0     = 0xb0 # VDM/PDM/CDM
    GL2CC_META1     = 0xb1 # VDM/PDM/CDM
    GL2CC_META2     = 0xb2 # VDM/PDM/CDM
    GL2CC_META3     = 0xb3 # VDM/PDM/CDM
    GL2CC_META4     = 0xb4 # VDM/PDM/CDM
    GL2CC_META5     = 0xb5 # VDM/PDM/CDM
    GL2CC_META6     = 0xb6 # VDM/PDM/CDM
    GL2CC_META7     = 0xb7 # VDM/PDM/CDM
    GL2CC_MB        = 0xb8 # VDM/PDM/CDM

class UNIT_D0_T602X(IntEnum):
    gCDM_CS         = 0xd0 # CDM
    gCDM_ID         = 0xd1 # CDM
    gCDM_CSR        = 0xd2 # CDM
    gCDM_CSW        = 0xd3 # CDM
    gCDM_CTXR       = 0xd4 # CDM
    gCDM_CTXW       = 0xd5 # CDM
    gIPP            = 0xd6 # PDM
    gIPP_CS         = 0xd7 # PDM
    gKSM_RCE        = 0xd8 # VDM/PDM/CDM

class UNIT_E0_T602X(IntEnum):
    gPM_SPn         = 0xe0 # VDM/PDM/CDM
    gVDM_CSD_SPn    = 0xe1 # VDM
    gVDM_SSD_SPn    = 0xe2 # VDM
    gVDM_ILF_SPn    = 0xe3 # VDM
    gVDM_TFP_SPn    = 0xe4 # VDM
    gVDM_MMB_SPn    = 0xe5 # VDM
    gRDE_SPn        = 0xe6 # VDM/PDM/CDM

class UNIT_E0_T8103(IntEnum):
    gPM_SPn         = 0xe0 # VDM/PDM/CDM
    gVDM_CSD_SPn    = 0xe1 # VDM
    gVDM_SSD_SPn    = 0xe2 # VDM
    gVDM_ILF_SPn    = 0xe3 # VDM
    gVDM_TFP_SPn    = 0xe4 # VDM
    gVDM_MMB_SPn    = 0xe5 # VDM
    gCDM_CS_SPn_KS0 = 0xe6 # CDM
    gCDM_CS_SPn_KS1 = 0xe7 # CDM
    gCDM_CS_SPn_KS2 = 0xe8 # CDM
    gCDM_SPn_KS0    = 0xe9 # CDM
    gCDM_SPn_KS1    = 0xea # CDM
    gCDM_SPn_KS2    = 0xeb # CDM
    gIPP_SPn        = 0xec # PDM
    gIPP_CS_SPn     = 0xed # PDM
    gRDE0_SPn       = 0xee # VDM/PDM/CDM
    gRDE1_SPn       = 0xef # VDM/PDM/CDM

def agx_decode_unit(v):
    if v < 0xa0:
        group = v >> 4
        return UNIT_00(v & 0x0f).name.replace("n", str(group))
    elif v < 0xd0:
        return UNIT_A0(v).name
    elif v < 0xe0:
        return UNIT_D0_T602X(v).name
    else:
        group = (v >> 4) & 1
        return UNIT_E0_T8103(v & 0xef).name.replace("n", str(group))

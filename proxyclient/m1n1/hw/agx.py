# SPDX-License-Identifier: MIT
from ..utils import *
from enum import IntEnum

__all__ = ["SGXRegs", "SGXInfoRegs", "agx_decode_unit", "R_FAULT_INFO"]

class FAULT_REASON(IntEnum):
    INVALID = 0
    AF_FAULT = 1
    WRITE_ONLY = 2
    READ_ONLY = 3
    NO_ACCESS = 4
    UNK = 5

class R_FAULT_INFO(Register64):
    ADDR        = 63, 24
    WRITE       = 23
    CONTEXT     = 22, 17
    UNIT        = 16, 9
    UNK_8       = 8
    REASON      = 3, 1, FAULT_REASON
    FAULTED     = 0

class SGXRegs(RegMap):
    FAULT_INFO      = 0x17030, R_FAULT_INFO

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
    DCMPn           = 0x00
    UL1Cn           = 0x01
    CMPn            = 0x02
    GSL1_n          = 0x03
    IAPn            = 0x04
    VCEn            = 0x05
    TEn             = 0x06
    RASn            = 0x07
    VDMn            = 0x08
    PPPn            = 0x09
    IPFn            = 0x0a
    IPF_CPFn        = 0x0b
    VFn             = 0x0c
    VF_CPFn         = 0x0d
    ZLSn            = 0x0e

class UNIT_A0(IntEnum):
    dPM             = 0xa1
    dCDM_KS0        = 0xa2
    dCDM_KS1        = 0xa3
    dCDM_KS2        = 0xa4
    dIPP            = 0xa5
    dIPP_CS         = 0xa6
    dVDM_CSD        = 0xa7
    dVDM_SSD        = 0xa8
    dVDM_ILF        = 0xa9
    dVDM_ILD        = 0xaa
    dRDE0           = 0xab
    dRDE1           = 0xac
    FC              = 0xad
    GSL2            = 0xae

    GL2CC_META0     = 0xb0
    GL2CC_META1     = 0xb1
    GL2CC_META2     = 0xb2
    GL2CC_META3     = 0xb3
    GL2CC_META4     = 0xb4
    GL2CC_META5     = 0xb5
    GL2CC_META6     = 0xb6
    GL2CC_META7     = 0xb7
    GL2CC_MB        = 0xb8

class UNIT_E0(IntEnum):
    gPM_SPn         = 0xe0
    gVDM_CSD_SPn    = 0xe1
    gVDM_SSD_SPn    = 0xe2
    gVDM_ILF_SPn    = 0xe3
    gVDM_TFP_SPn    = 0xe4
    gVDM_MMB_SPn    = 0xe5
    gCDM_CS_SPn_KS0 = 0xe6
    gCDM_CS_SPn_KS1 = 0xe7
    gCDM_CS_SPn_KS2 = 0xe8
    gCDM_SPn_KS0    = 0xe9
    gCDM_SPn_KS1    = 0xea
    gCDM_SPn_KS2    = 0xeb
    gIPP_SPn        = 0xec
    gIPP_CS_SPn     = 0xed
    gRDE0_SPn       = 0xee
    gRDE1_SPn       = 0xef

def agx_decode_unit(v):
    if v < 0xa0:
        group = v >> 4
        return UNIT_00(v & 0x0f).name.replace("n", str(group))
    elif v < 0xe0:
        return UNIT_A0(v).name
    else:
        group = (v >> 4) & 1
        return UNIT_E0(v & 0xef).name.replace("n", str(group))

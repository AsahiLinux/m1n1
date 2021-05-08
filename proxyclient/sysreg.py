#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import json, os
from enum import IntEnum
from utils import Register64, Register32

def load_registers():
    data = json.load(open(os.path.join(os.path.dirname(__file__), "..", "tools", "arm_regs.json")))
    for reg in data:
        yield reg["name"], tuple(reg["enc"])

sysreg_fwd = dict(load_registers())
sysreg_rev = {v: k for k, v in sysreg_fwd.items()}
globals().update(sysreg_fwd)

class ESR_EC(IntEnum):
    UNKNOWN        = 0b000000
    WFI            = 0b000001
    FP_TRAP        = 0b000111
    PAUTH_TRAP     = 0b001000
    LS64           = 0b001010
    BTI            = 0b001101
    ILLEGAL        = 0b001110
    SVC            = 0b010101
    HVC            = 0b010110
    SMC            = 0b010111
    MSR            = 0b011000
    SVE            = 0b011001
    PAUTH_FAIL     = 0b011100
    IABORT_LOWER   = 0b100000
    IABORT         = 0b100001
    PC_ALIGN       = 0b100010
    DABORT_LOWER   = 0b100100
    DABORT         = 0b100101
    SP_ALIGN       = 0b100110
    FP_EXC         = 0b101100
    SERROR         = 0b101111
    BKPT_LOWER     = 0b110000
    BKPT           = 0b110001
    SSTEP_LOWER    = 0b110010
    SSTEP          = 0b110011
    WATCH_LOWER    = 0b110100
    WATCH          = 0b110101
    BRK            = 0b111100
    IMPDEF         = 0b111111

class MSR_DIR(IntEnum):
    WRITE = 0
    READ = 1

class ESR_ISS_MSR(Register32):
    Op0 = 21, 20
    Op2 = 19, 17
    Op1 = 16, 14
    CRn = 13, 10
    Rt = 9, 5
    CRm = 4, 1
    DIR = 0, 0, MSR_DIR

class DABORT_DFSC(IntEnum):
    ASIZE_L0         = 0b000000
    ASIZE_L1         = 0b000001
    ASIZE_L2         = 0b000010
    ASIZE_L3         = 0b000011
    XLAT_L0          = 0b000100
    XLAT_L1          = 0b000101
    XLAT_L2          = 0b000110
    XLAT_L3          = 0b000111
    AF_L0            = 0b001000
    AF_L1            = 0b001001
    AF_L2            = 0b001010
    AF_L3            = 0b001011
    PERM_L0          = 0b001100
    PERM_L1          = 0b001101
    PERM_L2          = 0b001110
    PERM_L3          = 0b001111
    EABORT           = 0b010000
    TAG_CHECK        = 0b010001
    PT_EABORT_Lm1    = 0b010011
    PT_EABORT_L0     = 0b010100
    PT_EABORT_L1     = 0b010101
    PT_EABORT_L2     = 0b010110
    PT_EABORT_L3     = 0b010111
    ECC_ERROR        = 0b011000
    PT_ECC_ERROR_Lm1 = 0b011011
    PT_ECC_ERROR_L0  = 0b011100
    PT_ECC_ERROR_L1  = 0b011101
    PT_ECC_ERROR_L2  = 0b011110
    PT_ECC_ERROR_L3  = 0b011111
    ALIGN            = 0b100001
    ASIZE_Lm1        = 0b101001
    XLAT_Lm1         = 0b101011
    TLB_CONFLICT     = 0b110000
    UNSUPP_ATOMIC    = 0b110001
    IMPDEF_LOCKDOWN  = 0b110100
    IMPDEF_ATOMIC    = 0b110101

class ESR_ISS_DABORT(Register32):
    ISV = 24
    SAS = 23, 22
    SSE = 21
    SRT = 20, 16
    SF = 15
    AR = 14
    VNCR = 13
    SET = 12, 11
    LSR = 12, 11
    FnV = 10
    EA = 9
    CM = 8
    S1PTR = 7
    WnR = 6
    DFSC = 5, 0, DABORT_DFSC

class ESR(Register64):
    ISS2 = 36, 32
    EC = 31, 26, ESR_EC
    IL = 25
    ISS = 24, 0

class SPSR_M(IntEnum):
    EP0t = 0
    EL1t = 4
    EL1h = 5
    EL2t = 8
    EL2h = 9

class SPSR(Register64):
    N = 31
    Z = 30
    C = 29
    V = 28
    TCO = 25
    DIT = 24
    UAO = 23
    PAN = 22
    SS = 21
    IL = 20
    SSBS = 12
    BTYPE = 11, 10
    D = 9
    A = 8
    I = 7
    F = 6
    M = 4, 0, SPSR_M


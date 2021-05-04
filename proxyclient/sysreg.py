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

class MSR_DIR(IntEnum):
    WRITE = 0
    READ = 1

class ESR_ISS_MSR(Register32):
    Op0 = 21, 20
    Op2 = 19, 17
    Op1 = 16, 14
    CRn = 13, 10
    Rt = 9, 5
    CRm = 3, 1
    DIR = 0, 0, MSR_DIR

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


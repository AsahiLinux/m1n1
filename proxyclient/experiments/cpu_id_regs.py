#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.sysreg import MIDR

# generated via
# grep -e ' | [A-Z][A-Z0-9]' -e ' [0-9]\+) ID_AA64' Documentation/arch/arm64/cpu-feature-registers.rst | \
# cut -d'|' -f1-3 | \
# sed -e 's/^     |/   /; s/ \+|/ =/' \
#     -e 's/\[\([0-9]\+\)-\([0-9]\+\)\]/\1, \2/' \
#     -e 's/ \+$//; s/-/#/' \
#     -e 's/^.*\(ID_AA64.*\)_EL1/class \1(Register64):/'

class ID_AA64ISAR0(Register64): # Instruction Set Attribute Register 0
    RNDR = 63, 60
    TS = 55, 52
    FHM = 51, 48
    DP = 47, 44
    SM4 = 43, 40
    SM3 = 39, 36
    SHA3 = 35, 32
    RDM = 31, 28
    ATOMICS = 23, 20
    CRC32 = 19, 16
    SHA2 = 15, 12
    SHA1 = 11, 8
    AES = 7, 4

class ID_AA64PFR0(Register64): # Processor Feature Register 0
    DIT = 51, 48
    MPAM = 43, 40
    SVE = 35, 32
    GIC = 27, 24
    FP = 19, 16
    EL3 = 15, 12
    EL2 = 11, 8
    EL1 = 7, 4
    EL0 = 3, 0

class ID_AA64PFR1(Register64): # Processor Feature Register 1
    SME = 27, 24
    MTE = 11, 8
    SSBS = 7, 4
    BT = 3, 0

class ID_AA64ISAR1(Register64): # Instruction set attribute register 1
    I8MM = 55, 52
    DGH = 51, 48
    BF16 = 47, 44
    SB = 39, 36
    FRINTTS = 35, 32
    GPI = 31, 28
    GPA = 27, 24
    LRCPC = 23, 20
    FCMA = 19, 16
    JSCVT = 15, 12
    API = 11, 8
    APA = 7, 4
    DPB = 3, 0

class ID_AA64MMFR0(Register64): # Memory model feature register 0
    ECV = 63, 60

class ID_AA64MMFR2(Register64): # Memory model feature register 2
    AT = 35, 32

class ID_AA64ZFR0(Register64): # SVE feature ID register 0
    F64MM = 59, 56
    F32MM = 55, 52
    I8MM = 47, 44
    SM4 = 43, 40
    SHA3 = 35, 32
    B16B16 = 27, 24
    BF16 = 23, 20
    AES = 7, 4
    SVEVer = 3, 0

class ID_AA64MMFR1(Register64): # Memory model feature register 1
    AFP = 47, 44

class ID_AA64ISAR2(Register64): # Instruction set attribute register 2
    CSSC = 55, 52
    RPRFM = 51, 48
    BC = 23, 20
    MOPS = 19, 16
    APA3 = 15, 12
    GPA3 = 11, 8
    RPRES = 7, 4
    WFXT = 3, 0

class ID_AA64AFR0(Register64): # Auxiliary Feature Register 0
    pass

class ID_AA64AFR1(Register64): # Auxiliary Feature Register 1
    pass

class ID_AA64DFR0(Register64): # Debug Feature Register 0
    # HPMN0 = 63, 60
    # ExtTrcBuff = 59, 56
    # BRBE = 55, 52
    # MTPMU = 51, 48
    # TraceBuffer = 47, 44
    # TraceFilt = 43, 40
    # DoubleLock = 39, 36
    PMSVer = 35, 32
    CTX_CMPs = 31, 28
    WRPs = 23, 20
    PMSS = 19, 16
    BRPs = 15, 12
    PMUVer = 11, 8
    TraceVer = 7, 4
    DebugVer = 3, 0

class ID_AA64DFR1(Register64): # Debug Feature Register 1
    pass

class ID_AA64FPFR0(Register64): # Floating-point Feature Register 0
    pass

class ID_AA64ISAR3(Register64): # Instruction set attribute register 3
    pass

class ID_AA64MMFR3(Register64): # Memory model feature register 4
    pass

class ID_AA64MMFR4(Register64): # Memory model feature register 4
    pass

class ID_AA64PFR2(Register64): # Processor Feature Register 2
    pass

class ID_AA64SMFR0(Register64): # SME Feature ID Register 0
    FA64 = 63
    LUTv2 = 60
    SMEver = 59, 56
    I16I64 = 55, 52
    F64F64 = 48
    I16I32 = 47, 44
    B16B16 = 43
    F16F16 = 42
    F8F16 = 41
    F8F32 = 40
    I8I32 = 39, 36
    F16F32 = 35
    B16F32 = 34
    BI32I32 = 33
    F32F32 = 32
    SF8FMA = 30
    SF8DP4 = 29
    SF8DP2 = 28
    SBitPerm = 25
    AES = 24
    SFEXPA = 23
    STMOP = 16
    SMOP4 = 0


# ID registers ordered in the same way as Documentation/arch/arm64/cpu-feature-registers.rst in the
# Linux kernel source excluding AArch32 registers
id_regs = dict([
    ("ID_AA64ISAR0_EL1", (ID_AA64ISAR0_EL1, ID_AA64ISAR0)),
    ("ID_AA64PFR0_EL1",  (ID_AA64PFR0_EL1,  ID_AA64PFR0)),
    ("ID_AA64PFR1_EL1",  (ID_AA64PFR1_EL1,  ID_AA64PFR1)),
    ("MIDR_EL1",         (MIDR_EL1,         MIDR)),
    ("ID_AA64ISAR1_EL1", (ID_AA64ISAR1_EL1, ID_AA64ISAR1)),
    ("ID_AA64MMFR0_EL1", (ID_AA64MMFR0_EL1, ID_AA64MMFR0)),
    ("ID_AA64MMFR2_EL1", (ID_AA64MMFR2_EL1, ID_AA64MMFR2)),
    ("ID_AA64ZFR0_EL1",  ((3, 0, 0, 4, 4),  ID_AA64ZFR0)),
    ("ID_AA64MMFR1_EL1", (ID_AA64MMFR1_EL1, ID_AA64MMFR1)),
    ("ID_AA64ISAR2_EL1", (ID_AA64ISAR2_EL1, ID_AA64ISAR2)),

    ("ID_AA64AFR0_EL1",  (ID_AA64AFR0_EL1, ID_AA64AFR0)),
    ("ID_AA64AFR1_EL1",  (ID_AA64AFR1_EL1, ID_AA64AFR1)),
    ("ID_AA64DFR0_EL1",  (ID_AA64DFR0_EL1, ID_AA64DFR0)),
    ("ID_AA64DFR1_EL1",  (ID_AA64DFR1_EL1, ID_AA64DFR1)),
    ("ID_AA64FPFR0_EL1", ((3, 0, 0, 4, 7), ID_AA64FPFR0)),
    ("ID_AA64ISAR3_EL1", ((3, 0, 0, 6, 3), ID_AA64ISAR3)),
    ("ID_AA64MMFR3_EL1", ((3, 0, 0, 7, 3), ID_AA64MMFR3)),
    ("ID_AA64MMFR4_EL1", ((3, 0, 0, 7, 4), ID_AA64MMFR4)),
    ("ID_AA64PFR2_EL1",  ((3, 0, 0, 4, 2), ID_AA64PFR2)),
    ("ID_AA64SMFR0_EL1", ((3, 0, 0, 4, 5), ID_AA64SMFR0)),
])

for name, (ident, reg) in id_regs.items():
    value = reg(u.mrs(ident))
    print(f"{name}: {value}")

# SPDX-License-Identifier: MIT
import json, os, re
from enum import Enum, IntEnum, IntFlag
from .utils import Register, Register64, Register32

__all__ = ["sysreg_fwd", "sysreg_rev"]

def _load_registers():
    global sysreg_fwd, sysop_fwd

    sysreg_fwd = {}
    sysop_fwd = {}
    for fname in ["arm_regs.json", "apple_regs.json"]:
        data = json.load(open(os.path.join(os.path.dirname(__file__), "..", "..", "tools", fname)))
        for reg in data:
            if "accessors" in reg:
                for acc in reg["accessors"]:
                    if acc in ("MRS", "MSR"):
                        sysreg_fwd[reg["name"]] = tuple(reg["enc"])
                    else:
                        sysop_fwd[acc + " " + reg["name"]] = tuple(reg["enc"])
            else:
                sysreg_fwd[reg["name"]] = tuple(reg["enc"])

_load_registers()
sysreg_rev = {v: k for k, v in sysreg_fwd.items()}
sysop_rev = {v: k for k, v in sysop_fwd.items()}
sysop_fwd_id = {k.replace(" ", "_"): v for k,v in sysop_fwd.items()}

globals().update(sysreg_fwd)
__all__.extend(sysreg_fwd.keys())
globals().update(sysop_fwd_id)
__all__.extend(sysop_fwd_id.keys())

def sysreg_name(enc):
    if enc in sysreg_rev:
        return sysreg_rev[enc]
    if enc in sysop_rev:
        return sysop_rev[enc]
    return f"s{enc[0]}_{enc[1]}_c{enc[2]}_c{enc[3]}_{enc[4]}"

def sysreg_parse(s):
    if isinstance(s, tuple) or isinstance(s, list):
        return tuple(s)
    s = s.strip()
    for r in (r"s(\d+)_(\d+)_c(\d+)_c(\d+)_(\d+)", r"(\d+), *(\d+), *(\d+), *(\d+), *(\d+)"):
        if m := re.match(r, s):
            enc = tuple(map(int, m.groups()))
            break
    else:
        for i in sysreg_fwd, sysop_fwd, sysop_fwd_id:
            try:
                enc = i[s]
            except KeyError:
                continue
            break
        else:
            raise Exception(f"Unknown sysreg name {s}")
    return enc

def DBGBCRn_EL1(n):
    return (2,0,0,n,5)

def DBGBVRn_EL1(n):
    return (2,0,0,n,4)

def DBGWCRn_EL1(n):
    return (2,0,0,n,7)

def DBGWVRn_EL1(n):
    return (2,0,0,n,6)

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
    EL0t = 0
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

class ACTLR(Register64):
    EnMDSB  = 12
    EnPRSV  = 6
    EnAFP   = 5
    EnAPFLG = 4
    DisHWP  = 3
    EnTSO   = 1

class HCR(Register64):
    TWEDEL   = 63, 60
    TWEDEn   = 59
    TID5     = 58
    DCT      = 57
    ATA      = 56
    TTLBOS   = 55
    TTLBIS   = 54
    EnSCXT   = 53
    TOCU     = 52
    AMVOFFEN = 51
    TICAB    = 50
    TID4     = 49
    FIEN     = 47
    FWB      = 46
    NV2      = 45
    AT       = 44
    NV1      = 43
    NV       = 42
    API      = 41
    APK      = 40
    MIOCNCE  = 38
    TEA      = 37
    TERR     = 36
    TLOR     = 35
    E2H      = 34
    ID       = 33
    CD       = 32
    RW       = 31
    TRVM     = 30
    HCD      = 29
    TDZ      = 28
    TGE      = 27
    TVM      = 26
    TTLB     = 25
    TPU      = 24
    TPCP     = 23
    TPC      = 23
    TSW      = 22
    TACR     = 21
    TIDCP    = 20
    TSC      = 19
    TID3     = 18
    TID2     = 17
    TID1     = 16
    TID0     = 15
    TWE      = 14
    TWI      = 13
    DC       = 12
    BSU      = 11, 10
    FB       = 9
    VSE      = 8
    VI       = 7
    VF       = 6
    AMO      = 5
    IMO      = 4
    FMO      = 3
    PTW      = 2
    SWIO     = 1
    VM       = 0

class HACR(Register64):
    TRAP_CPU_EXT = 0
    TRAP_AIDR = 4
    TRAP_AMX = 10
    TRAP_SPRR = 11
    TRAP_GXF = 13
    TRAP_CTRR = 14
    TRAP_IPI = 16
    TRAP_s3_4_c15_c5z6_x = 18
    TRAP_s3_4_c15_c0z12_5 = 19
    GIC_CNTV = 20
    TRAP_s3_4_c15_c10_4 = 25
    TRAP_SERROR_INFO = 48
    TRAP_EHID = 49
    TRAP_HID = 50
    TRAP_s3_0_c15_c12_1z2 = 51
    TRAP_ACC = 52
    TRAP_PM = 57
    TRAP_UPM = 58
    TRAP_s3_1z7_c15_cx_3 = 59

class AMX_CTL(Register64):
    EN = 63
    EN_EL1 = 62

class MDCR(Register64):
    TDE = 8
    TDA = 9
    TDOSA = 10
    TDRA = 11

class MDSCR(Register64):
    SS = 0
    MDE = 15

class DBGBCR(Register32):
    BT = 23, 20
    LBN = 16, 16
    SSC = 15, 14
    HMC = 13
    BAS = 8,5
    PMC = 2,1
    E = 0

class DBGWCR_LSC(IntFlag):
    L = 1
    S = 2

class DBGWCR(Register32):
    SSCE = 29
    MASK = 28, 24
    WT = 20
    LBN = 19, 16
    SSC = 15, 14
    HMC = 13
    BAS = 12, 5
    LSC = 4, 3
    PAC = 2, 1
    E = 0

# TCR_EL1
class TCR(Register64):
    DS = 59
    TCMA1 = 58
    TCMA0 = 57
    E0PD1 = 56
    E0PD0 = 55
    NFD1 = 54
    NFD0 = 53
    TBID1 = 52
    TBID0 = 51
    HWU162 = 50
    HWU161 = 49
    HWU160 = 48
    HWU159 = 47
    HWU062 = 46
    HWU061 = 45
    HWU060 = 44
    HWU059 = 43
    HPD1 = 42
    HPD0 = 41
    HD = 40
    HA = 39
    TBI1 = 38
    TBI0 = 37
    AS = 36
    IPS = 34, 32
    TG1 = 31, 30
    SH1 = 29, 28
    ORGN1 = 27, 26
    IRGN1 = 25, 24
    EPD1 = 23
    A1 = 22
    T1SZ = 21, 16
    TG0 = 15, 14
    SH0 = 13, 12
    ORGN0 = 11, 10
    IRGN0 = 9, 8
    EPD0 = 7
    T0SZ = 5, 0

class TLBI_RVA(Register64):
    ASID = 63, 48
    TG = 47, 46
    SCALE = 45, 44
    NUM = 43, 39
    TTL = 38, 37
    BaseADDR = 36, 0

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)

# SPDX-License-Identifier: GPL-2.0-or-later
import array

from .. import sysreg
from .sprr import HV_VREGS, HVC_SYSREG_FLAG

__all__ = ["patch_impdef_to_hvc", "SHADOW_REGS", "HVC_SPTM_SYSREG"]

HVC_SPTM_SYSREG = 0x4000  # | reg << 6 | is_read << 5 | Rt

# remap to register that can be read from EL1 where possible
RENAME = {
    "TPIDR_EL2": "TPIDR_EL1",
    "CPTR_EL2": "CPACR_EL1",
    "CNTV_CTL_EL02": "CNTV_CTL_EL0",
    "CNTV_CVAL_EL02": "CNTV_CVAL_EL0",
    "CNTP_CTL_EL02": "CNTP_CTL_EL0",
    "CNTP_CVAL_EL02": "CNTP_CVAL_EL0",
}

# map directly to existing SPRR vregs to keep the GXF/SPRR emulation working
VREG_MAP = {
    "AFSR1_GL2": "AFSR1_GL1",
    "ELR_EL2": "ELR_EL1",
    "SPSR_EL2": "SPSR_EL1",
    "ESR_EL2": "ESR_EL1",
    "FAR_EL2": "FAR_EL1",
    "SPRR_UPERM_EL02": "SPRR_UPERM_EL0",
}

# HVC register indices; must match enum hv_sptm_reg in src/hv/hv_sptm.h.
SHADOW_REGS = [
    sysreg.HCR_EL2,
    sysreg.HCRX_EL2,
    sysreg.HACR_EL2,
    sysreg.MDCR_EL2,
    sysreg.VPIDR_EL2,
    sysreg.VMPIDR_EL2,
    sysreg.SCTLR_EL12,
    sysreg.ACTLR_EL12_PRE,
    sysreg.CPACR_EL12,
    sysreg.TTBR0_EL12,
    sysreg.TTBR1_EL12,
    sysreg.TCR_EL12,
    sysreg.MAIR_EL12,
    sysreg.AMAIR_EL12,
    sysreg.VTTBR_EL2,
    sysreg.VTCR_EL2,
    sysreg.VMSA_LOCK_EL1,
    sysreg.VMSA_LOCK_EL12,
    sysreg.VBAR_EL12,
    sysreg.ELR_EL12,
    sysreg.SPSR_EL12,
    sysreg.ESR_EL12,
    sysreg.FAR_EL12,
    sysreg.AFSR0_EL12,
    sysreg.AFSR1_EL12,
    sysreg.AFSR1_EL2,
    sysreg.HPFAR_EL2,
    sysreg.VBAR_GL12,
    sysreg.SP_GL12,
    sysreg.TPIDR_GL2,
    sysreg.CONTEXTIDR_EL12,
    sysreg.SCXTNUM_EL0,
    sysreg.SCXTNUM_EL12,
    sysreg.ICH_HCR_EL2,
    sysreg.ICH_VMCR_EL2,
    sysreg.CNTVOFF_EL2,
    sysreg.CNTKCTL_EL12,
    sysreg.VM_TMR_FIQ_ENA_EL2,
    sysreg.AGTCNTRDIR_EL1,
    sysreg.AGTCNTRDIR_EL12,
    sysreg.GXF_CONFIG_EL12,
    sysreg.GXF_ENTRY_EL12,
    sysreg.GXF_PABENTRY_EL12,
    sysreg.SPRR_CONFIG_EL12,
    sysreg.SPRR_UMPRR_EL12,
    sysreg.SPRR_PMPRR_EL12,
    sysreg.SPRR_AMRANGE_EL12,
    sysreg.SPRR_PPERM_EL12,
    sysreg.SPRR_UPERM_SH1_EL12,
    sysreg.SPRR_UPERM_SH2_EL12,
    sysreg.SPRR_UPERM_SH3_EL12,
    sysreg.SPRR_PPERM_SH1_EL12,
    sysreg.SPRR_PPERM_SH2_EL12,
    sysreg.SPRR_PPERM_SH3_EL12,
    sysreg.CTRR_CTL_EL12,
    sysreg.CTRR_LOCK_EL12,
    sysreg.CTRR_A_CTL_EL1,
    sysreg.CTRR_A_LWR_EL12,
    sysreg.CTRR_A_UPR_EL12,
    sysreg.CTRR_A_LWR_EL2,
    sysreg.CTRR_A_UPR_EL2,
    sysreg.ACC_CTRR_A_CTL_EL2,
    sysreg.CTRR_B_CTL_EL1,
    sysreg.CTRR_B_LWR_EL12,
    sysreg.CTRR_B_UPR_EL12,
    sysreg.ACC_CTRR_B_CTL_EL2,
    sysreg.CTRR_C_LWR_EL1,
    sysreg.CTRR_C_UPR_EL1,
    sysreg.CTRR_C_CTL_EL1,
    sysreg.CTRR_C_LWR_EL12,
    sysreg.CTRR_C_UPR_EL12,
    sysreg.CTRR_C_CTL_EL12,
    sysreg.ACC_CTRR_C_LWR_EL2,
    sysreg.ACC_CTRR_C_UPR_EL2,
    sysreg.ACC_CTRR_C_CTL_EL2,
    sysreg.CTRR_D_LWR_EL1,
    sysreg.CTRR_D_UPR_EL1,
    sysreg.CTRR_D_CTL_EL1,
    sysreg.CTRR_D_LWR_EL12,
    sysreg.CTRR_D_UPR_EL12,
    sysreg.CTRR_D_CTL_EL12,
    sysreg.CTRR_D_LWR_EL2,
    sysreg.CTRR_D_UPR_EL2,
    sysreg.ACC_CTRR_D_LWR_EL2,
    sysreg.ACC_CTRR_D_UPR_EL2,
    sysreg.ACC_CTRR_D_CTL_EL2,
    sysreg.CTXR_A_LWR_EL1,
    sysreg.CTXR_A_UPR_EL1,
    sysreg.CTXR_A_CTL_EL1,
    sysreg.CTXR_A_LWR_EL12,
    sysreg.CTXR_A_UPR_EL12,
    sysreg.CTXR_A_CTL_EL12,
    sysreg.ACC_CTXR_A_LWR_EL2,
    sysreg.ACC_CTXR_A_UPR_EL2,
    sysreg.ACC_CTXR_A_CTL_EL2,
    sysreg.CTXR_B_LWR_EL1,
    sysreg.CTXR_B_UPR_EL1,
    sysreg.CTXR_B_CTL_EL1,
    sysreg.CTXR_B_LWR_EL12,
    sysreg.CTXR_B_UPR_EL12,
    sysreg.CTXR_B_CTL_EL12,
    sysreg.ACC_CTXR_B_LWR_EL2,
    sysreg.ACC_CTXR_B_UPR_EL2,
    sysreg.ACC_CTXR_B_CTL_EL2,
    sysreg.CTXR_C_LWR_EL1,
    sysreg.CTXR_C_UPR_EL1,
    sysreg.CTXR_C_CTL_EL1,
    sysreg.CTXR_C_LWR_EL12,
    sysreg.CTXR_C_UPR_EL12,
    sysreg.CTXR_C_CTL_EL12,
    sysreg.ACC_CTXR_C_LWR_EL2,
    sysreg.ACC_CTXR_C_UPR_EL2,
    sysreg.ACC_CTXR_C_CTL_EL2,
    sysreg.CTXR_D_LWR_EL1,
    sysreg.CTXR_D_UPR_EL1,
    sysreg.CTXR_D_CTL_EL1,
    sysreg.CTXR_D_LWR_EL12,
    sysreg.CTXR_D_UPR_EL12,
    sysreg.CTXR_D_CTL_EL12,
    sysreg.ACC_CTXR_D_LWR_EL2,
    sysreg.ACC_CTXR_D_UPR_EL2,
    sysreg.ACC_CTXR_D_CTL_EL2,
    sysreg.VMKEYLO_EL2,
    sysreg.VMKEYHI_EL2,
    sysreg.KERNKEYLO_EL1,
    sysreg.KERNKEYHI_EL1,
    sysreg.KERNKEYLO_EL12,
    sysreg.KERNKEYHI_EL12,
    sysreg.APGAKeyLo_EL12,
    sysreg.APGAKeyHi_EL12,
    sysreg.APIAKeyLo_EL12,
    sysreg.APIAKeyHi_EL12,
    sysreg.APIBKeyLo_EL12,
    sysreg.APIBKeyHi_EL12,
    sysreg.APDAKeyLo_EL12,
    sysreg.APDAKeyHi_EL12,
    sysreg.APDBKeyLo_EL12,
    sysreg.APDBKeyHi_EL12,
    sysreg.AMX_CTL_EL2,
    sysreg.AMX_CONFIG_EL1,
    sysreg.AMX_CONFIG_EL12,
    sysreg.AMX_STATE_EL12,
    sysreg.APCTL_EL1,
    sysreg.APSTS_EL1,
    sysreg.APCTL_EL12,
    sysreg.APSTS_EL12,
    sysreg.PMCR1_GL1,
    sysreg.JCTL_EL0,
    (2, 1, 9, 8, 0),
    (2, 4, 6, 1, 6),
    (3, 1, 15, 0, 3),
    (3, 1, 15, 0, 5),
    (3, 1, 15, 1, 3),
    (3, 1, 15, 1, 6),
    (3, 1, 15, 2, 3),
    (3, 1, 15, 7, 2),
    (3, 1, 15, 7, 4),
    (3, 1, 15, 9, 4),
    (3, 1, 15, 13, 4),
    (3, 1, 15, 15, 4),
    (3, 2, 13, 8, 2),
    (3, 4, 1, 2, 5),
    (3, 4, 15, 0, 1),
    (3, 4, 15, 4, 1),
    (3, 4, 15, 4, 3),
    (3, 4, 15, 4, 4),
    (3, 4, 15, 9, 6),
    (3, 4, 15, 9, 7),
    (3, 4, 15, 10, 0),
    (3, 4, 15, 10, 1),
    (3, 4, 15, 10, 2),
    (3, 4, 15, 10, 3),
    (3, 4, 15, 10, 7),
    (3, 4, 15, 12, 0),
    (3, 4, 15, 12, 6),
    (3, 4, 15, 13, 6),
    (3, 4, 15, 13, 7),
    (3, 4, 15, 14, 0),
    (3, 4, 15, 14, 1),
    (3, 4, 15, 14, 2),
    (3, 4, 15, 14, 3),
    (3, 4, 15, 15, 1),
    (3, 4, 15, 15, 2),
    (3, 4, 15, 15, 4),
    (3, 4, 15, 15, 5),
    (3, 5, 15, 3, 6),
    (3, 5, 15, 3, 7),
    (3, 5, 15, 6, 2),
    (3, 5, 15, 11, 2),
    (3, 6, 15, 0, 4),
    (3, 6, 15, 0, 5),
    (3, 6, 15, 1, 1),
    (3, 6, 15, 8, 5),
    (3, 6, 15, 12, 7),
    (3, 7, 3, 14, 1),
    (3, 7, 15, 1, 3),
    (3, 7, 15, 3, 3),
    (3, 7, 15, 5, 0),
    (3, 7, 15, 5, 3),
    (3, 7, 15, 7, 3),
    (3, 7, 15, 9, 3),
]


def _msr(enc, read):
    op0, op1, crn, crm, op2 = enc
    return (0xd5000000 | (read << 21) | (1 << 20) | ((op0 & 1) << 19) | (op1 << 16) |
            (crn << 12) | (crm << 8) | (op2 << 5))


def _hvc(imm):
    return 0xd4000002 | (imm << 5)


def _enc(name):
    if isinstance(name, tuple):
        return name
    return getattr(sysreg, name)


RENAME_OPCODES = {}
for _src, _dst in RENAME.items():
    for _rd in (0, 1):
        RENAME_OPCODES[_msr(_enc(_src), _rd)] = _msr(_enc(_dst), _rd)

SHADOW_OPCODES = {_msr(enc, rd): (i, rd) for i, enc in enumerate(SHADOW_REGS) for rd in (0, 1)}

VREG_OPCODES = {_msr(_enc(src), rd): (HV_VREGS.index(_enc(dst)), rd) for src, dst in VREG_MAP.items() for rd in (0, 1)}


def patch_impdef_to_hvc(data, log=None):
    a = array.array("I", data)
    renamed = shadowed = vregs = 0

    for i, w in enumerate(a):
        if w >> 24 != 0xd5:
            continue

        masked = w & ~0x1f
        dst = RENAME_OPCODES.get(masked)
        if dst is not None:
            a[i] = dst | (w & 0x1f)
            renamed += 1
            continue

        hit = VREG_OPCODES.get(masked)
        if hit is not None:
            reg, rd = hit
            a[i] = _hvc(HVC_SYSREG_FLAG | (reg << 6) | (rd << 5) | (w & 0x1f))
            vregs += 1
            continue

        hit = SHADOW_OPCODES.get(masked)
        if hit is not None:
            reg, rd = hit
            a[i] = _hvc(HVC_SPTM_SYSREG | (reg << 6) | (rd << 5) | (w & 0x1f))
            shadowed += 1
            continue

    if log:
        log(f"  IMPDEF patcher: {renamed} renamed, {shadowed} shadowed, {vregs} vregs")

    return a.tobytes()

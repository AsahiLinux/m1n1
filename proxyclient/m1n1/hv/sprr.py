# SPDX-License-Identifier: GPL-2.0-or-later
import array

from .. import sysreg
from ..sysreg import sysreg_encode

__all__ = ["patch_text_sprr_emu", "HV_VREGS"]

# Must be kept in sync with enum hv_vreg in src/hv/hv_sprr.h (vreg_id = index).
HV_VREGS = [
    # SPRR
    sysreg.SPRR_AMRANGE_EL1,
    sysreg.SPRR_AMRANGE_EL12,
    sysreg.SPRR_CONFIG_EL1,
    sysreg.SPRR_CONFIG_EL12,
    sysreg.SPRR_UPERM_EL0,
    sysreg.SPRR_PPERM_EL1,
    sysreg.SPRR_PMPRR_EL1,
    sysreg.SPRR_PMPRR_EL12,
    sysreg.SPRR_PPERM_EL12,
    sysreg.SPRR_PPERM_SH1_EL1,
    sysreg.SPRR_PPERM_SH1_EL12,
    sysreg.SPRR_PPERM_SH2_EL1,
    sysreg.SPRR_PPERM_SH2_EL12,
    sysreg.SPRR_PPERM_SH3_EL1,
    sysreg.SPRR_PPERM_SH3_EL12,
    sysreg.SPRR_UMPRR_EL1,
    sysreg.SPRR_UMPRR_EL12,
    sysreg.SPRR_UPERM_SH1_EL1,
    sysreg.SPRR_UPERM_SH1_EL12,
    sysreg.SPRR_UPERM_SH2_EL1,
    sysreg.SPRR_UPERM_SH2_EL12,
    sysreg.SPRR_UPERM_SH3_EL1,
    sysreg.SPRR_UPERM_SH3_EL12,

    # GXF
    sysreg.GXF_PABENTRY_EL1,
    sysreg.GXF_CONFIG_EL1,
    sysreg.GXF_CONFIG_EL12,
    sysreg.GXF_ENTRY_EL1,
    sysreg.GXF_ENTRY_EL12,
    sysreg.GXF_PABENTRY_EL12,
    sysreg.GXF_STATUS_EL1,

    # Exception state
    sysreg.AFSR0_EL12,
    sysreg.AFSR1_EL1,
    sysreg.AFSR1_EL12,
    sysreg.AFSR1_EL2,
    sysreg.AFSR1_GL1,
    sysreg.ASPSR_EL1,
    sysreg.ASPSR_GL1,
    sysreg.ELR_EL1,
    sysreg.ELR_EL12,
    sysreg.ELR_GL1,
    sysreg.ESR_EL1,
    sysreg.ESR_EL12,
    sysreg.ESR_GL1,
    sysreg.FAR_EL1,
    sysreg.FAR_EL12,
    sysreg.FAR_GL1,
    sysreg.HPFAR_EL2,
    sysreg.SPSR_EL1,
    sysreg.SPSR_EL12,
    sysreg.SPSR_GL1,
    sysreg.SP_GL12,
    sysreg.TPIDR_GL1,
    sysreg.TPIDR_GL2,
    sysreg.VBAR_EL1,
    sysreg.VBAR_EL12,
    sysreg.VBAR_GL1,
    sysreg.VBAR_GL12,

    # MMU and Virtualization
    sysreg.ACTLR_EL12_PRE,
    sysreg.AMAIR_EL12,
    sysreg.CONTEXTIDR_EL12,
    sysreg.CPACR_EL12,
    sysreg.HACR_EL2,
    sysreg.HCRX_EL2,
    sysreg.HCR_EL2,
    sysreg.ICH_HCR_EL2,
    sysreg.ICH_VMCR_EL2,
    sysreg.MAIR_EL12,
    sysreg.MDCR_EL2,
    sysreg.SCTLR_EL1,
    sysreg.SCTLR_EL12,
    sysreg.SCXTNUM_EL0,
    sysreg.SCXTNUM_EL12,
    sysreg.TCR_EL1,
    sysreg.TCR_EL12,
    sysreg.TTBR0_EL1,
    sysreg.TTBR0_EL12,
    sysreg.TTBR1_EL1,
    sysreg.TTBR1_EL12,
    sysreg.VMPIDR_EL2,
    sysreg.VPIDR_EL2,
    sysreg.VTCR_EL2,
    sysreg.VTTBR_EL2,

    # Timers
    sysreg.AGTCNTRDIR_EL1,
    sysreg.AGTCNTRDIR_EL12,
    sysreg.APL_CNTV_CTL_EL0,
    sysreg.APL_CNTV_TVAL_EL0,
    sysreg.CNTKCTL_EL12,
    sysreg.CNTVOFF_EL2,
    sysreg.VM_TMR_FIQ_ENA_EL2,

    # CTxR
    sysreg.CTRR_A_CTL_EL1,
    sysreg.ACC_CTRR_A_CTL_EL2,
    sysreg.CTRR_A_LWR_EL12,
    sysreg.CTRR_A_LWR_EL2,
    sysreg.CTRR_A_UPR_EL12,
    sysreg.CTRR_A_UPR_EL2,
    sysreg.CTRR_B_CTL_EL1,
    sysreg.ACC_CTRR_B_CTL_EL2,
    sysreg.CTRR_B_LWR_EL12,
    sysreg.CTRR_B_UPR_EL12,
    sysreg.CTRR_CTL_EL12,
    sysreg.CTRR_C_CTL_EL1,
    sysreg.CTRR_C_CTL_EL12,
    sysreg.ACC_CTRR_C_CTL_EL2,
    sysreg.CTRR_C_LWR_EL1,
    sysreg.CTRR_C_LWR_EL12,
    sysreg.ACC_CTRR_C_LWR_EL2,
    sysreg.CTRR_C_UPR_EL1,
    sysreg.CTRR_C_UPR_EL12,
    sysreg.ACC_CTRR_C_UPR_EL2,
    sysreg.CTRR_D_CTL_EL1,
    sysreg.CTRR_D_CTL_EL12,
    sysreg.ACC_CTRR_D_CTL_EL2,
    sysreg.CTRR_D_LWR_EL1,
    sysreg.CTRR_D_LWR_EL12,
    sysreg.CTRR_D_LWR_EL2,
    sysreg.ACC_CTRR_D_LWR_EL2,
    sysreg.CTRR_D_UPR_EL1,
    sysreg.CTRR_D_UPR_EL12,
    sysreg.CTRR_D_UPR_EL2,
    sysreg.ACC_CTRR_D_UPR_EL2,
    sysreg.CTRR_LOCK_EL12,
    sysreg.CTXR_A_CTL_EL1,
    sysreg.CTXR_A_CTL_EL12,
    sysreg.ACC_CTXR_A_CTL_EL2,
    sysreg.CTXR_A_LWR_EL1,
    sysreg.CTXR_A_LWR_EL12,
    sysreg.ACC_CTXR_A_LWR_EL2,
    sysreg.CTXR_A_UPR_EL1,
    sysreg.CTXR_A_UPR_EL12,
    sysreg.ACC_CTXR_A_UPR_EL2,
    sysreg.CTXR_B_CTL_EL1,
    sysreg.CTXR_B_CTL_EL12,
    sysreg.ACC_CTXR_B_CTL_EL2,
    sysreg.CTXR_B_LWR_EL1,
    sysreg.CTXR_B_LWR_EL12,
    sysreg.ACC_CTXR_B_LWR_EL2,
    sysreg.CTXR_B_UPR_EL1,
    sysreg.CTXR_B_UPR_EL12,
    sysreg.ACC_CTXR_B_UPR_EL2,
    sysreg.CTXR_C_CTL_EL1,
    sysreg.CTXR_C_CTL_EL12,
    sysreg.ACC_CTXR_C_CTL_EL2,
    sysreg.CTXR_C_LWR_EL1,
    sysreg.CTXR_C_LWR_EL12,
    sysreg.ACC_CTXR_C_LWR_EL2,
    sysreg.CTXR_C_UPR_EL1,
    sysreg.CTXR_C_UPR_EL12,
    sysreg.ACC_CTXR_C_UPR_EL2,
    sysreg.CTXR_D_CTL_EL1,
    sysreg.CTXR_D_CTL_EL12,
    sysreg.ACC_CTXR_D_CTL_EL2,
    sysreg.CTXR_D_LWR_EL1,
    sysreg.CTXR_D_LWR_EL12,
    sysreg.ACC_CTXR_D_LWR_EL2,
    sysreg.CTXR_D_UPR_EL1,
    sysreg.CTXR_D_UPR_EL12,
    sysreg.ACC_CTXR_D_UPR_EL2,
    sysreg.VMSA_LOCK_EL1,
    sysreg.VMSA_LOCK_EL12,

    # PAC
    sysreg.APCTL_EL1,
    sysreg.APCTL_EL12,
    sysreg.APDAKeyHi_EL12,
    sysreg.APDAKeyLo_EL12,
    sysreg.APDBKeyHi_EL12,
    sysreg.APDBKeyLo_EL12,
    sysreg.APGAKeyHi_EL12,
    sysreg.APGAKeyLo_EL12,
    sysreg.APIAKeyHi_EL12,
    sysreg.APIAKeyLo_EL12,
    sysreg.APIBKeyHi_EL12,
    sysreg.APIBKeyLo_EL12,
    sysreg.APSTS_EL1,
    sysreg.APSTS_EL12,
    sysreg.KERNKEYHI_EL1,
    sysreg.KERNKEYHI_EL12,
    sysreg.KERNKEYLO_EL1,
    sysreg.KERNKEYLO_EL12,
    sysreg.VMKEYHI_EL2,
    sysreg.VMKEYLO_EL2,

    # AMX
    sysreg.AMX_CONFIG_EL1,
    sysreg.AMX_CONFIG_EL12,
    sysreg.AMX_CTL_EL2,
    sysreg.AMX_STATE_EL12,

    # Misc
    sysreg.JCTL_EL0,
    sysreg.PMCR1_GL1,

    # Unknown
    (2, 1, 9, 8, 0),
    (2, 4, 6, 1, 6),
    (3, 1, 15, 0, 3),
    (3, 1, 15, 13, 4),
    (3, 1, 15, 1, 3),
    (3, 1, 15, 1, 6),
    (3, 1, 15, 2, 3),
    (3, 1, 15, 7, 2),
    (3, 1, 15, 7, 4),
    (3, 1, 15, 9, 4),
    (3, 2, 13, 8, 2),
    (3, 4, 15, 0, 1),
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
    (3, 4, 15, 4, 1),
    (3, 4, 15, 4, 3),
    (3, 4, 15, 4, 4),
    (3, 4, 15, 9, 6),
    (3, 4, 15, 9, 7),
    (3, 4, 1, 2, 5),
    (3, 5, 15, 11, 2),
    (3, 5, 15, 3, 6),
    (3, 5, 15, 3, 7),
    (3, 5, 15, 6, 2),
    (3, 6, 15, 0, 4),
    (3, 6, 15, 0, 5),
    (3, 6, 15, 12, 7),
    (3, 6, 15, 1, 1),
    (3, 6, 15, 8, 5),
    (3, 7, 15, 1, 3),
    (3, 7, 15, 3, 3),
    (3, 7, 15, 5, 0),
    (3, 7, 15, 5, 3),
    (3, 7, 15, 7, 3),
    (3, 7, 15, 9, 3),
    (3, 7, 3, 14, 1),
]

# remap to register that can either be read from EL1 or is emulated
REMAP = {
    sysreg.TPIDR_EL2: sysreg.TPIDR_EL1,
    # This is quite a hack: SPTM uses CPTR_EL2 to en-/dis-able FP which just happens to
    # be at the same bits like CPACR_EL1. This is probably gonna bite us sooner or later
    # but the alternative is keeping track of FP state across SPTM/XNU transitions and
    # that's fairly annoying. Maybe we'll need this once we add support for secure kernel.
    sysreg.CPTR_EL2: sysreg.CPACR_EL1,
    sysreg.CNTV_CTL_EL02: sysreg.CNTV_CTL_EL0,
    sysreg.CNTV_CVAL_EL02: sysreg.CNTV_CVAL_EL0,
    sysreg.CNTP_CTL_EL02: sysreg.CNTP_CTL_EL0,
    sysreg.CNTP_CVAL_EL02: sysreg.CNTP_CVAL_EL0,
    sysreg.AFSR1_GL2: sysreg.AFSR1_GL1,
    sysreg.ELR_EL2: sysreg.ELR_EL1,
    sysreg.SPSR_EL2: sysreg.SPSR_EL1,
    sysreg.ESR_EL2: sysreg.ESR_EL1,
    sysreg.FAR_EL2: sysreg.FAR_EL1,
    sysreg.SPRR_UPERM_EL02: sysreg.SPRR_UPERM_EL0,
}

GENTER = 0x00201420
GEXIT = 0x00201400
GXF_TLBI_ALL = 0x00201401
GXF_TLBI_WITH_ARG = 0x00201300
GXF_TLBI_WITH_ARG_MASK = 0xffffffc0

HVC_SYSREG_FLAG = 0x8000


def _hvc(imm):
    return 0xd4000002 | (imm << 5)


# MSR/MRS opcode (Rt masked) -> (replacement opcode, Rt shift)
_SYSREG = {
    sysreg_encode(enc, rd): (_hvc(HVC_SYSREG_FLAG | (i << 6) | (rd << 5)), 5)
    for i, enc in enumerate(HV_VREGS) for rd in (0, 1)
}
for src, dst in REMAP.items():
    for rd in (0, 1):
        opcode = sysreg_encode(dst, rd)
        _SYSREG[sysreg_encode(src, rd)] = _SYSREG.get(opcode, (opcode, 0))


def patch_text_sprr_emu(data):
    a = array.array("I", data)

    for i, w in enumerate(a):
        if w & 0xfffffff0 == GENTER:
            a[i] = _hvc(w & 0xffff)
        elif w == GXF_TLBI_ALL or w & GXF_TLBI_WITH_ARG_MASK == GXF_TLBI_WITH_ARG:
            a[i] = _hvc(w & 0xffff)
        elif w == GEXIT:
            a[i] = _hvc(GEXIT & 0xffff)
        else:
            hit = _SYSREG.get(w & ~0x1f)
            if hit is None:
                continue
            opcode, rt_shift = hit
            a[i] = opcode | ((w & 0x1f) << rt_shift)

    return a.tobytes()

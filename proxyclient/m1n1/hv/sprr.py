# SPDX-License-Identifier: MIT
import array

from .. import sysreg

__all__ = ["patch_text_sprr_emu", "HV_VREGS"]

# Must be kept in sync with enum hv_vreg in src/hv_sprr.h (vreg_id = index).
HV_VREGS = [
    sysreg.SPRR_CONFIG_EL1,
    sysreg.GXF_CONFIG_EL1,
    sysreg.GXF_STATUS_EL1,
    sysreg.GXF_ENTRY_EL1,
    sysreg.GXF_PABENTRY_EL1,
    sysreg.SPRR_UPERM_EL0,
    sysreg.SPRR_PPERM_EL1,
    sysreg.TPIDR_GL1,
    sysreg.VBAR_GL1,
    sysreg.SPSR_GL1,
    sysreg.ASPSR_GL1,
    sysreg.ESR_GL1,
    sysreg.ELR_GL1,
    sysreg.FAR_GL1,
    sysreg.AFSR1_GL1,
    sysreg.ASPSR_EL1,
    sysreg.SPRR_UMPRR_EL1,
    sysreg.TTBR0_EL1,
    sysreg.TTBR1_EL1,
    sysreg.TCR_EL1,
    sysreg.SCTLR_EL1,
]

GENTER = 0x00201420
GEXIT = 0x00201400

HVC_SYSREG_FLAG = 0x8000


def _msr(enc, read):
    op0, op1, crn, crm, op2 = enc
    return (0xd5000000 | (read << 21) | ((op0 & 3) << 19) | (op1 << 16) | (crn << 12) |
            (crm << 8) | (op2 << 5))


def _hvc(imm):
    return 0xd4000002 | (imm << 5)


# MSR/MRS opcode (Rt masked) -> (vreg_id, read)
_SYSREG = {_msr(enc, rd): (i, rd) for i, enc in enumerate(HV_VREGS) for rd in (0, 1)}


def patch_text_sprr_emu(data, log=None):
    a = array.array("I", data)
    genter = gexit = sysreg_ = 0

    for i, w in enumerate(a):
        if w >> 16 == GENTER >> 16:
            if w & 0xfffffff0 == GENTER:  # genter #imm; bit5 set distinguishes gexit
                a[i] = _hvc(w & 0xffff)
                genter += 1
            elif w == GEXIT:
                a[i] = _hvc(GEXIT & 0xffff)
                gexit += 1
            continue
        if w >> 24 != 0xd5:
            continue
        hit = _SYSREG.get(w & ~0x1f)
        if hit is not None:
            vreg, rd = hit
            a[i] = _hvc(HVC_SYSREG_FLAG | (vreg << 6) | (rd << 5) | (w & 0x1f))
            sysreg_ += 1

    if log:
        log(f"  {genter} genter, {gexit} gexit, {sysreg_} sysreg patched")

    return a.tobytes()

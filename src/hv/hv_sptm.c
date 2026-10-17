/* SPDX-License-Identifier: GPL-2.0-or-later */

#include "hv_sptm.h"
#include "cpu_regs.h"
#include "hv.h"
#include "smp.h"
#include "string.h"
#include "utils.h"

struct hv_sptm_cpu {
    u64 timer_deadline;
    u64 shadow[HV_SPTM_MAX];
};

static struct hv_sptm_cpu sptm_cpus[MAX_CPUS];

static u64 apple_timer_now(void)
{
    return mrs(SYS_IMP_APL_CNTVCT_ALIAS_EL0);
}

bool hv_sptm_timer_pending(void)
{
    struct hv_sptm_cpu *cpu = &sptm_cpus[smp_id()];

    if (hv_sptm_mode != SPTM_EMULATION)
        return false;
    if (!(cpu->shadow[HV_SPTM_APL_CNTV_CTL_EL0] & CNTx_CTL_ENABLE))
        return false;
    if (cpu->shadow[HV_SPTM_APL_CNTV_CTL_EL0] & CNTx_CTL_IMASK)
        return false;

    return (s64)(cpu->timer_deadline - apple_timer_now()) <= 0;
}

void hv_sptm_timer_arm(void)
{
    struct hv_sptm_cpu *cpu = &sptm_cpus[smp_id()];

    if (hv_sptm_mode != SPTM_EMULATION)
        return;
    if (!(cpu->shadow[HV_SPTM_APL_CNTV_CTL_EL0] & CNTx_CTL_ENABLE))
        return;
    if (cpu->shadow[HV_SPTM_APL_CNTV_CTL_EL0] & CNTx_CTL_IMASK)
        return;

    /* Check if the guest's timer has already expired */
    s64 apple_delta = cpu->timer_deadline - apple_timer_now();
    if (apple_delta <= 0) {
        hv_update_fiq();
        return;
    }

    /* Scale the guest's Apple timer (24 MHz on M4 Pro) to host timer ticks (1GHz on M4 Pro) */
    u64 host_ticks = DIV_ROUND_UP(apple_delta * mrs(CNTFRQ_EL0), mrs(SYS_IMP_APL_CNTFRQ_EL0));
    u64 host_now = mrs(CNTPCT_EL0);
    s64 host_remaining = mrs(CNTP_CVAL_EL0) - host_now;

    /* Make sure we don't postpone m1n1's timer */
    if (host_remaining <= 0)
        return;
    if (host_ticks >= (u64)host_remaining)
        return;
    msr(CNTP_CVAL_EL0, host_now + host_ticks);
    sysop("isb");
}

static const u8 sptm_protection_regs[] = {
    HV_SPTM_CTRR_C_LWR_EL1,     HV_SPTM_CTRR_C_UPR_EL1,     HV_SPTM_CTRR_C_CTL_EL1,
    HV_SPTM_CTRR_D_LWR_EL1,     HV_SPTM_CTRR_D_UPR_EL1,     HV_SPTM_CTRR_D_CTL_EL1,
    HV_SPTM_CTXR_A_LWR_EL1,     HV_SPTM_CTXR_A_UPR_EL1,     HV_SPTM_CTXR_A_CTL_EL1,
    HV_SPTM_CTXR_B_LWR_EL1,     HV_SPTM_CTXR_B_UPR_EL1,     HV_SPTM_CTXR_B_CTL_EL1,
    HV_SPTM_CTXR_C_LWR_EL1,     HV_SPTM_CTXR_C_UPR_EL1,     HV_SPTM_CTXR_C_CTL_EL1,
    HV_SPTM_CTXR_D_LWR_EL1,     HV_SPTM_CTXR_D_UPR_EL1,     HV_SPTM_CTXR_D_CTL_EL1,
    HV_SPTM_CTRR_A_CTL_EL1,     HV_SPTM_CTRR_B_CTL_EL1,     HV_SPTM_ACC_CTRR_A_CTL_EL2,
    HV_SPTM_ACC_CTRR_B_CTL_EL2, HV_SPTM_ACC_CTRR_C_CTL_EL2, HV_SPTM_ACC_CTRR_D_CTL_EL2,
    HV_SPTM_ACC_CTXR_A_CTL_EL2, HV_SPTM_ACC_CTXR_B_CTL_EL2, HV_SPTM_ACC_CTXR_C_CTL_EL2,
    HV_SPTM_ACC_CTXR_D_CTL_EL2,
};

static void sptm_init_cpu(int i)
{
    memset(&sptm_cpus[i], 0, sizeof(sptm_cpus[i]));

    /* SPTM either panics or gets stuck in a polling loop if any bit here isn't set */
    sptm_cpus[i].shadow[HV_SPTM_HCR_EL2] = HCR_RW | HCR_E2H | HCR_APK | HCR_API;
    sptm_cpus[i].shadow[HV_SPTM_APSTS_EL1] = 1;

    /* SPTM expects CTRR to be enabled and locked */
    sptm_cpus[i].shadow[HV_SPTM_CTRR_A_CTL_EL1] = 0x8000000000000001;
    sptm_cpus[i].shadow[HV_SPTM_CTRR_B_CTL_EL1] = 0x8000000000000001;
    sptm_cpus[i].shadow[HV_SPTM_ACC_CTRR_A_CTL_EL2] = 0x8000000000000001;
    sptm_cpus[i].shadow[HV_SPTM_ACC_CTRR_B_CTL_EL2] = 0x8000000000000001;
    sptm_cpus[i].shadow[HV_SPTM_ACC_CTRR_C_CTL_EL2] = 0x8000000000000001;
    sptm_cpus[i].shadow[HV_SPTM_ACC_CTRR_D_CTL_EL2] = 0x8000000000000001;

    /*
     * This is another set of CTRR registers and presumably these values mean
     * at least enabled and locked as well. SPTM will panic if it finds anything
     * different in here.
     */
    sptm_cpus[i].shadow[HV_SPTM_ACC_CTXR_A_CTL_EL2] = 0xc000000000aa019a;
    sptm_cpus[i].shadow[HV_SPTM_ACC_CTXR_B_CTL_EL2] = 0xc0000000009a02aa;
    sptm_cpus[i].shadow[HV_SPTM_ACC_CTXR_C_CTL_EL2] = 0xc000000000aa026a;
    sptm_cpus[i].shadow[HV_SPTM_ACC_CTXR_D_CTL_EL2] = 0xc000000000aa02a9;
}

void hv_sptm_init(void)
{
    for (int i = 0; i < MAX_CPUS; i++)
        sptm_init_cpu(i);
}

void hv_sptm_init_secondary(int cpu)
{
    for (u32 i = 0; i < ARRAY_SIZE(sptm_protection_regs); i++)
        sptm_cpus[cpu].shadow[sptm_protection_regs[i]] =
            sptm_cpus[boot_cpu_idx].shadow[sptm_protection_regs[i]];
}

#define VREG_MASKED_ALIAS(vreg_id, shadow_id, mask)                                                \
    case vreg_id:                                                                                  \
        if (is_read)                                                                               \
            rval = cpu->shadow[shadow_id];                                                         \
        else                                                                                       \
            cpu->shadow[shadow_id] = wval & (mask);                                                \
        break

#define VREG_MASKED(vreg_id, mask) VREG_MASKED_ALIAS(vreg_id, vreg_id, mask)

bool hv_sptm_dispatch(struct exc_info *ctx, u16 imm)
{
    if (hv_sptm_mode != SPTM_EMULATION)
        return false;
    if (imm < HV_HVC_SPTM_SYSREG)
        return false;
    if (imm >= HV_HVC_SPTM_SYSREG + FIELD_PREP(HV_HVC_SPTM_REG, HV_SPTM_MAX))
        return false;

    struct hv_sptm_cpu *cpu = &sptm_cpus[smp_id()];
    u32 reg = FIELD_GET(HV_HVC_SPTM_REG, imm);
    u32 rt = FIELD_GET(HV_HVC_SPTM_RT, imm);
    bool is_read = imm & HV_HVC_SPTM_DIR;

    ctx->regs[31] = 0;

    u64 wval = ctx->regs[rt];
    u64 rval = 0;

    switch (reg) {
        /*
         * SPTM writes the end address, then reads it back and checks if the lower bits are
         * cleared. It accesses the _EL12 variants but doesn't validate them but we might need
         * that once we add support for "secure kernel".
         */
        VREG_MASKED(HV_SPTM_CTRR_C_LWR_EL1, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTRR_C_UPR_EL1, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTRR_D_LWR_EL1, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTRR_D_UPR_EL1, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTRR_C_LWR_EL12, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTRR_C_UPR_EL12, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTRR_D_LWR_EL12, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTRR_D_UPR_EL12, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTRR_D_LWR_EL2, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTRR_D_UPR_EL2, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_A_LWR_EL1, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_A_UPR_EL1, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_B_LWR_EL1, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_B_UPR_EL1, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_C_LWR_EL1, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_C_UPR_EL1, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_D_LWR_EL1, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_D_UPR_EL1, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_A_LWR_EL12, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_A_UPR_EL12, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_B_LWR_EL12, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_B_UPR_EL12, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_C_LWR_EL12, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_C_UPR_EL12, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_D_LWR_EL12, ~0xfffULL);
        VREG_MASKED(HV_SPTM_CTXR_D_UPR_EL12, ~0xfffULL);

        /*
         * This is a bit of hack to make SPTM happy since it also checks the per-cluster variants
         * against the same values the per-core ones have after it wrote those. Just mirror the
         * per-cluster register even though it's not quite clear what happens on real hardware.
         */
        VREG_MASKED_ALIAS(HV_SPTM_ACC_CTRR_C_LWR_EL2, HV_SPTM_CTRR_C_LWR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_SPTM_ACC_CTRR_C_UPR_EL2, HV_SPTM_CTRR_C_UPR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_SPTM_ACC_CTRR_D_LWR_EL2, HV_SPTM_CTRR_D_LWR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_SPTM_ACC_CTRR_D_UPR_EL2, HV_SPTM_CTRR_D_UPR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_SPTM_ACC_CTXR_A_LWR_EL2, HV_SPTM_CTXR_A_LWR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_SPTM_ACC_CTXR_A_UPR_EL2, HV_SPTM_CTXR_A_UPR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_SPTM_ACC_CTXR_B_LWR_EL2, HV_SPTM_CTXR_B_LWR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_SPTM_ACC_CTXR_B_UPR_EL2, HV_SPTM_CTXR_B_UPR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_SPTM_ACC_CTXR_C_LWR_EL2, HV_SPTM_CTXR_C_LWR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_SPTM_ACC_CTXR_C_UPR_EL2, HV_SPTM_CTXR_C_UPR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_SPTM_ACC_CTXR_D_LWR_EL2, HV_SPTM_CTXR_D_LWR_EL1, ~0xfffULL);
        VREG_MASKED_ALIAS(HV_SPTM_ACC_CTXR_D_UPR_EL2, HV_SPTM_CTXR_D_UPR_EL1, ~0xfffULL);

        case HV_SPTM_APL_CNTV_CTL_EL0:
            if (is_read) {
                rval = cpu->shadow[HV_SPTM_APL_CNTV_CTL_EL0];
                if ((rval & CNTx_CTL_ENABLE) && (s64)(cpu->timer_deadline - apple_timer_now()) <= 0)
                    rval |= CNTx_CTL_ISTATUS;
            } else {
                cpu->shadow[reg] = wval & (CNTx_CTL_ENABLE | CNTx_CTL_IMASK);
                hv_update_fiq();
                hv_sptm_timer_arm();
            }
            break;
        case HV_SPTM_APL_CNTV_TVAL_EL0:
            if (is_read) {
                rval = (u32)(cpu->timer_deadline - apple_timer_now());
            } else {
                cpu->timer_deadline = apple_timer_now() + (s32)wval;
                hv_update_fiq();
                hv_sptm_timer_arm();
            }
            break;
        default:
            if (is_read)
                rval = cpu->shadow[reg];
            else
                cpu->shadow[reg] = wval;
            break;
    }

    if (is_read)
        ctx->regs[rt] = rval;
    return true;
}

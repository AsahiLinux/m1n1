/* SPDX-License-Identifier: GPL-2.0-or-later */

#include "hv_sptm.h"
#include "cpu_regs.h"
#include "hv.h"
#include "smp.h"
#include "string.h"
#include "utils.h"

bool hv_sptm_active = false;

struct hv_sptm_cpu {
    u64 shadow[HV_SPTM_MAX];
};

static struct hv_sptm_cpu sptm_cpus[MAX_CPUS];

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
    sptm_cpus[i].shadow[HV_SPTM_APCTL_EL1] = BIT(3);

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
    hv_sptm_active = true;
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
    if (!hv_sptm_active)
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

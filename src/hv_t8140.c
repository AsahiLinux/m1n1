/* SPDX-License-Identifier: MIT */
/*
 * This T8140 CPU/ACC/CPM hook is a horrible hack that we don't know how to
 * get rid of. We spent almost two weeks experimenting and ultimately
 * converged to this file.
 *
 * Known failed edits:
 *
 * - Deleting this hook or forwarding all writes causes PEH/DPE bringup
 *   failures.
 * - Dropping all writes produced SPMI errors and hard-rebooted the machine,
 *   and did not fix SPMI.
 *
 */

#include "hv.h"
#include "cpu_regs.h"
#include "memory.h"
#include "smp.h"
#include "soc.h"
#include "string.h"
#include "utils.h"

#define T8140_ACC_PAGE_SIZE 0x4000UL
#define T8140_ACC_GUARD_FIRST_PAGE 2

static const u64 t8140_acc_pages[] = {
    0x210074000UL, 0x211074000UL, 0x210e44000UL, 0x211e44000UL,
    0x210e48000UL, 0x211e48000UL, 0x210058000UL, 0x210158000UL,
    0x210258000UL, 0x210358000UL, 0x211058000UL, 0x211158000UL,
};

static void t8140_flush_stage2_hooks(void)
{
    sysop("dsb ishst");
    sysop("tlbi vmalls12e1is");
    sysop("dsb ish");
    sysop("isb");
}

static int t8140_acc_page_index(u64 ipa)
{
    u64 page = ipa & ~(T8140_ACC_PAGE_SIZE - 1);

    for (u32 i = 0; i < ARRAY_SIZE(t8140_acc_pages); i++)
        if (page == t8140_acc_pages[i])
            return i;

    return -1;
}

#define T8140_ACC_PC_DPE_LOOP_LO 0xfffffe00097b7b00UL
#define T8140_ACC_PC_DPE_LOOP_HI 0xfffffe00097b8d00UL

static bool t8140_acc_hook(struct exc_info *ctx, u64 ipa, u64 *val, bool write, int width)
{
    if (width < 0 || width > 6)
        return false;

    int idx = t8140_acc_page_index(ipa);
    if (idx < 0)
        return false;

    u64 bytes = 1UL << width;
    u64 off = ipa & (T8140_ACC_PAGE_SIZE - 1);
    if (off + bytes > T8140_ACC_PAGE_SIZE)
        return false;

    if (write) {
        u64 pc = ctx->elr;
        if (pc >= T8140_ACC_PC_DPE_LOOP_LO && pc < T8140_ACC_PC_DPE_LOOP_HI) {
            return hv_pa_rw(ctx, ipa, val, true, width);
        }
        if (idx >= 6 && idx <= 9 && (off == 0x1000 || off == 0x1008)) {
            return hv_pa_rw(ctx, ipa, val, true, width);
        }
        /*
         * For E-core CPUs (idx 6..9 -> pages 0x21x058000), forward so the
         * silicon power state matches XNU's view; otherwise cpu0 re-enters
         * peh.c with a stale SError that never clears. P-core CPUs (idx
         * 10..11) are HV-managed; drop those.
         */
        if (idx >= 6 && idx <= 9) {
            return hv_pa_rw(ctx, ipa, val, true, width);
        }
        return true;
    }

    return hv_pa_rw(ctx, ipa, val, false, width);
}

int hv_t8140_map_accumulators(void)
{
    if (chip_id != T8140)
        return 0;

    int failures = 0;
    for (u32 i = T8140_ACC_GUARD_FIRST_PAGE; i < ARRAY_SIZE(t8140_acc_pages); i++)
        failures += hv_map_hook(t8140_acc_pages[i], t8140_acc_hook,
                                T8140_ACC_PAGE_SIZE) != 0;

    u32 requested = ARRAY_SIZE(t8140_acc_pages) - T8140_ACC_GUARD_FIRST_PAGE;
    u32 installed = requested - failures;
    printf("HV: T8140 CPU/ACC/CPM write guard for %lu/%lu pages\n",
           (u64)installed, (u64)requested);
    t8140_flush_stage2_hooks();
    return failures ? -failures : 0;
}

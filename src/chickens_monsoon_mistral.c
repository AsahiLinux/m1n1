/* SPDX-License-Identifier: MIT */

#include "cpu_regs.h"
#include "utils.h"

static void init_t8015_common(void)
{
    // "Disable refcount syncing between E and P"
    reg_mask(SYS_IMP_APL_CYC_OVRD, CYC_OVRD_DSBL_SNOOP_TIME_MASK,
             CYC_OVRD_DSBL_SNOOP_TIME_VALUE(2));

    // "WKdm write ack lost when bif_wke_colorWrAck_XXaH asserts concurrently for both colors"
    reg_set(SYS_IMP_APL_HID8, WKE_FORCE_STRICT_ORDER);
}

void init_t8015_mistral(void)
{
    init_t8015_common();

    // "Atomic launch eligibility is erroneously taken away when a store at SMB gets invalidated"
    reg_clr(SYS_IMP_APL_EHID11, EHID11_SMB_DRAIN_THRESH_MASK);
}

void init_t8015_monsoon(void)
{
    init_t8015_common();
}

/* SPDX-License-Identifier: MIT */

#include "cpu_regs.h"
#include "utils.h"

static void init_common_icestorm(void)
{
    // "Sibling Merge in LLC can cause UC load to violate ARM Memory Ordering Rules."
    reg_set(SYS_IMP_APL_HID5, HID5_DISABLE_FILL_2C_MERGE);

    reg_clr(SYS_IMP_APL_EHID9, EHID9_DEV_2_THROTTLE_ENABLE);

    // "Prevent store-to-load forwarding for UC memory to avoid barrier ordering
    // violation"
    reg_set(SYS_IMP_APL_EHID10, HID10_FORCE_WAIT_STATE_DRAIN_UC | HID10_DISABLE_ZVA_TEMPORAL_TSO);

    // Disable SMC trapping to EL2
    reg_clr(SYS_IMP_APL_EHID20, EHID20_TRAP_SMC);
}

void init_m1_icestorm(void)
{
    init_common_icestorm();

    reg_set(SYS_IMP_APL_EHID20, EHID20_FORCE_NONSPEC_IF_OLDEST_REDIR_VALID_AND_OLDER |
                                    EHID20_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_NE_BLK_RTR_POINTER);

    reg_mask(SYS_IMP_APL_EHID20, EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL_MASK,
             EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL(3));
}

/* SPDX-License-Identifier: MIT */

#include "cpu_regs.h"
#include "utils.h"

// This file name has both the codenames of E-core and P-core because to software
// it is one core that switches modes based on frequency

static void init_common_hurricane_zephyr(void)
{
    /* "Increase Snoop reservation in EDB to reduce starvation risk
        Needs to be done before MMU is enabled" */
    reg_mask(SYS_IMP_APL_HID5, HID5_SNOOP_EDB_RESV_MASK, HID5_SNOOP_EDB_RESV_VALUE(2));

    // "IC prefetch configuration"
    reg_mask(SYS_IMP_APL_HID0, HID0_IC_PREFETCH_DEPTH_MASK, HID0_IC_PREFETCH_DEPTH_VALUE(1));
    reg_set(SYS_IMP_APL_HID0, HID0_IC_PREFETCH_LIMIT_ONE_BRN);

    // "disable reporting of TLB-multi-hit-error"
    reg_clr(SYS_IMP_APL_LSU_ERR_CTL, LSU_ERR_CTL_DISABLE_TLB_MULTI_HIT_ERROR_REPORTING);

    // "disable crypto fusion across decode groups"
    /* Not sure on what's happening here... did the meaning of this bit
       change at some point? Original Name: ARM64_REG_HID1_disAESFuseAcrossGrp */
    reg_set(SYS_IMP_APL_HID1, HID1_CONSERVATIVE_SIQ);
}

void init_t8010_2_hurricane_zephyr(void)
{
    init_common_hurricane_zephyr();
}

void init_t8011_hurricane_zephyr(void)
{
    init_common_hurricane_zephyr();

    reg_clr(SYS_IMP_APL_HID3, HID3_DISABLE_DC_ZVA_CMD_ONLY);
    reg_clr(SYS_IMP_APL_EHID3, EHID3_DISABLE_DC_ZVA_CMD_ONLY);
}

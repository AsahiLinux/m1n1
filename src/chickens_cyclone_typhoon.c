/* SPDX-License-Identifier: MIT */

#include "cpu_regs.h"
#include "utils.h"

// This file includes chickens for both cyclone and typhoon chips
// due to their similarity.

static void init_common_cyclone_typhoon(void)
{
    /* "Disable LSP flush with context switch to work around bug in LSP
            that can cause Cyclone to wedge when CONTEXTIDR is written." */
    reg_set(SYS_IMP_APL_HID0, HID0_LOOP_BUFFER_DISABLE);

    /* Not sure on what's happening here... did the meaning of this bit
       change at some point? Original name: ARM64_REG_HID1_rccDisStallInactiveIexCtl */
    reg_set(SYS_IMP_APL_HID1, HID1_DIS_SPEC_MDSB_INVL_ROB_FLUSH);
    reg_set(SYS_IMP_APL_HID3, HID3_DIS_XMON_SNP_EVICT_TRIGGER_L2_STARAVTION_MODE);

    reg_clr(SYS_IMP_APL_HID5, HID5_DIS_HWP_LD | HID5_DIS_HWP_ST);

    // Change memcache data ID from 0 to 15
    reg_set(SYS_IMP_APL_HID8, HID8_DATA_SET_ID0_VALUE(0xf) | HID8_DATA_SET_ID1_VALUE(0xf));
}

void init_t7000_typhoon(void)
{
    init_common_cyclone_typhoon();
}

void init_t7001_typhoon(void)
{
    init_common_cyclone_typhoon();

    // Change memcache data ID from 0 to 15
    reg_set(SYS_IMP_APL_HID8, HID8_DATA_SET_ID2_VALUE(0xf));
}

void init_s5l8960x_cyclone(void)
{
    init_common_cyclone_typhoon();
    reg_set(SYS_IMP_APL_HID1, HID1_DIS_LSP_FLUSH_WITH_CONTEXT_SWITCH);
}

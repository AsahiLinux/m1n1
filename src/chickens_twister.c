/* SPDX-License-Identifier: MIT */

#include "cpu_regs.h"
#include "utils.h"

static void init_twister_common(void)
{
    reg_clr(SYS_IMP_APL_HID11_LEGACY, HID11_DISABLE_FILL_C1_BUB_OPT);

    // Change memcache data ID from 0 to 15
    reg_set(SYS_IMP_APL_HID8, HID8_DATA_SET_ID0_VALUE(0xf) | HID8_DATA_SET_ID1_VALUE(0xf) |
                                  HID8_DATA_SET_ID2_VALUE(0xf) | HID8_DATA_SET_ID3_VALUE(0xf));

    reg_set(SYS_IMP_APL_HID7, HID7_HID11_DISABLE_NEX_FAST_FMUL);

    // "disable reporting of TLB-multi-hit-error"
    reg_clr(SYS_IMP_APL_LSU_ERR_STS, LSU_ERR_STS_DISABLE_TLB_MULTI_HIT_ERROR_REPORTING);
}

void init_samsung_twister(int rev)
{
    if (rev == 0x20) { // s8000 ONLY
        /* "Set CYC_CFG:skipInit to pull in isAlive by one DCLK
            to work around potential hang.  Must only be applied to Maui C0." "*/
        reg_set(SYS_IMP_APL_ACC_CFG, ACC_CFG_SKIP_INIT);
    }
    init_twister_common();
}

void init_tsmc_twister(void)
{
    init_twister_common();
}

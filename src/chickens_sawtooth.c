/* SPDX-License-Identifier: MIT */

#include "cpu_regs.h"
#include "utils.h"

static void init_common_sawtooth(void)
{
    reg_set(SYS_IMP_APL_EHID0, EHID0_BLI_UNK32);
}

void init_t6030_sawtooth(void)
{
    init_common_sawtooth();
    reg_mask(SYS_IMP_APL_EHID9, EHID9_DEV_2_THROTTLE_LIMIT_MASK, EHID9_DEV_2_THROTTLE_LIMIT(62));
    reg_set(SYS_IMP_APL_EHID9, EHID9_DEV_2_THROTTLE_ENABLE);

    reg_set(SYS_IMP_APL_EHID18, EHID18_BLZ_UNK34);

    reg_mask(SYS_IMP_APL_HID5, HID5_BLZ_UNK_19_18_MASK, HID5_BLZ_UNK19);
}

void init_t6031_sawtooth(void)
{
    init_common_sawtooth();

    reg_mask(SYS_IMP_APL_EHID9, EHID9_DEV_2_THROTTLE_LIMIT_MASK, EHID9_DEV_2_THROTTLE_LIMIT(62));
    reg_set(SYS_IMP_APL_EHID9, EHID9_DEV_2_THROTTLE_ENABLE);
    reg_set(SYS_IMP_APL_EHID18, EHID18_BLZ_UNK34);

    reg_mask(SYS_IMP_APL_HID5, HID5_BLZ_UNK_19_18_MASK, HID5_BLZ_UNK19);
}

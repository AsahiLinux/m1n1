/* SPDX-License-Identifier: MIT */

#include "cpu_regs.h"
#include "utils.h"

static void init_common_avalanche(void)
{

    reg_mask(SYS_IMP_APL_HID1, HID1_AVL_UNK42_MASK, HID1_AVL_UNK42(1));
    reg_mask(SYS_IMP_APL_HID1, HID1_AVL_UNK22_MASK, HID1_AVL_UNK22(3));

    reg_set(SYS_IMP_APL_HID9, HID9_TSO_ALLOW_DC_ZVA_WC | HID9_AVL_UNK17);

    // "configure dummy cycles to work around incorrect temp sensor readings on
    // NEX power gating" (maybe)
    reg_mask(SYS_IMP_APL_HID13,
             HID13_AVL_UNK0_MASK | HID13_AVL_UNK7_MASK | HID13_PRE_CYCLES_MASK |
                 HID13_AVL_UNK26_MASK | HID13_AVL_UNK30_MASK | HID13_AVL_UNK34_MASK |
                 HID13_AVL_UNK38_MASK | HID13_AVL_UNK42_MASK | HID13_AVL_UNK46_MASK |
                 HID13_AVL_UNK50_MASK | HID13_RESET_CYCLE_COUNT_MASK,
             HID13_AVL_UNK0(8) | HID13_AVL_UNK7(8) | HID13_PRE_CYCLES(1) | HID13_AVL_UNK26(4) |
                 HID13_AVL_UNK30(4) | HID13_AVL_UNK34(4) | HID13_AVL_UNK38(4) | HID13_AVL_UNK42(4) |
                 HID13_AVL_UNK46(4) | HID13_AVL_UNK50(4) | HID13_RESET_CYCLE_COUNT(0));

    // No idea what the correct name for these registers is
    reg_mask(s3_0_c15_c0_3, GENMASK(7, 0) | GENMASK(43, 36), (0x1aULL << 0) | (0x1fULL << 36));
    reg_mask(s3_0_c15_c0_4, GENMASK(15, 8), (0x1fULL << 8));
}

static void init_m2_avalanche(void)
{
    init_common_avalanche();

    reg_mask(SYS_IMP_APL_HID3, HID3_AVL_UNK57_MASK, HID3_AVL_UNK57(0x3c));
    reg_set(SYS_IMP_APL_HID3, HID3_DEV_PCIE_THROTTLE_ENABLE);
    reg_set(SYS_IMP_APL_HID18, HID18_AVL_UNK27 | HID18_AVL_UNK29);
    reg_set(SYS_IMP_APL_HID16, HID16_AVL_UNK12);
}

void init_t8112_avalanche(int rev)
{
    UNUSED(rev);

    init_m2_avalanche();
}

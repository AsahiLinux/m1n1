/* SPDX-License-Identifier: MIT */

#include "cpu_regs.h"
#include "uart.h"
#include "utils.h"
static void init_common_everest(void)
{
    reg_set(SYS_IMP_APL_HID12, BIT(46));
    reg_set(SYS_IMP_APL_HID3, HID3_DEV_PCIE_THROTTLE_ENABLE);
    reg_mask(SYS_IMP_APL_HID3, GENMASK(ULONG(62), ULONG(56)), BIT(60) | BIT(59) | BIT(58));
    reg_clr(SYS_IMP_APL_HID3, BIT(4));
    reg_set(SYS_IMP_APL_HID9, BIT(17));
    reg_mask(SYS_IMP_APL_HID13,
             HID13_POST_OFF_CYCLES_MASK | HID13_POST_ON_CYCLES_MASK | HID13_PRE_CYCLES_MASK |
                 HID13_GROUP0_FF1_DELAY_MASK | HID13_GROUP0_FF2_DELAY_MASK |
                 HID13_GROUP0_FF3_DELAY_MASK | HID13_GROUP0_FF4_DELAY_MASK |
                 HID13_GROUP0_FF5_DELAY_MASK | HID13_GROUP0_FF6_DELAY_MASK |
                 HID13_GROUP0_FF7_DELAY_MASK | HID13_RESET_CYCLES_MASK,
             HID13_POST_OFF_CYCLES(4) | HID13_POST_ON_CYCLES(5) | HID13_PRE_CYCLES(1) |
                 HID13_GROUP0_FF1_DELAY(4) | HID13_GROUP0_FF2_DELAY(4) | HID13_GROUP0_FF3_DELAY(4) |
                 HID13_GROUP0_FF4_DELAY(4) | HID13_GROUP0_FF5_DELAY(4) | HID13_GROUP0_FF6_DELAY(4) |
                 HID13_GROUP0_FF7_DELAY(4) | HID13_RESET_CYCLES(0));
    reg_set(SYS_IMP_APL_HID16, BIT(54));
    reg_set(SYS_IMP_APL_HID18,
            HID18_GEXIT_EL_SPECULATION_DISABLE | HID18_GENTER_SPECULATION_DISABLE);

    msr(SYS_IMP_APL_HID26, HID26_GROUP1_OFFSET(0xF88F65588LL) | HID26_GROUP2_OFFSET(0x3F28));
    reg_mask(SYS_IMP_APL_HID27,
             GENMASK(43, 40) | GENMASK(39, 36) | GENMASK(35, 32) | GENMASK(31, 28) |
                 GENMASK(27, 24) | GENMASK(23, 20) | GENMASK(19, 16) | GENMASK(15, 8) |
                 GENMASK(7, 4) | GENMASK(3, 0),
             BIT(40) | BIT(36) | BIT(32) | BIT(28) | BIT(24) | BIT(20) | BIT(16) | 0x2b00uL |
                 BIT(4) | BIT(0));
    /* This is new to M3 and i have no idea what it is yet */
    reg_set(s3_0_c15_c2_3, BIT(3));
    reg_clr(s3_0_c15_c2_4, BIT(0) | BIT(1) | BIT(16) | BIT(17) | BIT(18) | BIT(22));
}

void init_t6030_everest(int rev)
{
    UNUSED(rev);

    reg_set(SYS_IMP_APL_HID16, BIT(54));
    reg_set(SYS_IMP_APL_HID3, HID3_DEV_PCIE_THROTTLE_ENABLE);
    reg_mask(SYS_IMP_APL_HID3, HID3_DEV_PCIE_THROTTLE_LIMIT_MASK, HID3_DEV_PCIE_THROTTLE_LIMIT(60));
    reg_clr(SYS_IMP_APL_HID3, BIT(4));
    reg_set(SYS_IMP_APL_HID9, BIT(17));
    reg_mask(SYS_IMP_APL_HID13,
             HID13_POST_OFF_CYCLES_MASK | HID13_POST_ON_CYCLES_MASK | HID13_PRE_CYCLES_MASK |
                 HID13_GROUP0_FF0_DELAY_MASK | HID13_GROUP0_FF1_DELAY_MASK |
                 HID13_GROUP0_FF2_DELAY_MASK | HID13_GROUP0_FF3_DELAY_MASK |
                 HID13_GROUP0_FF4_DELAY_MASK | HID13_GROUP0_FF5_DELAY_MASK |
                 HID13_GROUP0_FF6_DELAY_MASK | HID13_GROUP0_FF7_DELAY_MASK |
                 HID13_RESET_CYCLES_MASK,
             HID13_POST_OFF_CYCLES(4) | HID13_POST_ON_CYCLES(5) | HID13_PRE_CYCLES(1) |
                 HID13_GROUP0_FF0_DELAY(0) | HID13_GROUP0_FF1_DELAY(4) | HID13_GROUP0_FF2_DELAY(4) |
                 HID13_GROUP0_FF3_DELAY(4) | HID13_GROUP0_FF4_DELAY(4) | HID13_GROUP0_FF5_DELAY(4) |
                 HID13_GROUP0_FF6_DELAY(4) | HID13_GROUP0_FF7_DELAY(4) | HID13_RESET_CYCLES(0));

    msr(SYS_IMP_APL_HID26,
        HID26_GROUP1_OFFSET(0x16 | (0x2 << 8) | (0x2 << 12) | (0x2 << 16) | (0x2 << 20) |
                            (0x2 << 24) | (0x2 << 28) | (0x2uL << 32)) |
            HID26_GROUP2_OFFSET(0x23 | (0x1 << 8) | (0x1 << 12) | (0x1 << 16) | (0x1 << 20) |
                                (0x1 << 24)));
    reg_mask(SYS_IMP_APL_HID27,
             GENMASK(43, 40) | GENMASK(39, 36) | GENMASK(35, 32) | GENMASK(31, 28) |
                 GENMASK(27, 24) | GENMASK(23, 20) | GENMASK(19, 16) | GENMASK(15, 8) |
                 GENMASK(7, 4) | GENMASK(3, 0),
             BIT(40) | BIT(36) | BIT(32) | BIT(28) | BIT(24) | BIT(20) | BIT(16) | 0x2b00uL |
                 BIT(4) | BIT(0));

    reg_set(SYS_IMP_APL_HID18,
            BIT(61) | HID18_GENTER_SPECULATION_DISABLE | HID18_GEXIT_EL_SPECULATION_DISABLE);

    reg_set(s3_0_c15_c2_3, BIT(3));
    reg_clr(s3_0_c15_c2_4, BIT(0) | BIT(1) | BIT(16) | BIT(17) | BIT(18) | BIT(22));

    reg_set(SYS_IMP_APL_HID4, HID4_ENABLE_LFSR_STALL_LOAD_PIPE2_ISSUE);
}

void init_t6031_everest(int rev)
{
    UNUSED(rev);
    msr(s3_1_c15_c1_5, 0x3uL);
    msr(s3_4_c15_c14_6, 0x3uL);
    init_common_everest();
    reg_set(SYS_IMP_APL_HID4, HID4_ENABLE_LFSR_STALL_LOAD_PIPE2_ISSUE);
}

/* SPDX-License-Identifier: MIT */

#include "cpu_regs.h"
#include "utils.h"

static void init_common_firestorm(void)
{
    reg_set(SYS_IMP_APL_HID0, HID0_SAME_PG_POWER_OPTIMIZATION);

    // Disable SMC trapping to EL2
    reg_clr(SYS_IMP_APL_HID1, HID1_TRAP_SMC);

    reg_clr(SYS_IMP_APL_HID3, HID3_DEV_PCIE_THROTTLE_ENABLE | HID3_DISABLE_ARBITER_FIX_BIF_CRD);

    // "Post-silicon tuning of STNT widget contiguous counter threshold"
    reg_mask(SYS_IMP_APL_HID4, HID4_STNT_COUNTER_THRESHOLD_MASK, HID4_STNT_COUNTER_THRESHOLD(3));

    // "Sibling Merge in LLC can cause UC load to violate ARM Memory Ordering Rules."
    reg_set(SYS_IMP_APL_HID5, HID5_DISABLE_FILL_2C_MERGE);

    reg_set(SYS_IMP_APL_HID9, HID9_TSO_ALLOW_DC_ZVA_WC);

    reg_set(SYS_IMP_APL_HID11, HID11_DISABLE_LD_NT_WIDGET);

    // "configure dummy cycles to work around incorrect temp sensor readings on
    // NEX power gating"
    reg_mask(SYS_IMP_APL_HID13, HID13_PRE_CYCLES_MASK, HID13_PRE_CYCLES(4));

    // Best bit names...
    // Maybe: "RF bank and Multipass conflict forward progress widget does not
    // handle 3+ cycle livelock"
    reg_set(SYS_IMP_APL_HID16, HID16_SPAREBIT0 | HID16_SPAREBIT3 | HID16_ENABLE_MPX_PICK_45 |
                                   HID16_ENABLE_MP_CYCLONE_7);
}

static void init_m1_firestorm(void)
{
    init_common_firestorm();

    // "Cross-beat Crypto(AES/PMUL) ICache fusion is not disabled for branch
    // uncondtional "recoded instruction."
    reg_set(SYS_IMP_APL_HID0, HID0_FETCH_WIDTH_DISABLE | HID0_CACHE_FUSION_DISABLE);

    reg_set(SYS_IMP_APL_HID7, HID7_FORCE_NONSPEC_IF_STEPPING |
                                  HID7_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_INVALID_AND_MP_VALID);

    reg_mask(SYS_IMP_APL_HID7, HID7_FORCE_NONSPEC_TARGET_TIMER_SEL_MASK,
             HID7_FORCE_NONSPEC_TARGET_TIMER_SEL(3));

    reg_set(SYS_IMP_APL_HID9, HID9_TSO_SERIALIZE_VLD_MICROOPS | HID9_FIX_BUG_51667805);

    reg_set(SYS_IMP_APL_HID18, HID18_HVC_SPECULATION_DISABLE);

    reg_clr(SYS_IMP_APL_HID21, HID21_ENABLE_LDREX_FILL_REPLY);
}

void init_t8103_firestorm(int rev)
{
    init_m1_firestorm();

    reg_mask(SYS_IMP_APL_HID6, HID6_UP_CRD_TKN_INIT_C2_MASK, HID6_UP_CRD_TKN_INIT_C2(0));

    if (rev >= 0x10) {
        reg_set(SYS_IMP_APL_HID4,
                HID4_ENABLE_LFSR_STALL_LOAD_PIPE_2_ISSUE | HID4_ENABLE_LFSR_STALL_STQ_REPLAY);

        reg_set(SYS_IMP_APL_HID9, HID9_FIX_BUG_55719865);
        reg_set(SYS_IMP_APL_HID11, HID11_ENABLE_FIX_UC_55719865);
    }

    if (rev == 0x11)
        reg_set(SYS_IMP_APL_HID1, HID1_ENABLE_MDSB_STALL_PIPELINE_ECO | HID1_ENABLE_BR_KILL_LIMIT);

    if (rev >= 0x11)
        reg_set(SYS_IMP_APL_HID18, HID18_SPAREBIT17);
}

void init_t6000_firestorm(int rev)
{
    init_m1_firestorm();

    reg_set(SYS_IMP_APL_HID9, HID9_FIX_BUG_55719865);
    reg_set(SYS_IMP_APL_HID11, HID11_ENABLE_FIX_UC_55719865);

    if (rev >= 0x10) {
        reg_set(SYS_IMP_APL_HID1, HID1_ENABLE_MDSB_STALL_PIPELINE_ECO | HID1_ENABLE_BR_KILL_LIMIT);

        reg_set(SYS_IMP_APL_HID4,
                HID4_ENABLE_LFSR_STALL_LOAD_PIPE_2_ISSUE | HID4_ENABLE_LFSR_STALL_STQ_REPLAY);

        reg_set(SYS_IMP_APL_HID18, HID18_SPAREBIT17);
    }
}

void init_t6001_firestorm(int rev)
{
    init_m1_firestorm();

    reg_set(SYS_IMP_APL_HID1, HID1_ENABLE_MDSB_STALL_PIPELINE_ECO);

    reg_set(SYS_IMP_APL_HID4,
            HID4_ENABLE_LFSR_STALL_LOAD_PIPE_2_ISSUE | HID4_ENABLE_LFSR_STALL_STQ_REPLAY);

    reg_set(SYS_IMP_APL_HID9, HID9_FIX_BUG_55719865);

    reg_set(SYS_IMP_APL_HID11, HID11_ENABLE_FIX_UC_55719865);

    if (rev >= 0x10) {
        reg_set(SYS_IMP_APL_HID1, HID1_ENABLE_BR_KILL_LIMIT);

        reg_set(SYS_IMP_APL_HID18, HID18_SPAREBIT17);
    }
}

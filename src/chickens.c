/* SPDX-License-Identifier: MIT */

#include "chickens.h"
#include "cpu_regs.h"
#include "uart.h"
#include "utils.h"

/* Part IDs in MIDR_EL1 */
#define MIDR_PART_A14_ICESTORM  0x20
#define MIDR_PART_A14_FIRESTORM 0x21
#define MIDR_PART_M1_ICESTORM   0x22
#define MIDR_PART_M1_FIRESTORM  0x23

#define MIDR_REV_LOW  GENMASK(3, 0)
#define MIDR_PART     GENMASK(15, 4)
#define MIDR_REV_HIGH GENMASK(23, 20)

void init_common(void)
{
    int core = mrs(MPIDR_EL1) & 0xff;

    // Unknown, related to SMP?
    msr(s3_4_c15_c5_0, core);
    msr(SYS_IMP_APL_AMX_CTL_EL1, 0x100);
    sysop("isb");
}

void init_common_icestorm(void)
{
    // "Sibling Merge in LLC can cause UC load to violate ARM Memory Ordering Rules."
    reg_set(SYS_IMP_APL_HID5, HID5_DISABLE_FILL_2C_MERGE);

    reg_clr(SYS_IMP_APL_EHID9, EHID9_DEV_THROTTLE_2_ENABLE);

    // "Prevent store-to-load forwarding for UC memory to avoid barrier ordering
    // violation"
    reg_set(SYS_IMP_APL_EHID10, HID10_FORCE_WAIT_STATE_DRAIN_UC | HID10_DISABLE_ZVA_TEMPORAL_TSO);

    // FIXME: do we actually need this?
    reg_set(SYS_IMP_APL_EHID20, EHID20_TRAP_SMC);
}

void init_common_firestorm(void)
{
    reg_set(SYS_IMP_APL_HID0, HID0_SAME_PG_POWER_OPTIMIZATION);

    // FIXME: do we actually need this?
    reg_set(SYS_IMP_APL_HID1, HID1_TRAP_SMC);

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

void init_m1_icestorm(int rev)
{
    UNUSED(rev);

    init_common_icestorm();

    reg_set(SYS_IMP_APL_EHID20, EHID20_FORCE_NONSPEC_IF_OLDEST_REDIR_VALID_AND_OLDER |
                                    EHID20_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_NE_BLK_RTR_POINTER);

    reg_mask(SYS_IMP_APL_EHID20, EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL_MASK,
             EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL(3));

    init_common();
}

void init_m1_firestorm(int rev)
{
    if (rev < 0x10)
        printf("  Revisions <0x10 not supported!\n");

    init_common_firestorm();

    // "Cross-beat Crypto(AES/PMUL) ICache fusion is not disabled for branch
    // uncondtional "recoded instruction."
    reg_set(SYS_IMP_APL_HID0, HID0_FETCH_WIDTH_DISABLE | HID0_CACHE_FUSION_DISABLE);

    if (rev == 0x11)
        reg_set(SYS_IMP_APL_HID1, HID1_ENABLE_MDSB_STALL_PIPELINE_ECO | HID1_ENABLE_BR_KILL_LIMIT);

    reg_set(SYS_IMP_APL_HID4,
            HID4_ENABLE_LFSR_STALL_LOAD_PIPE_2_ISSUE | HID4_ENABLE_LFSR_STALL_STQ_REPLAY);

    // "Sibling Merge in LLC can cause UC load to violate ARM Memory Ordering
    // Rules."
    reg_set(SYS_IMP_APL_HID5, HID5_DISABLE_FILL_2C_MERGE);

    reg_mask(SYS_IMP_APL_HID6, HID6_UP_CRD_TKN_INIT_C2_MASK, HID6_UP_CRD_TKN_INIT_C2(0));

    reg_set(SYS_IMP_APL_HID7, HID7_FORCE_NONSPEC_IF_STEPPING |
                                  HID7_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_INVALID_AND_MP_VALID);

    reg_mask(SYS_IMP_APL_HID7, HID7_FORCE_NONSPEC_TARGET_TIMER_SEL_MASK,
             HID7_FORCE_NONSPEC_TARGET_TIMER_SEL(3));

    reg_set(SYS_IMP_APL_HID9,
            HID9_TSO_SERIALIZE_VLD_MICROOPS | HID9_FIX_BUG_51667805 | HID9_FIX_BUG_55719865);

    reg_set(SYS_IMP_APL_HID18, HID18_HVC_SPECULATION_DISABLE);

    if (rev >= 0x11)
        reg_set(SYS_IMP_APL_HID18, HID18_SPAREBIT17);

    reg_clr(SYS_IMP_APL_HID21, HID21_ENABLE_LDREX_FILL_REPLY);

    init_common();
}

const char *init_cpu(void)
{
    const char *cpu = "Unknown";

    msr(OSLAR_EL1, 0);

    /* This is performed unconditionally on all cores (necessary?) */
    if (is_ecore())
        reg_set(SYS_IMP_APL_EHID4, HID4_DISABLE_DC_MVA | HID4_DISABLE_DC_SW_L2_OPS);
    else
        reg_set(SYS_IMP_APL_HID4, HID4_DISABLE_DC_MVA | HID4_DISABLE_DC_SW_L2_OPS);

    uint64_t midr = mrs(MIDR_EL1);
    int part = FIELD_GET(MIDR_PART, midr);
    int rev = (FIELD_GET(MIDR_REV_HIGH, midr) << 4) | FIELD_GET(MIDR_REV_LOW, midr);

    printf("  CPU part: 0x%x rev: 0x%x\n", part, rev);

    switch (part) {
        case MIDR_PART_M1_FIRESTORM:
            cpu = "M1 Firestorm";
            init_m1_firestorm(rev);
            break;

        case MIDR_PART_M1_ICESTORM:
            cpu = "M1 Icestorm";
            init_m1_icestorm(rev);
            break;

        default:
            uart_puts("  Unknown CPU type");
            break;
    }

    /* Unmask external IRQs, set WFI mode to up (2) */
    reg_mask(SYS_IMP_APL_CYC_OVRD,
             CYC_OVRD_FIQ_MODE_MASK | CYC_OVRD_IRQ_MODE_MASK | CYC_OVRD_WFI_MODE_MASK,
             CYC_OVRD_FIQ_MODE(0) | CYC_OVRD_IRQ_MODE(0) | CYC_OVRD_WFI_MODE(2));

    /* Enable branch prediction state retention across ACC sleep */
    reg_mask(SYS_IMP_APL_ACC_CFG, ACC_CFG_BP_SLEEP_MASK, ACC_CFG_BP_SLEEP(3));

    return cpu;
}

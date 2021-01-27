/* SPDX-License-Identifier: MIT */

#include "chickens.h"
#include "uart.h"
#include "utils.h"

#define sys_reg(op0, op1, CRn, CRm, op2) s##op0##_##op1##_c##CRn##_c##CRm##_##op2

#define reg_clr(reg, bits)      msr(reg, mrs(reg) & ~(bits))
#define reg_set(reg, bits)      msr(reg, mrs(reg) | bits)
#define reg_mask(reg, clr, set) msr(reg, (mrs(reg) & ~(clr)) | set)

/* Part IDs in MIDR_EL1 */
#define MIDR_PART_M1_ICESTORM  34
#define MIDR_PART_M1_FIRESTORM 35

/* HID registers */
#define SYS_HID0                        sys_reg(3, 0, 15, 0, 0)
#define HID0_FETCH_WIDTH_DISABLE        (1UL << 28)
#define HID0_CACHE_FUSION_DISABLE       (1UL << 36)
#define HID0_SAME_PG_POWER_OPTIMIZATION (1UL << 45)

#define SYS_HID1      sys_reg(3, 0, 15, 1, 0)
#define HID1_TRAP_SMC (1UL << 54)

#define SYS_HID3                         sys_reg(3, 0, 15, 3, 0)
#define HID3_DEV_PCIE_THROTTLE_ENABLE    (1UL << 63)
#define HID3_DISABLE_ARBITER_FIX_BIF_CRD (1UL << 44)

#define SYS_HID4                         sys_reg(3, 0, 15, 4, 0)
#define SYS_EHID4                        sys_reg(3, 0, 15, 4, 1)
#define HID4_DISABLE_DC_MVA              (1UL << 11)
#define HID4_DISABLE_DC_SW_L2_OPS        (1UL << 44)
#define HID4_STNT_COUNTER_THRESHOLD(x)   (((unsigned long)x) << 40)
#define HID4_STNT_COUNTER_THRESHOLD_MASK (3UL << 40)

#define SYS_HID5                   sys_reg(3, 0, 15, 5, 0)
#define HID5_DISABLE_FILL_2C_MERGE (1UL << 61)

#define SYS_HID6                     sys_reg(3, 0, 15, 6, 0)
#define HID6_UP_CRD_TKN_INIT_C2(x)   (((unsigned long)x) << 5)
#define HID6_UP_CRD_TKN_INIT_C2_MASK (0x1FUL << 5)

#define SYS_HID7                                                      sys_reg(3, 0, 15, 7, 0)
#define HID7_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_INVALID_AND_MP_VALID (1UL << 16)
#define HID7_FORCE_NONSPEC_IF_STEPPING                                (1UL << 20)
#define HID7_FORCE_NONSPEC_TARGET_TIMER_SEL(x)                        (((unsigned long)x) << 24)
#define HID7_FORCE_NONSPEC_TARGET_TIMER_SEL_MASK                      (3UL << 24)

#define SYS_HID9                        sys_reg(3, 0, 15, 9, 0)
#define HID9_TSO_ALLOW_DC_ZVA_WC        (1UL << 26)
#define HID9_TSO_SERIALIZE_VLD_MICROOPS (1UL << 29)
#define HID9_FIX_BUG_51667805           (1UL << 48)

#define SYS_EHID9                   sys_reg(3, 0, 15, 9, 1)
#define EHID9_DEV_THROTTLE_2_ENABLE (1UL << 5)

#define SYS_EHID10                      sys_reg(3, 0, 15, 10, 1)
#define HID10_FORCE_WAIT_STATE_DRAIN_UC (1UL << 32)
#define HID10_DISABLE_ZVA_TEMPORAL_TSO  (1UL << 49)

#define SYS_HID11                  sys_reg(3, 0, 15, 11, 0)
#define HID11_DISABLE_LD_NT_WIDGET (1UL << 59)

#define SYS_HID13             sys_reg(3, 0, 15, 14, 0)
#define HID13_PRE_CYCLES(x)   (((unsigned long)x) << 14)
#define HID13_PRE_CYCLES_MASK (0xFUL << 14)

#define SYS_HID16                 sys_reg(3, 0, 15, 15, 2)
#define HID16_SPAREBIT0           (1UL << 56)
#define HID16_SPAREBIT3           (1UL << 59)
#define HID16_ENABLE_MPX_PICK_45  (1UL << 61)
#define HID16_ENABLE_MP_CYCLONE_7 (1UL << 62)

#define SYS_HID18                     sys_reg(3, 0, 15, 11, 2)
#define HID18_HVC_SPECULATION_DISABLE (1UL << 14)

#define SYS_EHID20                                                    sys_reg(3, 0, 15, 1, 2)
#define EHID20_TRAP_SMC                                               (1UL << 8)
#define EHID20_FORCE_NONSPEC_IF_OLDEST_REDIR_VALID_AND_OLDER          (1UL << 15)
#define EHID20_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_NE_BLK_RTR_POINTER (1UL << 16)
#define EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL(x)                    (((unsigned long)x) << 21)
#define EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL_MASK                  (3UL << 21)

#define SYS_HID21                     sys_reg(3, 0, 15, 1, 3)
#define HID21_ENABLE_LDREX_FILL_REPLY (1UL << 19)

/* ACC/CYC Registers */
#define SYS_ACC_CFG           sys_reg(3, 5, 15, 4, 0)
#define ACC_CFG_BP_SLEEP(x)   (((unsigned long)x) << 2)
#define ACC_CFG_BP_SLEEP_MASK (3UL << 2)

#define SYS_CYC_OVRD           sys_reg(3, 5, 15, 5, 0)
#define CYC_OVRD_FIQ_MODE(x)   (((unsigned long)x) << 20)
#define CYC_OVRD_FIQ_MODE_MASK (3UL << 20)
#define CYC_OVRD_IRQ_MODE(x)   (((unsigned long)x) << 22)
#define CYC_OVRD_IRQ_MODE_MASK (3UL << 22)

void init_m1_common(void)
{
    int core = mrs(MPIDR_EL1) & 0xff;

    // Unknown, related to SMP?
    msr(s3_4_c15_c5_0, core);
    msr(s3_4_c15_c1_4, 0x100);
    sysop("isb");
}

void init_m1_icestorm(void)
{
    // "Sibling Merge in LLC can cause UC load to violate ARM Memory Ordering Rules."
    reg_set(SYS_HID5, HID5_DISABLE_FILL_2C_MERGE);

    reg_clr(SYS_EHID9, EHID9_DEV_THROTTLE_2_ENABLE);

    // "Prevent store-to-load forwarding for UC memory to avoid barrier ordering
    // violation"
    reg_set(SYS_EHID10, HID10_FORCE_WAIT_STATE_DRAIN_UC | HID10_DISABLE_ZVA_TEMPORAL_TSO);

    // FIXME: do we actually need this?
    reg_set(SYS_EHID20, EHID20_TRAP_SMC);

    reg_set(SYS_EHID20, EHID20_FORCE_NONSPEC_IF_OLDEST_REDIR_VALID_AND_OLDER |
                            EHID20_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_NE_BLK_RTR_POINTER);

    reg_mask(SYS_EHID20, EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL_MASK,
             EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL(3));

    init_m1_common();
}

void init_m1_firestorm(void)
{
    // "Cross-beat Crypto(AES/PMUL) ICache fusion is not disabled for branch
    // uncondtional "recoded instruction."
    reg_set(SYS_HID0,
            HID0_SAME_PG_POWER_OPTIMIZATION | HID0_FETCH_WIDTH_DISABLE | HID0_CACHE_FUSION_DISABLE);

    // FIXME: do we actually need this?
    reg_set(SYS_HID1, HID1_TRAP_SMC);

    reg_clr(SYS_HID3, HID3_DEV_PCIE_THROTTLE_ENABLE | HID3_DISABLE_ARBITER_FIX_BIF_CRD);

    // "Post-silicon tuning of STNT widget contiguous counter threshold"
    reg_mask(SYS_HID4, HID4_STNT_COUNTER_THRESHOLD_MASK, HID4_STNT_COUNTER_THRESHOLD(3));

    // "Sibling Merge in LLC can cause UC load to violate ARM Memory Ordering
    // Rules."
    reg_set(SYS_HID5, HID5_DISABLE_FILL_2C_MERGE);

    reg_mask(SYS_HID6, HID6_UP_CRD_TKN_INIT_C2_MASK, HID6_UP_CRD_TKN_INIT_C2(0));

    reg_set(SYS_HID7, HID7_FORCE_NONSPEC_IF_STEPPING |
                          HID7_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_INVALID_AND_MP_VALID);

    reg_mask(SYS_HID7, HID7_FORCE_NONSPEC_TARGET_TIMER_SEL_MASK,
             HID7_FORCE_NONSPEC_TARGET_TIMER_SEL(3));

    reg_set(SYS_HID9,
            HID9_TSO_ALLOW_DC_ZVA_WC | HID9_TSO_SERIALIZE_VLD_MICROOPS | HID9_FIX_BUG_51667805);

    reg_set(SYS_HID11, HID11_DISABLE_LD_NT_WIDGET);

    // "configure dummy cycles to work around incorrect temp sensor readings on
    // NEX power gating"
    reg_mask(SYS_HID13, HID13_PRE_CYCLES_MASK, HID13_PRE_CYCLES(4));

    // Best bit names...
    // Maybe: "RF bank and Multipass conflict forward progress widget does not
    // handle 3+
    //         cycle livelock"
    reg_set(SYS_HID16, HID16_SPAREBIT0 | HID16_SPAREBIT3 | HID16_ENABLE_MPX_PICK_45 |
                           HID16_ENABLE_MP_CYCLONE_7);

    reg_set(SYS_HID18, HID18_HVC_SPECULATION_DISABLE);

    reg_clr(SYS_HID21, HID21_ENABLE_LDREX_FILL_REPLY);

    init_m1_common();
}

const char *init_cpu(void)
{
    const char *cpu = "Unknown";
    int is_ecore = !(mrs(MPIDR_EL1) & (1 << 16));

    msr(OSLAR_EL1, 0);

    /* This is performed unconditionally on all cores (necessary?) */
    if (is_ecore)
        reg_set(SYS_EHID4, HID4_DISABLE_DC_MVA | HID4_DISABLE_DC_SW_L2_OPS);
    else
        reg_set(SYS_HID4, HID4_DISABLE_DC_MVA | HID4_DISABLE_DC_SW_L2_OPS);

    int part = (mrs(MIDR_EL1) >> 4) & 0xfff;

    switch (part) {
        case MIDR_PART_M1_FIRESTORM:
            cpu = "M1 Firestorm";
            init_m1_firestorm();
            break;

        case MIDR_PART_M1_ICESTORM:
            cpu = "M1 Icestorm";
            init_m1_icestorm();
            break;

        default:
            uart_puts("Unknown CPU type");
            break;
    }

    /* Unmask external IRQs */
    reg_mask(SYS_CYC_OVRD, CYC_OVRD_FIQ_MODE_MASK | CYC_OVRD_IRQ_MODE_MASK,
             CYC_OVRD_FIQ_MODE(0) | CYC_OVRD_IRQ_MODE(0));

    /* Enable branch prediction state retention across ACC sleep */
    reg_mask(SYS_ACC_CFG, ACC_CFG_BP_SLEEP_MASK, ACC_CFG_BP_SLEEP(3));

    return cpu;
}

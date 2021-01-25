/* SPDX-License-Identifier: MIT */

#include "chickens.h"
#include "uart.h"
#include "utils.h"

#define sys_reg(op0, op1, CRn, CRm, op2)                                           \
    s##op0##_##op1##_c##CRn##_c##CRm##_##op2

#define reg_clr(reg, bits) msr(reg, mrs(reg) & ~(bits))
#define reg_set(reg, bits) msr(reg, mrs(reg) | bits)
#define reg_mask(reg, clr, set) msr(reg, (mrs(reg) & ~(clr)) | set)

/* Part IDs in MIDR_EL1 */
#define MIDR_PART_M1_FIRESTORM 33
#define MIDR_PART_M1_ICESTORM 34

/* HID registers */
#define SYS_HID4                    sys_reg(3, 0, 15, 4, 0)
#define SYS_EHID4                   sys_reg(3, 0, 15, 4, 1)
#define HID4_DISABLE_DC_MVA         (1UL << 11)
#define HID4_DISABLE_DC_SW_L2_OPS   (1UL << 44)

#define SYS_HID5                    sys_reg(3, 0, 15, 5, 0)
#define HID5_DISABLE_FILL_2C_MERGE  (1UL << 61)

#define SYS_EHID9           sys_reg(3, 0, 15, 9, 1)
#define EHID9_DEV_THROTTLE_2_ENABLE (1UL << 5)

#define SYS_EHID10                  sys_reg(3, 0, 15, 10, 1)
#define HID10_FORCE_WAIT_STATE_DRAIN_UC (1UL << 32)
#define HID10_DISABLE_ZVA_TEMPORAL_TSO  (1UL << 49)

#define SYS_EHID20                  sys_reg(3, 0, 15, 1, 2)
#define EHID20_TRAP_SMC             (1UL << 8)

#define EHID20_FORCE_NONSPEC_IF_OLDEST_REDIR_VALID_AND_OLDER            (1UL << 15)
#define EHID20_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_NE_BLK_RTR_POINTER   (1UL << 16)
#define EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL(x)          (((unsigned long)x) << 21)
#define EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL_MASK        (3UL << 21)

/* ACC/CYC Registers */
#define SYS_ACC_CFG                 sys_reg(3, 5, 15, 4, 0)
#define ACC_CFG_BP_SLEEP(x)         (((unsigned long)x) << 2)
#define ACC_CFG_BP_SLEEP_MASK       (3UL << 2)

#define SYS_CYC_OVRD                sys_reg(3, 5, 15, 5, 0)
#define CYC_OVRD_FIQ_MODE(x)        (((unsigned long)x) << 20)
#define CYC_OVRD_FIQ_MODE_MASK      (3UL << 20)
#define CYC_OVRD_IRQ_MODE(x)        (((unsigned long)x) << 22)
#define CYC_OVRD_IRQ_MODE_MASK      (3UL << 22)



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

    // "Prevent store-to-load forwarding for UC memory to avoid barrier ordering violation"
    reg_set(SYS_EHID10, HID10_FORCE_WAIT_STATE_DRAIN_UC | HID10_DISABLE_ZVA_TEMPORAL_TSO);

    // FIXME: do we actually need this?
    reg_set(SYS_EHID20, EHID20_TRAP_SMC);

    reg_clr(SYS_EHID9, EHID9_DEV_THROTTLE_2_ENABLE);

    reg_set(SYS_EHID20, EHID20_FORCE_NONSPEC_IF_OLDEST_REDIR_VALID_AND_OLDER |
                        EHID20_FORCE_NONSPEC_IF_SPEC_FLUSH_POINTER_NE_BLK_RTR_POINTER);

    reg_mask(SYS_EHID20, EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL_MASK,
             EHID20_FORCE_NONSPEC_TARGETED_TIMER_SEL(3));

    init_m1_common();
}

void init_m1_firestorm(void)
{
    // TODO

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


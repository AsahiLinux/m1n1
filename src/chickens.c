/* SPDX-License-Identifier: MIT */

#include "chickens.h"
#include "cpu_regs.h"
#include "uart.h"
#include "utils.h"

/* Part IDs in MIDR_EL1 */
#define MIDR_PART_T8181_ICESTORM  0x20
#define MIDR_PART_T8181_FIRESTORM 0x21
#define MIDR_PART_T8103_ICESTORM  0x22
#define MIDR_PART_T8103_FIRESTORM 0x23
#define MIDR_PART_T6000_ICESTORM  0x24
#define MIDR_PART_T6000_FIRESTORM 0x25
#define MIDR_PART_T6001_ICESTORM  0x28
#define MIDR_PART_T6001_FIRESTORM 0x29
#define MIDR_PART_T8110_BLIZZARD  0x30
#define MIDR_PART_T8110_AVALANCHE 0x31
#define MIDR_PART_T8112_BLIZZARD  0x32
#define MIDR_PART_T8112_AVALANCHE 0x33
#define MIDR_PART_T6020_BLIZZARD  0x34
#define MIDR_PART_T6020_AVALANCHE 0x35
#define MIDR_PART_T6021_BLIZZARD  0x38
#define MIDR_PART_T6021_AVALANCHE 0x39
#define MIDR_PART_T6031_EVEREST   0x49
#define MIDR_PART_T6031_SAWTOOTH  0x48

#define MIDR_REV_LOW  GENMASK(3, 0)
#define MIDR_PART     GENMASK(15, 4)
#define MIDR_REV_HIGH GENMASK(23, 20)

void init_m1_icestorm(void);
void init_t8103_firestorm(int rev);
void init_t6000_firestorm(int rev);
void init_t6001_firestorm(int rev);
void init_t8112_blizzard(void);
void init_t8112_avalanche(int rev);
void init_t6020_blizzard(void);
void init_t6020_avalanche(int rev);
void init_t6021_blizzard(void);
void init_t6021_avalanche(int rev);
void init_t6031_sawtooth(void);
void init_t6031_everest(int rev);

const char *init_cpu(void)
{
    const char *cpu = "Unknown";

    msr(OSLAR_EL1, 0);

    /* This is performed unconditionally on all cores (necessary?) */
    if (is_ecore())
        reg_set(SYS_IMP_APL_EHID4, EHID4_DISABLE_DC_MVA | EHID4_DISABLE_DC_SW_L2_OPS);
    else
        reg_set(SYS_IMP_APL_HID4, HID4_DISABLE_DC_MVA | HID4_DISABLE_DC_SW_L2_OPS);

    /* Enable NEX powergating, the reset cycles might be overriden by chickens */
    if (!is_ecore()) {
        reg_mask(SYS_IMP_APL_HID13, HID13_RESET_CYCLES_MASK, HID13_RESET_CYCLES(12));
        reg_set(SYS_IMP_APL_HID14, HID14_ENABLE_NEX_POWER_GATING);
    }

    uint64_t midr = mrs(MIDR_EL1);
    int part = FIELD_GET(MIDR_PART, midr);
    int rev = (FIELD_GET(MIDR_REV_HIGH, midr) << 4) | FIELD_GET(MIDR_REV_LOW, midr);

    printf("  CPU part: 0x%x rev: 0x%x\n", part, rev);

    switch (part) {
        case MIDR_PART_T8103_FIRESTORM:
            cpu = "M1 Firestorm";
            init_t8103_firestorm(rev);
            break;

        case MIDR_PART_T6000_FIRESTORM:
            cpu = "M1 Pro Firestorm";
            init_t6000_firestorm(rev);
            break;

        case MIDR_PART_T6001_FIRESTORM:
            cpu = "M1 Max Firestorm";
            init_t6001_firestorm(rev);
            break;

        case MIDR_PART_T8103_ICESTORM:
            cpu = "M1 Icestorm";
            init_m1_icestorm();
            break;

        case MIDR_PART_T6000_ICESTORM:
            cpu = "M1 Pro Icestorm";
            init_m1_icestorm();
            break;

        case MIDR_PART_T6001_ICESTORM:
            cpu = "M1 Max Icestorm";
            init_m1_icestorm();
            break;

        case MIDR_PART_T8112_AVALANCHE:
            cpu = "M2 Avalanche";
            init_t8112_avalanche(rev);
            break;

        case MIDR_PART_T8112_BLIZZARD:
            cpu = "M2 Blizzard";
            init_t8112_blizzard();
            break;

        case MIDR_PART_T6020_AVALANCHE:
            cpu = "M2 Pro Avalanche";
            init_t6020_avalanche(rev);
            break;

        case MIDR_PART_T6020_BLIZZARD:
            cpu = "M2 Pro Blizzard";
            init_t6020_blizzard();
            break;

        case MIDR_PART_T6021_AVALANCHE:
            cpu = "M2 Max Avalanche";
            init_t6021_avalanche(rev);
            break;

        case MIDR_PART_T6021_BLIZZARD:
            cpu = "M2 Max Blizzard";
            init_t6021_blizzard();
            break;

        case MIDR_PART_T6031_EVEREST:
            cpu = "M3 Max Everest";
            init_t6031_everest(rev);
            break;

        case MIDR_PART_T6031_SAWTOOTH:
            cpu = "M3 Max Sawtooth";
            init_t6031_sawtooth();
            break;

        default:
            uart_puts("  Unknown CPU type");
            break;
    }

    int core = mrs(MPIDR_EL1) & 0xff;

    // Unknown, related to SMP?
    msr(s3_4_c15_c5_0, core);
    msr(SYS_IMP_APL_AMX_CTL_EL1, 0x100);

    // Enable IRQs (at least necessary on t600x)
    // XXX 0 causes pathological behavior in EL1, 2 works.
    msr(SYS_IMP_APL_SIQ_CFG_EL1, 2);

    sysop("isb");

    /* Unmask external IRQs, set WFI mode to up (2) */
    reg_mask(SYS_IMP_APL_CYC_OVRD,
             CYC_OVRD_FIQ_MODE_MASK | CYC_OVRD_IRQ_MODE_MASK | CYC_OVRD_WFI_MODE_MASK,
             CYC_OVRD_FIQ_MODE(0) | CYC_OVRD_IRQ_MODE(0) | CYC_OVRD_WFI_MODE(2));

    /* Enable branch prediction state retention across ACC sleep */
    reg_mask(SYS_IMP_APL_ACC_CFG, ACC_CFG_BP_SLEEP_MASK, ACC_CFG_BP_SLEEP(3));

    return cpu;
}

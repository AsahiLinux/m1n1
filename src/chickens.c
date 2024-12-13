/* SPDX-License-Identifier: MIT */

#include "chickens.h"
#include "cpu_regs.h"
#include "midr.h"
#include "uart.h"
#include "utils.h"

void init_s5l8960x_cyclone(void);
void init_t7000_typhoon(void);
void init_t7001_typhoon(void);
void init_samsung_twister(int rev);
void init_tsmc_twister(void);
void init_t8010_2_hurricane_zephyr(void);
void init_t8011_hurricane_zephyr(void);
void init_t8015_monsoon(void);
void init_t8015_mistral(void);
void init_t8015_monsoon(void);
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
void init_t6030_sawtooth(void);
void init_t6030_everest(int rev);
void init_t6031_sawtooth(void);
void init_t6031_everest(int rev);

bool cpufeat_actlr_el2, cpufeat_fast_ipi, cpufeat_mmu_sprr;
bool cpufeat_global_sleep, cpufeat_workaround_cyclone_cache;

const char *init_cpu(void)
{
    const char *cpu = "Unknown";

    msr(OSLAR_EL1, 0);

    /* This is performed unconditionally on all cores (necessary?) */
    if (is_ecore())
        reg_set(SYS_IMP_APL_EHID4, EHID4_DISABLE_DC_MVA | EHID4_DISABLE_DC_SW_L2_OPS);
    else
        reg_set(SYS_IMP_APL_HID4, HID4_DISABLE_DC_MVA | HID4_DISABLE_DC_SW_L2_OPS);

    uint64_t midr = mrs(MIDR_EL1);
    int part = FIELD_GET(MIDR_PART, midr);
    int rev = (FIELD_GET(MIDR_REV_HIGH, midr) << 4) | FIELD_GET(MIDR_REV_LOW, midr);

    printf("  CPU part: 0x%x rev: 0x%x\n", part, rev);

    if (part >= MIDR_PART_T8015_MONSOON) {
        /* Enable NEX powergating, the reset cycles might be overridden by chickens */
        if (!is_ecore()) {
            reg_mask(SYS_IMP_APL_HID13, HID13_RESET_CYCLES_MASK, HID13_RESET_CYCLES(12));
            reg_set(SYS_IMP_APL_HID14, HID14_ENABLE_NEX_POWER_GATING);
        }
    }

    switch (part) {
        case MIDR_PART_S5L8960X_CYCLONE:
            cpu = "A7 Cyclone";
            init_s5l8960x_cyclone();
            break;

        case MIDR_PART_T7000_TYPHOON:
            cpu = "A8 Typhoon";
            init_t7000_typhoon();
            break;

        case MIDR_PART_T7001_TYPHOON:
            cpu = "A8X Typhoon";
            init_t7001_typhoon();
            break;

        case MIDR_PART_S8000_TWISTER:
            cpu = "A9 Twister (Samsung)";
            init_samsung_twister(rev);
            break;

        case MIDR_PART_S8001_3_TWISTER:
            cpu = "A9(X) Twister (TSMC)";
            init_tsmc_twister();
            break;

        case MIDR_PART_T8010_2_HURRICANE:
            cpu = "A10/T2 Hurricane-Zephyr";
            init_t8010_2_hurricane_zephyr();
            break;

        case MIDR_PART_T8011_HURRICANE:
            cpu = "A10X Hurricane-Zephyr";
            init_t8011_hurricane_zephyr();
            break;

        case MIDR_PART_T8015_MONSOON:
            cpu = "A11 Monsoon";
            init_t8015_monsoon();
            break;

        case MIDR_PART_T8015_MISTRAL:
            cpu = "A11 Mistral";
            init_t8015_mistral();
            break;

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

        case MIDR_PART_T6030_EVEREST:
            cpu = "M3 Pro Everest";
            init_t6030_everest(rev);
            break;

        case MIDR_PART_T6030_SAWTOOTH:
            cpu = "M3 Pro Sawtooth";
            init_t6030_sawtooth();
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

    if (part >= MIDR_PART_T8110_BLIZZARD)
        cpufeat_actlr_el2 = true;

    if (part >= MIDR_PART_T8101_ICESTORM && part != MIDR_PART_T8301_THUNDER) {
        int core = mrs(MPIDR_EL1) & 0xff;

        // Enable IRQs (at least necessary on t600x)
        // XXX 0 causes pathological behavior in EL1, 2 works.
        msr(SYS_IMP_APL_SIQ_CFG_EL1, 2);
        sysop("isb");

        msr(SYS_IMP_APL_AMX_CTX_EL1, core);

        /* T8030 SPRR is different */
        cpufeat_mmu_sprr = true;
    }

    if (part >= MIDR_PART_T8030_LIGHTNING)
        msr(SYS_IMP_APL_AMX_CTL_EL1, 0x100);

    if (part >= MIDR_PART_T8015_MONSOON)
        cpufeat_fast_ipi = true;

    if (part >= MIDR_PART_T8010_2_HURRICANE)
        cpufeat_global_sleep = true;
    else {
        /* Disable deep sleep */
        reg_clr(SYS_IMP_APL_ACC_CFG, ACC_CFG_DEEP_SLEEP);
        cpufeat_workaround_cyclone_cache = true;
    }

    /* Unmask external IRQs, set WFI mode to up (2) */
    reg_mask(SYS_IMP_APL_CYC_OVRD,
             CYC_OVRD_FIQ_MODE_MASK | CYC_OVRD_IRQ_MODE_MASK | CYC_OVRD_WFI_MODE_MASK,
             CYC_OVRD_FIQ_MODE(0) | CYC_OVRD_IRQ_MODE(0) | CYC_OVRD_WFI_MODE(2));

    // Enable branch prediction state retention across ACC sleep
    reg_mask(SYS_IMP_APL_ACC_CFG, ACC_CFG_BP_SLEEP_MASK, ACC_CFG_BP_SLEEP(3));

    return cpu;
}

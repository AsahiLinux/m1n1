/* SPDX-License-Identifier: MIT */

#include "chickens.h"
#include "cpu_regs.h"
#include "midr.h"
#include "uart.h"
#include "utils.h"

void init_s5l8960x_cyclone(int rev);
void init_t7000_typhoon(int rev);
void init_t7001_typhoon(int rev);
void init_samsung_twister(int rev);
void init_tsmc_twister(int rev);
void init_t8010_2_hurricane_zephyr(int rev);
void init_t8011_hurricane_zephyr(int rev);
void init_t8015_monsoon(int rev);
void init_t8015_mistral(int rev);
void init_t8015_monsoon(int rev);
void init_m1_icestorm(int rev);
void init_t8103_firestorm(int rev);
void init_t6000_firestorm(int rev);
void init_t6001_firestorm(int rev);
void init_t8112_blizzard(int rev);
void init_t8112_avalanche(int rev);
void init_t6020_blizzard(int rev);
void init_t6020_avalanche(int rev);
void init_t6021_blizzard(int rev);
void init_t6021_avalanche(int rev);
void init_t6030_sawtooth(int rev);
void init_t6030_everest(int rev);
void init_t6031_sawtooth(int rev);
void init_t6031_everest(int rev);

bool cpufeat_actlr_el2, cpufeat_fast_ipi, cpufeat_mmu_sprr;
bool cpufeat_workaround_cyclone_cache, cpufeat_cyc_ovrd;
enum cpufeat_sleep_mode cpufeat_sleep_mode;

struct midr_part_features {
    enum cpufeat_sleep_mode sleep_mode;
    bool disable_dc_mva;
    bool acc_cfg;
    bool cyc_ovrd;
    bool workaround_cyclone_cache;
    bool nex_powergating;
    bool fast_ipi;
    bool mmu_sprr;
    bool siq_cfg;
    bool amx;
    bool actlr_el2;
};

struct midr_part_info {
    int part;
    const char *name;
    void (*init)(int rev);
    const struct midr_part_features *features;
};

const struct midr_part_features features_a7 = {
    .disable_dc_mva = true,
    .acc_cfg = true,
    .cyc_ovrd = true,
    .workaround_cyclone_cache = true,
    .sleep_mode = SLEEP_LEGACY,
};

const struct midr_part_features features_a10 = {
    .disable_dc_mva = true,
    .acc_cfg = true,
    .cyc_ovrd = true,
    .workaround_cyclone_cache = false,
    .sleep_mode = SLEEP_GLOBAL,
};

const struct midr_part_features features_a11 = {
    .disable_dc_mva = true,
    .acc_cfg = true,
    .cyc_ovrd = true,
    .sleep_mode = SLEEP_GLOBAL,
    .nex_powergating = true,
    .fast_ipi = true,
};

const struct midr_part_features features_m1 = {
    .disable_dc_mva = true,
    .acc_cfg = true,
    .cyc_ovrd = true,
    .sleep_mode = SLEEP_GLOBAL,
    .nex_powergating = true,
    .fast_ipi = true,
    .mmu_sprr = true,
    .siq_cfg = true,
    .amx = true,
};

const struct midr_part_features features_m2 = {
    .disable_dc_mva = true,
    .acc_cfg = true,
    .cyc_ovrd = true,
    .sleep_mode = SLEEP_GLOBAL,
    .nex_powergating = true,
    .fast_ipi = true,
    .mmu_sprr = true,
    .siq_cfg = true,
    .amx = true,
    .actlr_el2 = true,
};

const struct midr_part_info midr_parts[] = {
    {MIDR_PART_S5L8960X_CYCLONE, "A7 Cyclone", init_s5l8960x_cyclone, &features_a7},
    {MIDR_PART_T7000_TYPHOON, "A8 Typhoon", init_t7000_typhoon, &features_a7},
    {MIDR_PART_T7001_TYPHOON, "A8X Typhoon", init_t7001_typhoon, &features_a7},
    {MIDR_PART_S8000_TWISTER, "A9 Twister (Samsung)", init_samsung_twister, &features_a7},
    {MIDR_PART_S8001_3_TWISTER, "A9(X) Twister (TSMC)", init_tsmc_twister, &features_a7},
    {MIDR_PART_T8010_2_HURRICANE, "A10/T2 Hurricane-Zephyr", init_t8010_2_hurricane_zephyr,
     &features_a10},
    {MIDR_PART_T8011_HURRICANE, "A10X Hurricane-Zephyr", init_t8011_hurricane_zephyr,
     &features_a10},
    {MIDR_PART_T8015_MONSOON, "A11 Monsoon", init_t8015_monsoon, &features_a11},
    {MIDR_PART_T8015_MISTRAL, "A11 Mistral", init_t8015_mistral, &features_a11},
    {MIDR_PART_T8103_FIRESTORM, "M1 Firestorm", init_t8103_firestorm, &features_m1},
    {MIDR_PART_T6000_FIRESTORM, "M1 Pro Firestorm", init_t6000_firestorm, &features_m1},
    {MIDR_PART_T6001_FIRESTORM, "M1 Max Firestorm", init_t6001_firestorm, &features_m1},
    {MIDR_PART_T8103_ICESTORM, "M1 Icestorm", init_m1_icestorm, &features_m1},
    {MIDR_PART_T6000_ICESTORM, "M1 Pro Icestorm", init_m1_icestorm, &features_m1},
    {MIDR_PART_T6001_ICESTORM, "M1 Max Icestorm", init_m1_icestorm, &features_m1},
    {MIDR_PART_T8112_AVALANCHE, "M2 Avalanche", init_t8112_avalanche, &features_m2},
    {MIDR_PART_T8112_BLIZZARD, "M2 Blizzard", init_t8112_blizzard, &features_m2},
    {MIDR_PART_T6020_AVALANCHE, "M2 Pro Avalanche", init_t6020_avalanche, &features_m2},
    {MIDR_PART_T6020_BLIZZARD, "M2 Pro Blizzard", init_t6020_blizzard, &features_m2},
    {MIDR_PART_T6021_AVALANCHE, "M2 Max Avalanche", init_t6021_avalanche, &features_m2},
    {MIDR_PART_T6021_BLIZZARD, "M2 Max Blizzard", init_t6021_blizzard, &features_m2},
    {MIDR_PART_T6030_EVEREST, "M3 Pro Everest", init_t6030_everest, &features_m2},
    {MIDR_PART_T6030_SAWTOOTH, "M3 Pro Sawtooth", init_t6030_sawtooth, &features_m2},
    {MIDR_PART_T6031_EVEREST, "M3 Max Everest", init_t6031_everest, &features_m2},
    {MIDR_PART_T6031_SAWTOOTH, "M3 Max Sawtooth", init_t6031_sawtooth, &features_m2},
};

const struct midr_part_features features_unknown = {
    .sleep_mode = SLEEP_NONE,
};

const struct midr_part_info midr_part_info_unknown = {
    .name = "Unknown",
    .features = &features_unknown,
};

void init_cpu(void)
{
    const struct midr_part_info *midr_part_info = NULL;
    msr(OSLAR_EL1, 0);

    uint64_t midr = mrs(MIDR_EL1);
    int part = FIELD_GET(MIDR_PART, midr);
    int rev = (FIELD_GET(MIDR_REV_HIGH, midr) << 4) | FIELD_GET(MIDR_REV_LOW, midr);

    printf("  CPU part: 0x%x rev: 0x%x\n", part, rev);

    for (size_t i = 0; i < sizeof(midr_parts) / sizeof(midr_parts[0]); i++) {
        if (midr_parts[i].part == part) {
            midr_part_info = &midr_parts[i];
            break;
        }
    }

    if (!midr_part_info)
        midr_part_info = &midr_part_info_unknown;

    printf("  CPU: %s\n", midr_part_info->name);

    cpufeat_workaround_cyclone_cache = midr_part_info->features->workaround_cyclone_cache;
    cpufeat_sleep_mode = midr_part_info->features->sleep_mode;
    cpufeat_fast_ipi = midr_part_info->features->fast_ipi;
    cpufeat_mmu_sprr = midr_part_info->features->mmu_sprr;
    cpufeat_actlr_el2 = midr_part_info->features->actlr_el2;
    cpufeat_cyc_ovrd = midr_part_info->features->cyc_ovrd;

    if (midr_part_info->features->disable_dc_mva) {
        /* This is performed unconditionally on all cores (necessary?) */
        if (is_ecore())
            reg_set(SYS_IMP_APL_EHID4, EHID4_DISABLE_DC_MVA | EHID4_DISABLE_DC_SW_L2_OPS);
        else
            reg_set(SYS_IMP_APL_HID4, HID4_DISABLE_DC_MVA | HID4_DISABLE_DC_SW_L2_OPS);
    }

    if (midr_part_info->features->nex_powergating) {
        /* Enable NEX powergating, the reset cycles might be overridden by chickens */
        if (!is_ecore()) {
            reg_mask(SYS_IMP_APL_HID13, HID13_RESET_CYCLES_MASK, HID13_RESET_CYCLES(12));
            reg_set(SYS_IMP_APL_HID14, HID14_ENABLE_NEX_POWER_GATING);
        }
    }

    /* Apply chicken bits if neccessary */
    if (midr_part_info->init)
        midr_part_info->init(rev);

    if (midr_part_info->features->siq_cfg) {
        // Enable IRQs (at least necessary on t600x)
        // XXX 0 causes pathological behavior in EL1, 2 works.
        msr(SYS_IMP_APL_SIQ_CFG_EL1, 2);
        sysop("isb");
    }

    if (midr_part_info->features->amx) {
        // XXX is this really AMX?
        int core = mrs(MPIDR_EL1) & 0xff;
        msr(SYS_IMP_APL_AMX_CTX_EL1, core);
        msr(SYS_IMP_APL_AMX_CTL_EL1, 0x100);
    }

    if (cpufeat_sleep_mode == SLEEP_LEGACY) {
        /* Disable deep sleep */
        reg_clr(SYS_IMP_APL_ACC_CFG, ACC_CFG_DEEP_SLEEP);
    }

    if (cpufeat_cyc_ovrd) {
        /* Unmask external IRQs, set WFI mode to up (2) */
        reg_mask(SYS_IMP_APL_CYC_OVRD,
                 CYC_OVRD_FIQ_MODE_MASK | CYC_OVRD_IRQ_MODE_MASK | CYC_OVRD_WFI_MODE_MASK,
                 CYC_OVRD_FIQ_MODE(0) | CYC_OVRD_IRQ_MODE(0) | CYC_OVRD_WFI_MODE(2));
    }

    // Enable branch prediction state retention across ACC sleep
    if (midr_part_info->features->acc_cfg) {
        reg_mask(SYS_IMP_APL_ACC_CFG, ACC_CFG_BP_SLEEP_MASK, ACC_CFG_BP_SLEEP(3));
    }
}

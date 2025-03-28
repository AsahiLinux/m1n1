/* SPDX-License-Identifier: MIT */

#include "cpufreq.h"
#include "adt.h"
#include "firmware.h"
#include "pmgr.h"
#include "soc.h"
#include "utils.h"

#define CLUSTER_PSTATE 0x20020

#define CLUSTER_PSTATE_FIXED_FREQ_PLL_RECLOCK BIT(42)
#define CLUSTER_PSTATE_BUSY                   BIT(31)
#define CLUSTER_PSTATE_SET                    BIT(25)
#define CLUSTER_PSTATE_M2_APSC_DIS            BIT(23)
#define CLUSTER_PSTATE_M1_APSC_DIS            BIT(22)
#define CLUSTER_PSTATE_UNK_M2                 BIT(22)
#define CLUSTER_PSTATE_UNK_M1                 BIT(20)
#define CLUSTER_PSTATE_DESIRED2               GENMASK(15, 12)
#define CLUSTER_PSTATE_APSC_BUSY              BIT(7)
#define CLUSTER_PSTATE_DESIRED1               GENMASK(4, 0)
#define CLUSTER_PSTATE_DESIRED1_S5L8960X      GENMASK(24, 22)

#define PMGR_VOLTAGE_CTL_OFF_S5L8960X 0x20c00
#define PMGR_VOLTAGE_CTL_OFF_T7000    0x23000
#define PMGR_VOLTAGE_CTL_OFF_S8000    0xa0000

#define CLUSTER_SWITCH_TIMEOUT 400

struct cluster_t {
    const char *name;
    u64 base;
    bool pcluster;
    uint32_t apsc_pstate;
    uint32_t default_pstate;
};

struct feat_t {
    const char *name;
    u64 offset;
    u64 clear;
    u64 set;
    u64 wait;
    bool pcluster_only;
};

static u32 pstate_reg_to_pstate(u64 val)
{
    switch (chip_id) {
        case S5L8960X:
        case T7000:
        case T7001:
            return FIELD_GET(CLUSTER_PSTATE_DESIRED1_S5L8960X, val);
        case S8000:
        case S8001:
        case S8003:
        case T8010:
        case T8011:
        case T8012:
        case T8015:
        case T8103:
        case T6000:
        case T6001:
        case T6002:
        case T8112:
        case T6020:
        case T6021:
        case T6022:
        case T6031:
            return FIELD_GET(CLUSTER_PSTATE_DESIRED1, val);
        default:
            printf("cpufreq: Chip 0x%x is unsupported\n", chip_id);
            return 0;
    }
}

static int set_pstate(const struct cluster_t *cluster, uint32_t pstate)
{
    u64 val = read64(cluster->base + CLUSTER_PSTATE);

    if (pstate_reg_to_pstate(val) != pstate) {
        switch (chip_id) {
            case S5L8960X:
            case T7000:
            case T7001:
                val &= ~CLUSTER_PSTATE_DESIRED1_S5L8960X;
                val |= CLUSTER_PSTATE_SET | FIELD_PREP(CLUSTER_PSTATE_DESIRED1_S5L8960X, pstate);
                break;
            case S8000:
            case S8001:
            case S8003:
            case T8010:
            case T8011:
            case T8012:
            case T8015:
            case T8103:
            case T6000:
            case T6001:
            case T6002:
                val &= ~CLUSTER_PSTATE_DESIRED2;
                val |= CLUSTER_PSTATE_SET | FIELD_PREP(CLUSTER_PSTATE_DESIRED2, pstate);
                /* fallthrough */
            case T8112:
            case T6020:
            case T6021:
            case T6022:
            case T6031:
                val &= ~CLUSTER_PSTATE_DESIRED1;
                val |= CLUSTER_PSTATE_SET | FIELD_PREP(CLUSTER_PSTATE_DESIRED1, pstate);
                break;
            default:
                printf("cpufreq: Chip 0x%x is unsupported\n", chip_id);
                return -1;
        }
        write64(cluster->base + CLUSTER_PSTATE, val);
        if (poll64(cluster->base + CLUSTER_PSTATE, CLUSTER_PSTATE_BUSY, 0, CLUSTER_SWITCH_TIMEOUT) <
            0) {
            printf("cpufreq: Timed out waiting for cluster %s P-State switch\n", cluster->name);
            return -1;
        }
    }

    return 0;
}

int cpufreq_init_cluster(const struct cluster_t *cluster, const struct feat_t *features)
{
    /* Reset P-State to the APSC p-state */

    if (cluster->apsc_pstate && set_pstate(cluster, cluster->apsc_pstate))
        return -1;

    /* CPU complex features */

    for (; features->name; features++) {
        if (features->pcluster_only && !cluster->pcluster)
            continue;

        u64 reg = cluster->base + features->offset;

        if (pmgr_get_feature(features->name))
            mask64(reg, features->clear, features->set);
        else
            mask64(reg, features->set, features->clear);

        if (features->wait && poll32(reg, features->wait, 0, CLUSTER_SWITCH_TIMEOUT) < 0) {
            printf("cpufreq: Timed out waiting for feature %s on cluster %s\n", features->name,
                   cluster->name);
            return -1;
        }
    }

    int pmgr_path[8];
    u64 pmgr_reg;

    if (adt_path_offset_trace(adt, "/arm-io/pmgr", pmgr_path) < 0) {
        printf("Error getting /arm-io/pmgr node\n");
        return -1;
    }

    if (adt_get_reg(adt, pmgr_path, "reg", 0, &pmgr_reg, NULL) < 0) {
        printf("Error getting /arm-io/pmgr regs\n");
        return -1;
    }

    switch (chip_id) {
        case S5L8960X:
            write32(pmgr_reg + PMGR_VOLTAGE_CTL_OFF_S5L8960X, 1);
            break;
        case T7000:
        case T7001:
            write32(pmgr_reg + PMGR_VOLTAGE_CTL_OFF_T7000, 1);
            break;
        case S8000:
        case S8001:
        case S8003:
        case T8010:
        case T8011:
        case T8012:
        case T8015:
            /*
             * On T8015 this will result in the register being written
             * two times (for two clusters). However, this is fine.
             */
            write32(pmgr_reg + PMGR_VOLTAGE_CTL_OFF_S8000, 1);
            break;
        case T8103:
        case T6000:
        case T6001:
        case T6002:
        case T8112:
        case T6020:
        case T6021:
        case T6022:
        case T6031:
            /* Unknown */
            write64(cluster->base + 0x440f8, 1);

            /* Initialize APSC */
            set64(cluster->base + 0x200f8, BIT(40));
            break;
        default:
            printf("cpufreq: Chip 0x%x is unsupported\n", chip_id);
            break;
    }

    switch (chip_id) {
        case T8103: {
            u64 lo = read64(cluster->base + 0x70000 + cluster->apsc_pstate * 0x20);
            u64 hi = read64(cluster->base + 0x70008 + cluster->apsc_pstate * 0x20);
            write64(cluster->base + 0x70210, lo);
            write64(cluster->base + 0x70218, hi);
            break;
        }
        case T8112: {
            u64 lo = read64(cluster->base + 0x78000 + cluster->apsc_pstate * 0x40);
            u64 hi = read64(cluster->base + 0x78008 + cluster->apsc_pstate * 0x40);
            write64(cluster->base + 0x7ffe8, lo);
            write64(cluster->base + 0x7fff0, hi);
            break;
        }
    }

    /* Default P-State */
    if (cluster->default_pstate && set_pstate(cluster, cluster->default_pstate))
        return -1;

    return 0;
}

void cpufreq_fixup_cluster(const struct cluster_t *cluster)
{
    u64 val = read64(cluster->base + CLUSTER_PSTATE);

    // Older versions of m1n1 stage 1 erroneously cleared CLUSTER_PSTATE_UNK_Mx, so put it back for
    // firmwares it supported (don't touch anything newer, which includes newer devices).
    // Also clear the CLUSTER_PSTATE_DESIRED2 field since it doesn't seem to do anything, and isn't
    // used on newer chips.
    if (os_firmware.version != V_UNKNOWN && os_firmware.version <= V13_3) {
        u64 bits = 0;
        switch (chip_id) {
            case T8103:
            case T6000:
            case T6001:
            case T6002:
                bits = CLUSTER_PSTATE_UNK_M1;
                break;
            case T8112:
            case T6020:
            case T6021:
            case T6022:
                bits = CLUSTER_PSTATE_UNK_M2;
                break;
            default:
                return;
        }
        if (!(val & bits) || (val & CLUSTER_PSTATE_DESIRED2)) {
            val |= bits;
            val &= ~CLUSTER_PSTATE_DESIRED2;
            printf("cpufreq: Correcting setting for cluster %s\n", cluster->name);
            write64(cluster->base + CLUSTER_PSTATE, val);
        }
    }
}

static const struct cluster_t s5l8960x_clusters[] = {
    {"CPU", 0x202200000, false, 2, 6},
    {},
};

static const struct cluster_t t7000_clusters[] = {
    {"CPU", 0x202200000, false, 2, 5},
    {},
};

static const struct cluster_t t7001_clusters[] = {
    {"CPU", 0x202200000, false, 2, 7},
    {},
};

static const struct cluster_t s8000_clusters[] = {
    {"CPU", 0x202200000, false, 2, 7},
    {},
};

static const struct cluster_t t8010_clusters[] = {
    /* Fused cluster, kernel expects E-core entry */
    {"CPU", 0x202f00000, false, 2, 4},
    {},
};

static const struct cluster_t t8012_clusters[] = {
    /* Fused cluster, kernel expects P-core entry */
    {"CPU", 0x202f00000, false, 6, 10},
    {},
};

static const struct cluster_t t8015_clusters[] = {
    {"ECPU", 0x208e00000, false, 2, 6},
    {"PCPU", 0x208e80000, true, 2, 7},
    {},
};

static const struct cluster_t t8103_clusters[] = {
    {"ECPU", 0x210e00000, false, 1, 5},
    {"PCPU", 0x211e00000, true, 1, 7},
    {},
};

static const struct cluster_t t6000_clusters[] = {
    {"ECPU0", 0x210e00000, false, 1, 5},
    {"PCPU0", 0x211e00000, true, 1, 7},
    {"PCPU1", 0x212e00000, true, 1, 7},
    {},
};

static const struct cluster_t t6002_clusters[] = {
    {"ECPU0", 0x0210e00000, false, 1, 5},
    {"PCPU0", 0x0211e00000, true, 1, 7},
    {"PCPU1", 0x0212e00000, true, 1, 7},
    {"ECPU1", 0x2210e00000, false, 1, 5},
    {"PCPU2", 0x2211e00000, true, 1, 7},
    {"PCPU3", 0x2212e00000, true, 1, 7},
    {},
};

static const struct cluster_t t8112_clusters[] = {
    {"ECPU", 0x210e00000, false, 1, 7},
    {"PCPU", 0x211e00000, true, 1, 6},
    {},
};

static const struct cluster_t t6020_clusters[] = {
    {"ECPU0", 0x210e00000, false, 1, 5},
    {"PCPU0", 0x211e00000, true, 1, 6},
    {"PCPU1", 0x212e00000, true, 1, 6},
    {},
};

static const struct cluster_t t6022_clusters[] = {
    {"ECPU0", 0x0210e00000, false, 1, 5},
    {"PCPU0", 0x0211e00000, true, 1, 6},
    {"PCPU1", 0x0212e00000, true, 1, 6},
    {"ECPU1", 0x2210e00000, false, 1, 5},
    {"PCPU2", 0x2211e00000, true, 1, 6},
    {"PCPU3", 0x2212e00000, true, 1, 6},
    {},
};

static const struct cluster_t t6031_clusters[] = {
    {"ECPU0", 0x210e00000, false, 1, 5},
    {"PCPU0", 0x211e00000, true, 1, 6},
    {"PCPU1", 0x212e00000, true, 1, 6},
    {},
};

static const struct cluster_t t6030_clusters[] = {
    {"ECPU0", 0x210e00000, false, 1, 5},
    {"PCPU0", 0x211e00000, true, 1, 6},
    {},
};

const struct cluster_t *cpufreq_get_clusters(void)
{
    switch (chip_id) {
        case S5L8960X:
            return s5l8960x_clusters;
        case T7000:
            return t7000_clusters;
        case T7001:
            return t7001_clusters;
        case S8000:
        case S8001:
        case S8003:
            return s8000_clusters;
        case T8010:
        case T8011:
            return t8010_clusters;
        case T8012:
            return t8012_clusters;
        case T8015:
            return t8015_clusters;
        case T8103:
            return t8103_clusters;
        case T6000:
        case T6001:
            return t6000_clusters;
        case T6002:
            return t6002_clusters;
        case T8112:
            return t8112_clusters;
        case T6020:
        case T6021:
            return t6020_clusters;
        case T6022:
            return t6022_clusters;
        case T6030:
            return t6030_clusters;
        case T6031:
            return t6031_clusters;
        default:
            printf("cpufreq: Chip 0x%x is unsupported\n", chip_id);
            return NULL;
    }
}

static const struct feat_t s5l8960x_features[] = {
    {},
};

static const struct feat_t s8000_features[] = {
    {"cpu-apsc", CLUSTER_PSTATE, CLUSTER_PSTATE_M1_APSC_DIS, 0, CLUSTER_PSTATE_APSC_BUSY, false},
    {},
};

static const struct feat_t t8010_features[] = {
    {"cpu-apsc", CLUSTER_PSTATE, CLUSTER_PSTATE_M1_APSC_DIS, 0, CLUSTER_PSTATE_APSC_BUSY, false},
    {},
};

static const struct feat_t t8015_features[] = {
    {"cpu-apsc", CLUSTER_PSTATE, CLUSTER_PSTATE_M1_APSC_DIS, 0, CLUSTER_PSTATE_APSC_BUSY, false},
    {"cpu-fixed-freq-pll-relock", CLUSTER_PSTATE, 0, CLUSTER_PSTATE_FIXED_FREQ_PLL_RECLOCK, 0,
     false},
    {},
};

static const struct feat_t t8103_features[] = {
    {"cpu-apsc", CLUSTER_PSTATE, CLUSTER_PSTATE_M1_APSC_DIS, 0, CLUSTER_PSTATE_APSC_BUSY, false},
    {"ppt-thrtl", 0x48400, 0, BIT(63), 0, false},
    {"llc-thrtl", 0x40240, 0, BIT(63), 0, false},
    {"amx-thrtl", 0x40250, 0, BIT(63), 0, false},
    {"cpu-fixed-freq-pll-relock", CLUSTER_PSTATE, 0, CLUSTER_PSTATE_FIXED_FREQ_PLL_RECLOCK, 0,
     false},
    {},
};

static const struct feat_t t8112_features[] = {
    {"cpu-apsc", CLUSTER_PSTATE, CLUSTER_PSTATE_M2_APSC_DIS, 0, CLUSTER_PSTATE_APSC_BUSY, false},
    {"ppt-thrtl", 0x40270, 0, BIT(63), 0, false},
    {"ppt-thrtl", 0x48408, 0, BIT(63), 0, false},
    {"ppt-thrtl", 0x48b30, 0, BIT(0), 0, true},
    {"ppt-thrtl", 0x20078, 0, BIT(0), 0, true},
    {"ppt-thrtl", 0x48400, 0, BIT(63), 0, false},
    {"amx-thrtl", 0x40250, 0, BIT(63), 0, false},
    {"cpu-fixed-freq-pll-relock", CLUSTER_PSTATE, 0, CLUSTER_PSTATE_FIXED_FREQ_PLL_RECLOCK, 0,
     false},
    {},
};

static const struct feat_t t6020_features[] = {
    {"cpu-apsc", CLUSTER_PSTATE, CLUSTER_PSTATE_M2_APSC_DIS, 0, CLUSTER_PSTATE_APSC_BUSY, false},
    {"ppt-thrtl", 0x48400, 0, BIT(63), 0, false},
    {"llc-thrtl", 0x40270, 0, BIT(63), 0, false},
    {"amx-thrtl", 0x40250, 0, BIT(63), 0, false},
    {"cpu-fixed-freq-pll-relock", CLUSTER_PSTATE, 0, CLUSTER_PSTATE_FIXED_FREQ_PLL_RECLOCK, 0,
     false},
    {},
};

static const struct feat_t t6030_features[] = {
    {"cpu-apsc", CLUSTER_PSTATE, CLUSTER_PSTATE_M2_APSC_DIS, 0, CLUSTER_PSTATE_APSC_BUSY, false},
    {"ppt-thrtl", 0x48400, 0, BIT(63), 0, false},
    {"ppt-thrtl", 0x48408, 0, BIT(63), 0, false},
    {"llc-thrtl", 0x40270, 0, BIT(63), 0, false},
    {"amx-thrtl", 0x40250, 0, BIT(63), 0, false},
    {"cpu-fixed-freq-pll-relock", CLUSTER_PSTATE, 0, CLUSTER_PSTATE_FIXED_FREQ_PLL_RECLOCK, 0,
     false},
    {},
};

static const struct feat_t t6031_features[] = {
    {"cpu-apsc", CLUSTER_PSTATE, CLUSTER_PSTATE_M2_APSC_DIS, 0, CLUSTER_PSTATE_APSC_BUSY, false},
    {"ppt-thrtl", 0x48400, 0, BIT(63), 0, false},
    {"llc-thrtl", 0x40270, 0, BIT(63), 0, false},
    {"amx-thrtl", 0x40250, 0, BIT(63), 0, false},
    {"cpu-fixed-freq-pll-relock", CLUSTER_PSTATE, 0, CLUSTER_PSTATE_FIXED_FREQ_PLL_RECLOCK, 0,
     false},
    {},
};

const struct feat_t *cpufreq_get_features(void)
{
    switch (chip_id) {
        case S5L8960X:
        case T7000:
        case T7001:
            return s5l8960x_features;
        case S8000:
        case S8001:
        case S8003:
            return s8000_features;
        case T8010:
        case T8011:
        case T8012:
            return t8010_features;
        case T8015:
            return t8015_features;
        case T8103:
        case T6000:
        case T6001:
        case T6002:
            return t8103_features;
        case T8112:
            return t8112_features;
        case T6020:
        case T6021:
        case T6022:
            return t6020_features;
        case T6030:
            return t6030_features;
        case T6031:
            return t6031_features;
        default:
            printf("cpufreq: Chip 0x%x is unsupported\n", chip_id);
            return NULL;
    }
}

int cpufreq_init(void)
{
    printf("cpufreq: Initializing clusters\n");

    const struct cluster_t *cluster = cpufreq_get_clusters();
    const struct feat_t *features = cpufreq_get_features();

    if (!cluster || !features)
        return -1;

    /* Without this, CLUSTER_PSTATE_BUSY gets stuck */
    if (chip_id == T8012 || chip_id == T8015)
        pmgr_power_on(0, "SPMI");

    bool err = false;
    while (cluster->base) {
        err |= cpufreq_init_cluster(cluster++, features);
    }

    return err ? -1 : 0;
}

void cpufreq_fixup(void)
{
    const struct cluster_t *cluster = cpufreq_get_clusters();

    if (!cluster)
        return;

    while (cluster->base) {
        cpufreq_fixup_cluster(cluster++);
    }
}

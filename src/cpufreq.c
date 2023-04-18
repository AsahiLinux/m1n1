/* SPDX-License-Identifier: MIT */

#include "cpufreq.h"
#include "adt.h"
#include "firmware.h"
#include "soc.h"
#include "utils.h"

#define CLUSTER_PSTATE 0x20
#define CLUSTER_CONFIG 0x6b8

#define CLUSTER_PSTATE_BUSY     BIT(31)
#define CLUSTER_PSTATE_SET      BIT(25)
#define CLUSTER_PSTATE_UNK_M2   BIT(22)
#define CLUSTER_PSTATE_UNK_M1   BIT(20)
#define CLUSTER_PSTATE_DESIRED2 GENMASK(16, 12)
#define CLUSTER_PSTATE_DESIRED1 GENMASK(4, 0)

#define CLUSTER_CONFIG_ENABLE BIT(63)
#define CLUSTER_CONFIG_DVMR1  BIT(32)
#define CLUSTER_CONFIG_DVMR2  BIT(31)

#define CLUSTER_SWITCH_TIMEOUT 100

struct cluster_t {
    const char *name;
    u64 base;
    bool dvmr;
    uint32_t boot_pstate;
};

int cpufreq_init_cluster(const struct cluster_t *cluster)
{
    u64 enable = CLUSTER_CONFIG_ENABLE;
    if (cluster->dvmr)
        enable |= CLUSTER_CONFIG_DVMR1 | CLUSTER_CONFIG_DVMR2;

    u64 val = read64(cluster->base + CLUSTER_CONFIG);
    if ((val & enable) != enable) {
        printf("cpufreq: Configuring cluster %s (dvmr: %d)\n", cluster->name, cluster->dvmr);
        write64(cluster->base + CLUSTER_CONFIG, val | enable);
    }

    val = read64(cluster->base + CLUSTER_PSTATE);

    if (FIELD_GET(CLUSTER_PSTATE_DESIRED1, val) != cluster->boot_pstate) {
        val &= ~CLUSTER_PSTATE_DESIRED1;
        val |= CLUSTER_PSTATE_SET | FIELD_PREP(CLUSTER_PSTATE_DESIRED1, cluster->boot_pstate);
        printf("cpufreq: Switching cluster %s to P-State %d\n", cluster->name,
               cluster->boot_pstate);
        write64(cluster->base + CLUSTER_PSTATE, val);
        if (poll32(cluster->base + CLUSTER_PSTATE, CLUSTER_PSTATE_BUSY, 0, CLUSTER_SWITCH_TIMEOUT) <
            0) {
            printf("cpufreq: Timed out waiting for cluster %s P-State switch\n", cluster->name);
            return -1;
        }
    }

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
            case T6000 ... T6002:
                bits = CLUSTER_PSTATE_UNK_M1;
                break;
            case T8112:
            case T6020 ... T6021:
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

static const struct cluster_t t8103_clusters[] = {
    {"ECPU", 0x210e20000, false, 5},
    {"PCPU", 0x211e20000, true, 7},
    {},
};

static const struct cluster_t t6000_clusters[] = {
    {"ECPU0", 0x210e20000, false, 5},
    {"PCPU0", 0x211e20000, false, 7},
    {"PCPU1", 0x212e20000, false, 7},
    {},
};

static const struct cluster_t t6002_clusters[] = {
    {"ECPU0", 0x0210e20000, false, 5},
    {"PCPU0", 0x0211e20000, false, 7},
    {"PCPU1", 0x0212e20000, false, 7},
    {"ECPU1", 0x2210e20000, false, 5},
    {"PCPU2", 0x2211e20000, false, 7},
    {"PCPU3", 0x2212e20000, false, 7},
    {},
};

static const struct cluster_t t8112_clusters[] = {
    {"ECPU", 0x210e20000, false, 7},
    {"PCPU", 0x211e20000, true, 6},
    {},
};

static const struct cluster_t t6020_clusters[] = {
    {"ECPU0", 0x210e20000, false, 5},
    {"PCPU0", 0x211e20000, false, 6},
    {"PCPU1", 0x212e20000, false, 6},
    {},
};

const struct cluster_t *cpufreq_get_clusters(void)
{
    switch (chip_id) {
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
        default:
            printf("cpufreq: Chip 0x%x is unsupported\n", chip_id);
            return NULL;
    }
}

int cpufreq_init(void)
{
    printf("cpufreq: Initializing clusters\n");

    const struct cluster_t *cluster = cpufreq_get_clusters();

    if (!cluster)
        return -1;

    bool err = false;
    while (cluster->base) {
        err |= cpufreq_init_cluster(cluster++);
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

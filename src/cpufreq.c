/* SPDX-License-Identifier: MIT */

#include "cpufreq.h"
#include "adt.h"
#include "soc.h"
#include "utils.h"

#define CLUSTER_PSTATE 0x20
#define CLUSTER_CONFIG 0x6b8

#define CLUSTER_PSTATE_BUSY     BIT(31)
#define CLUSTER_PSTATE_SET      BIT(25)
#define CLUSTER_PSTATE_DESIRED2 GENMASK(15, 12)
#define CLUSTER_PSTATE_DESIRED1 GENMASK(3, 0)

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
        val &= CLUSTER_PSTATE_DESIRED1 | CLUSTER_PSTATE_DESIRED2;
        val |= CLUSTER_PSTATE_SET | FIELD_PREP(CLUSTER_PSTATE_DESIRED1, cluster->boot_pstate) |
               FIELD_PREP(CLUSTER_PSTATE_DESIRED2, cluster->boot_pstate);
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

static const struct cluster_t t6021_clusters[] = {
    {"ECPU0", 0x210e20000, false, 5},
    {"PCPU0", 0x211e20000, false, 6},
    {"PCPU1", 0x212e20000, false, 6},
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

int cpufreq_init(void)
{
    printf("cpufreq: Initializing clusters\n");

    const struct cluster_t *cluster;

    switch (chip_id) {
        case T8103:
            cluster = t8103_clusters;
            break;
        case T6000:
        case T6001:
            cluster = t6000_clusters;
            break;
        case T6002:
            cluster = t6002_clusters;
            break;
        case T6021:
            cluster = t6021_clusters;
            break;
        case T8112:
            cluster = t8112_clusters;
            break;
        default:
            printf("cpufreq: Chip 0x%x is unsupported\n", chip_id);
            return -1;
    }

    bool err = false;
    while (cluster->base) {
        err |= cpufreq_init_cluster(cluster++);
    }

    return err ? -1 : 0;
}

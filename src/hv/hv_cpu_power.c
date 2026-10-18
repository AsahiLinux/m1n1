/* SPDX-License-Identifier: GPL-2.0-or-later */

#include <string.h>

#include "adt.h"
#include "hv.h"
#include "hv_sprr.h"
#include "smp.h"
#include "utils.h"

struct power_control {
    u64 base, value;
};

#define CPU_CONTROL_OFFSET 0x9000UL
static struct power_control cpu_control[MAX_CPUS * 2];
static u32 cpu_control_count;

/*
 * Each CPU belongs to a cluster so there will never be more than MAX_CPUs here.
 * For the cluster controls there are three offsets that directly trigger an
 * SError and 12 additional offsets which are all 0x10 apart that seem to cause
 * delayed SErrors. No idea what any of this does but ignoring writes and just
 * return whatever was written last for reads works.
 */
#define CPM_SERROR_0   0x8000
#define CPM_SERROR_1   0x8008
#define CPM_SERROR_2   0x40f8
#define CPM_SLOT_COUNT 12
static struct power_control cpm_control[MAX_CPUS][3 + CPM_SLOT_COUNT];
static u32 cpm_control_count;

static bool power_control_hook(struct power_control *control, u32 count, u64 ipa, u64 *val,
                               bool write, int width)
{
    if (width != 3)
        return false;

    for (u32 i = 0; i < count; i++) {
        if (ipa != control[i].base)
            continue;
        if (write)
            control[i].value = *val;
        else
            *val = control[i].value;
        return true;
    }

    return false;
}

static bool hv_power_control_hook(__always_unused struct exc_info *ctx, u64 ipa, u64 *val,
                                  bool write, int width)
{
    if (power_control_hook(cpu_control, cpu_control_count, ipa, val, write, width))
        return true;

    for (u32 i = 0; i < cpm_control_count; i++) {
        if (power_control_hook(cpm_control[i], ARRAY_SIZE(cpm_control[i]), ipa, val, write, width))
            return true;
    }

    return false;
}

static bool power_control_map(struct power_control *control, u32 count)
{
    for (u32 i = 0; i < count; i++) {
        if (hv_map_hook(control[i].base, hv_power_control_hook, sizeof(u64)) < 0)
            return false;
    }

    return true;
}

bool hv_cpu_power_init(void)
{
    if (hv_sptm_mode != SPTM_EMULATION)
        return true;

    cpu_control_count = 0;
    cpm_control_count = 0;
    memset(cpu_control, 0, sizeof(cpu_control));
    memset(cpm_control, 0, sizeof(cpm_control));

    int node = adt_path_offset(adt, "/cpus");
    if (node < 0)
        return false;

    ADT_FOREACH_CHILD(adt, node)
    {
        u64 reg[2];
        if (ADT_GETPROP_ARRAY(adt, node, "cpu-impl-reg", reg) != sizeof(reg))
            return false;
        if (cpu_control_count == ARRAY_SIZE(cpu_control))
            return false;

        cpu_control[cpu_control_count++] =
            (struct power_control){.base = reg[0] + CPU_CONTROL_OFFSET};
        cpu_control[cpu_control_count++] =
            (struct power_control){.base = reg[0] + CPU_CONTROL_OFFSET + sizeof(u64)};

        if (ADT_GETPROP_ARRAY(adt, node, "cpm-impl-reg", reg) != sizeof(reg))
            return false;

        u64 base = reg[0];
        u32 i;
        for (i = 0; i < cpm_control_count; i++) {
            if (cpm_control[i][0].base == base + 0x8000)
                break;
        }

        if (i < cpm_control_count)
            continue;

        cpm_control_count++;

        /* These directly result in SErrors with the address in the L2C_ERR registers */
        cpm_control[i][0] = (struct power_control){.base = base + CPM_SERROR_0};
        cpm_control[i][1] = (struct power_control){.base = base + CPM_SERROR_1};
        cpm_control[i][2] = (struct power_control){.base = base + CPM_SERROR_2};

        /* These *probably* cause delayed SErrors */
        for (u32 slot = 0; slot < CPM_SLOT_COUNT; slot++)
            cpm_control[i][3 + slot] = (struct power_control){.base = base + 0x4008 + slot * 0x10};
    }

    if (!power_control_map(cpu_control, cpu_control_count))
        return false;

    for (u32 i = 0; i < cpm_control_count; i++) {
        if (!power_control_map(cpm_control[i], ARRAY_SIZE(cpm_control[i])))
            return false;
    }

    sysop("dsb ishst");
    sysop("tlbi vmalls12e1is");
    sysop("dsb ish");
    sysop("isb");

    return true;
}

/* SPDX-License-Identifier: MIT */

#include "tunables.h"
#include "adt.h"
#include "pmgr.h"
#include "soc.h"
#include "types.h"
#include "utils.h"

/*
 * These magic tunable sequences are hardcoded in various places in XNU, and are required for
 * proper operation of various fabric features and other miscellanea. Without them, things tend
 * to subtly break...
 */

struct entry {
    u32 offset;
    u32 clear;
    u32 set;
};

struct entry t8103_agx_tunables[] = {
    {0x30, 0xffffffff, 0x50014},     {0x34, 0xffffffff, 0xa003c},
    {0x400, 0x400103ff, 0x40010001}, {0x600, 0x1ffffff, 0x1ffffff},
    {0x738, 0x1ff01ff, 0x140034},    {0x798, 0x1ff01ff, 0x14003c},
    {0x800, 0x100, 0x100},           {-1, 0, 0},
};

static void tunables_apply(u64 base, struct entry *entry)
{
    while (entry->offset != UINT32_MAX) {
        mask32(base + entry->offset, entry->clear, entry->set);
        entry++;
    }
}

int power_and_apply(const char *path, u64 base, struct entry *entries)
{
    if (pmgr_adt_power_enable(path) < 0) {
        printf("tunables: Failed to enable power: %s\n", path);
        return -1;
    }

    tunables_apply(base, entries);

    if (pmgr_adt_power_disable(path) < 0) {
        printf("tunables: Failed to disable power: %s\n", path);
        return -1;
    }

    return 0;
}

int tunables_apply_static(void)
{
    int ret = 0;

    switch (chip_id) {
        case T8103:
            ret |= power_and_apply("/arm-io/sgx", 0x205000000, t8103_agx_tunables);
            break;
        default:
            break;
    }

    return ret ? -1 : 0;
}

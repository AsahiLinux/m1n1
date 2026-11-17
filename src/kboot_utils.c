/* SPDX-License-Identifier: GPL-2.0-or-later */

#include <string.h>

#include "kboot_utils.h"
#include "adt.h"
#include "pmgr.h"
#include "utils.h"

#define bail(...)                                                                                  \
    do {                                                                                           \
        printf(__VA_ARGS__);                                                                       \
        return -1;                                                                                 \
    } while (0)

int adt_device_prefix_addrs(const char *adt_prefix, int max_devs, int regnum,
                            adt_dev_node_address devs[ADT_MAX_PREFIX_DEVS])
{
    int adt_prefix_len = strlen(adt_prefix);
    int count = 0;
    int path[8];

    if (max_devs > ADT_MAX_PREFIX_DEVS)
        bail("ADT: max_devs exceeds ADT_MAX_PREFIX_DEVS (%d)\n", ADT_MAX_PREFIX_DEVS);

    int node = adt_path_offset_trace(adt, "/arm-io", path);
    if (node < 0)
        bail("ADT: /arm-io not found\n");

    int pp = 0;
    while (path[pp])
        pp++;
    path[pp + 1] = 0;

    /* Find ADT registers */
    ADT_FOREACH_CHILD(adt, node)
    {
        const char *name = adt_get_name(adt, node);
        if (strncmp(name, adt_prefix, adt_prefix_len))
            continue;

        if (name[adt_prefix_len] < '0' || name[adt_prefix_len] > '9')
            continue;

        path[pp] = node;
        devs[count].node = node;
        devs[count].port = name[adt_prefix_len] - '0';
        if (adt_get_reg(adt, path, "reg", regnum, &devs[count++].address, NULL) < 0)
            bail("Error getting /arm-io/%s regs\n", name);
    }

    return count;
}

int adt_die_count(void)
{
    int node = adt_path_offset(adt, "/arm-io");
    int die_count;

    if (ADT_GETPROP(adt, node, "die-count", &die_count) < 0) {
        die_count = 1;
    }
    if (die_count > 8) {
        printf("ADT: limiting die-count from %u to 8\n", die_count);
        die_count = 8;
    }

    return die_count;
}

int dt_get_soc_path(char *path, size_t size, int die, int die_count)
{
    if (die_count > 1) {
        u64 die_unit_addr = die * PMGR_DIE_OFFSET + 0x200000000;
        return snprintf(path, size, "/soc@%lx", die_unit_addr);
    }

    return snprintf(path, size, "/soc");
}

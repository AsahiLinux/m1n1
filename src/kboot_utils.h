/* SPDX-License-Identifier: GPL-2.0-or-later */

#ifndef KBOOT_UTILS_H
#define KBOOT_UTILS_H

#include "types.h"

#define ADT_MAX_PREFIX_DEVS 8

typedef struct adt_dev_node_address {
    u64 address;
    int node;
    u8 port;
} adt_dev_node_address;

int adt_device_prefix_addrs(const char *adt_prefix, int max_devs, int regnum,
                            adt_dev_node_address devs[ADT_MAX_PREFIX_DEVS]);
int adt_die_count(void);

int dt_get_soc_path(char *path, size_t size, int die, int die_count);

#endif /* KBOOT_UTILS_H */

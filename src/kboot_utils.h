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

typedef int(kboot_match_t)(void *dt, int adt_node, int node_offset, int index, void *data);

int kboot_setup_matching_nodes(void *dt, int max_devices, const char *adt_prefix, int adt_reg_idx,
                               const char **compatibles, size_t num_compatibles, int fdt_reg_idx,
                               kboot_match_t *match_action, void *action_data);

#endif /* KBOOT_UTILS_H */

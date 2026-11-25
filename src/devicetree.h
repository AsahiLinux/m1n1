/* SPDX-License-Identifier: GPL-2.0-or-later */

#ifndef DEVICETREE_H
#define DEVICETREE_H

#include "types.h"

#include "libfdt/libfdt.h"

#define DT_MAX_RANGES 8

struct dt_ranges_tbl {
    u64 start;
    u64 parent;
    u64 size;
};

void dt_parse_ranges(void *dt, int node, struct dt_ranges_tbl *ranges);
u64 dt_translate(struct dt_ranges_tbl *ranges, const fdt64_t *reg);
u64 dt_get_address(void *dt, int node);
u64 dt_get_address_translated(void *dt, int node, unsigned index, struct dt_ranges_tbl *ranges);

/**
 * dt_node_is_compatible: check a node's compatible property against a list of compatibles
 * @fdt: pointer to the device tree blob
 * @nodeoffset: offset of a tree node
 * @compatibles: string list to match against
 * @num_compatibles: number of strings in `@compatibles`
 *
 * dt_node_check_compatible_any() returns `true` if the given node contains a
 * 'compatible' property matching one of the given strings as one of its elements,
 * it returns `false` otherwise, or on error.
 *
 * returns:
 *	true, if the node has a 'compatible' property listing one of the given strings
 *	false, otherwise
 */
bool dt_node_is_compatible(const void *fdt, int nodeoffset, const char **compatibles,
                           size_t num_compatibles);

#endif

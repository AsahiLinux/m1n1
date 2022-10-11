/* SPDX-License-Identifier: MIT */

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

#endif

/* SPDX-License-Identifier: (GPL-2.0-or-later OR BSD-2-Clause) */

#ifndef XDT_H
#define XDT_H

#include "types.h"

extern void *adt;

struct adt_property {
    char name[32];
    u32 size;
    u8 value[];
};

struct adt_node_hdr {
    u32 property_count;
    u32 child_count;
};

#define ADT_PROP(adt, offset) ((const struct adt_property *)(((u8 *)(adt)) + (offset)))

/* This API is designed to match libfdt's read-only API */

/* Required for Rust until we move xnuboot across */
u32 adt_get_size(void);

/* Basic sanity check */
int adt_check_header(const void *adt);

int adt_get_property_count(const void *adt, int offset);

int adt_first_property_offset(const void *adt, int offset);

int adt_next_property_offset(const void *adt, int offset);

const struct adt_property *adt_get_property_by_offset(const void *adt, int offset);

int adt_get_child_count(const void *adt, int offset);

int adt_first_child_offset(const void *adt, int offset);
int adt_next_sibling_offset(const void *adt, int offset);

int adt_subnode_offset(const void *adt, int parentoffset, const char *name);
int adt_path_offset(const void *adt, const char *path);
int adt_path_offset_trace(const void *adt, const char *path, int *offsets);

const char *adt_get_name(const void *adt, int nodeoffset);
const struct adt_property *adt_get_property(const void *adt, int nodeoffset, const char *name);
const void *adt_getprop_by_offset(const void *adt, int offset, const char **namep, u32 *lenp);
const void *adt_getprop(const void *adt, int nodeoffset, const char *name, u32 *lenp);
int adt_setprop(void *adt, int nodeoffset, const char *name, void *value, size_t len);
int adt_getprop_copy(const void *adt, int nodeoffset, const char *name, void *out, size_t len);

#define ADT_GETPROP(adt, nodeoffset, name, val)                                                    \
    adt_getprop_copy(adt, nodeoffset, name, (val), sizeof(*(val)))

#define ADT_GETPROP_ARRAY(adt, nodeoffset, name, arr)                                              \
    adt_getprop_copy(adt, nodeoffset, name, (arr), sizeof(arr))

int adt_get_reg(const void *adt, int *path, const char *prop, int idx, u64 *addr, u64 *size);
bool adt_is_compatible(const void *adt, int nodeoffset, const char *compat);
bool adt_is_compatible_at(const void *adt, int nodeoffset, const char *compat, size_t index);

#define ADT_FOREACH_CHILD(adt, node)                                                               \
    for (int _child_count = adt_get_child_count(adt, node); _child_count; _child_count = 0)        \
        for (node = adt_first_child_offset(adt, node); _child_count--;                             \
             node = adt_next_sibling_offset(adt, node))

/* Common ADT properties */
struct adt_segment_ranges {
    u64 phys;
    u64 iova;
    u64 remap;
    u32 size;
    u32 unk;
} PACKED;

#endif

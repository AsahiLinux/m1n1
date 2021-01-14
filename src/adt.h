/* SPDX-License-Identifier: (GPL-2.0-or-later OR BSD-2-Clause) */

#ifndef XDT_H
#define XDT_H

#include <stdint.h>

#define ADT_ERR_NOTFOUND 1
#define ADT_ERR_BADOFFSET 4
#define ADT_ERR_BADLENGTH 20

#define ADT_ALIGN 4

extern void *adt;

struct adt_property {
    char name[32];
    uint32_t size;
    uint8_t value[];
};

struct adt_node_hdr {
    uint32_t property_count;
    uint32_t child_count;
};

#define ADT_NODE(adt, offset)                                                  \
    ((const struct adt_node_hdr *)(((uint8_t *)(adt)) + (offset)))
#define ADT_PROP(adt, offset)                                                  \
    ((const struct adt_property *)(((uint8_t *)(adt)) + (offset)))
#define ADT_SIZE(node) ((node)->size & 0x7fffffff)

/* This API is designed to match libfdt's read-only API */

/* Basic sanity check */
int adt_check_header(const void *adt);

static inline int adt_first_property_offset(const void *adt, int offset)
{
    return offset + sizeof(struct adt_node_hdr);
}

static inline int adt_next_property_offset(const void *adt, int offset)
{
    const struct adt_property *prop = ADT_PROP(adt, offset);
    return offset + sizeof(struct adt_property) +
           ((prop->size + ADT_ALIGN - 1) & ~(ADT_ALIGN - 1));
}

static inline const struct adt_property *
adt_get_property_by_offset(const void *adt, int offset)
{
    return ADT_PROP(adt, offset);
}

int adt_first_child(const void *adt, int offset);
int adt_next_sibling(const void *adt, int offset);

int adt_subnode_offset_namelen(const void *adt, int parentoffset,
                               const char *name, int namelen);
int adt_subnode_offset(const void *adt, int parentoffset, const char *name);
int adt_path_offset(const void *adt, const char *path);
const char *adt_get_name(const void *adt, int nodeoffset);
const struct adt_property *adt_get_property_namelen(const void *adt,
                                                    int nodeoffset,
                                                    const char *name,
                                                    int namelen);
const struct adt_property *adt_get_property(const void *adt, int nodeoffset,
                                            const char *name);
const void *adt_getprop_by_offset(const void *adt, int offset,
                                  const char **namep, int *lenp);
const void *adt_getprop_namelen(const void *adt, int nodeoffset,
                                const char *name, int namelen, int *lenp);
const void *adt_getprop(const void *adt, int nodeoffset, const char *name,
                        int *lenp);
const void *adt_getprop_length(const void *adt, int nodeoffset,
                               const char *name, int len);
int adt_getprop_copy(const void *adt, int nodeoffset, const char *name,
                     void *out, int len);

#define ADT_GETPROP(adt, nodeoffset, name, val)                                \
    adt_getprop_copy(adt, nodeoffset, name, (val), sizeof(*(val)))

#endif

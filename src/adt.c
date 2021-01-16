/* SPDX-License-Identifier: (GPL-2.0-or-later OR BSD-2-Clause) */

#include "adt.h"
#include "string.h"

/* This API is designed to match libfdt's read-only API */

#define ADT_CHECK_HEADER(adt)                                                  \
    {                                                                          \
        int err;                                                               \
        if ((err = adt_check_header(adt)) != 0)                                \
            return err;                                                        \
    }

//#define DEBUG

#ifdef DEBUG
#include "utils.h"
#define dprintf printf
#else
#define dprintf(...)                                                           \
    do {                                                                       \
    } while (0)
#endif

int _adt_check_node_offset(const void *adt, int offset)
{
    if ((offset < 0) || (offset % ADT_ALIGN))
        return -ADT_ERR_BADOFFSET;

    const struct adt_node_hdr *node = ADT_NODE(adt, offset);

    // Sanity check
    if (node->property_count > 2048 || !node->property_count ||
        node->child_count > 2048)
        return -ADT_ERR_BADOFFSET;

    return 0;
}

int _adt_check_prop_offset(const void *adt, int offset)
{
    if ((offset < 0) || (offset % ADT_ALIGN))
        return -ADT_ERR_BADOFFSET;

    const struct adt_property *prop = ADT_PROP(adt, offset);

    if (prop->size & 0x7ff00000) // up to 1MB properties
        return -ADT_ERR_BADOFFSET;

    return 0;
}

int adt_check_header(const void *adt)
{
    return _adt_check_node_offset(adt, 0);
}

static int _adt_string_eq(const char *a, const char *b, size_t len)
{
    return (strlen(a) == len) && (memcmp(a, b, len) == 0);
}

static int _adt_nodename_eq(const char *a, const char *b, size_t len)
{
    if (memcmp(a, b, len) != 0)
        return 0;

    if (a[len] == '\0')
        return 1;
    else if (!memchr(b, '@', len) && (a[len] == '@'))
        return 1;
    else
        return 0;
}

const struct adt_property *adt_get_property_namelen(const void *adt, int offset,
                                                    const char *name,
                                                    size_t namelen)
{
    dprintf("adt_get_property_namelen(%p, %d, \"%s\", %u)\n", adt, offset, name,
            namelen);

    for (offset = adt_first_property_offset(adt, offset); (offset >= 0);
         (offset = adt_next_property_offset(adt, offset))) {
        const struct adt_property *prop;

        prop = adt_get_property_by_offset(adt, offset);

        dprintf(" off=0x%x name=\"%s\"\n", offset, prop->name);
        if (_adt_string_eq(prop->name, name, namelen))
            return prop;
    }

    return NULL;
}

const struct adt_property *adt_get_property(const void *adt, int nodeoffset,
                                            const char *name)
{
    return adt_get_property_namelen(adt, nodeoffset, name, strlen(name));
}

const void *adt_getprop_namelen(const void *adt, int nodeoffset,
                                const char *name, size_t namelen, u32 *lenp)
{
    const struct adt_property *prop;

    prop = adt_get_property_namelen(adt, nodeoffset, name, namelen);

    if (!prop)
        return NULL;

    if (lenp)
        *lenp = prop->size;

    return prop->value;
}

const void *adt_getprop_by_offset(const void *adt, int offset,
                                  const char **namep, u32 *lenp)
{
    const struct adt_property *prop;

    prop = adt_get_property_by_offset(adt, offset);
    if (!prop)
        return NULL;

    if (namep)
        *namep = prop->name;
    if (lenp)
        *lenp = prop->size;
    return prop->value;
}

const void *adt_getprop(const void *adt, int nodeoffset, const char *name,
                        u32 *lenp)
{
    return adt_getprop_namelen(adt, nodeoffset, name, strlen(name), lenp);
}

int adt_getprop_copy(const void *adt, int nodeoffset, const char *name,
                     void *out, size_t len)
{
    u32 plen;

    const void *p = adt_getprop(adt, nodeoffset, name, &plen);

    if (!p)
        return -ADT_ERR_NOTFOUND;

    if (plen != len)
        return -ADT_ERR_BADLENGTH;

    memcpy(out, p, len);
    return len;
}

int adt_first_child_offset(const void *adt, int offset)
{
    const struct adt_node_hdr *node = ADT_NODE(adt, offset);

    u32 cnt = node->property_count;
    offset = adt_first_property_offset(adt, offset);

    while (cnt--) {
        offset = adt_next_property_offset(adt, offset);
    }

    return offset;
}

int adt_next_sibling_offset(const void *adt, int offset)
{
    const struct adt_node_hdr *node = ADT_NODE(adt, offset);

    u32 cnt = node->child_count;
    offset = adt_first_child_offset(adt, offset);

    while (cnt--) {
        offset = adt_next_sibling_offset(adt, offset);
    }

    return offset;
}

int adt_subnode_offset_namelen(const void *adt, int offset, const char *name,
                               size_t namelen)
{
    const struct adt_node_hdr *node = ADT_NODE(adt, offset);

    ADT_CHECK_HEADER(adt);

    offset = adt_first_child_offset(adt, offset);

    for (u32 i = 0; i < node->child_count; i++) {
        const char *cname = adt_get_name(adt, offset);

        if (_adt_nodename_eq(cname, name, namelen))
            return offset;

        offset = adt_next_sibling_offset(adt, offset);
    }

    return -ADT_ERR_NOTFOUND;
}

int adt_subnode_offset(const void *adt, int parentoffset, const char *name)
{
    return adt_subnode_offset_namelen(adt, parentoffset, name, strlen(name));
}

int adt_path_offset(const void *adt, const char *path)
{
    const char *end = path + strlen(path);
    const char *p = path;
    int offset = 0;

    ADT_CHECK_HEADER(adt);

    while (*p) {
        const char *q;

        while (*p == '/')
            p++;
        if (!*p)
            return offset;
        q = strchr(p, '/');
        if (!q)
            q = end;

        offset = adt_subnode_offset_namelen(adt, offset, p, q - p);
        if (offset < 0)
            return offset;

        p = q;
    }

    return offset;
}

const char *adt_get_name(const void *adt, int nodeoffset)
{
    return adt_getprop(adt, nodeoffset, "name", NULL);
}

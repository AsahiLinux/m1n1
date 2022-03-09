/* SPDX-License-Identifier: (GPL-2.0-or-later OR BSD-2-Clause) */

#include "adt.h"
#include "string.h"

/* This API is designed to match libfdt's read-only API */

#define ADT_CHECK_HEADER(adt)                                                                      \
    {                                                                                              \
        int err;                                                                                   \
        if ((err = adt_check_header(adt)) != 0)                                                    \
            return err;                                                                            \
    }

//#define DEBUG

#ifdef DEBUG
#include "utils.h"
#define dprintf printf
#else
#define dprintf(...)                                                                               \
    do {                                                                                           \
    } while (0)
#endif

int _adt_check_node_offset(const void *adt, int offset)
{
    if ((offset < 0) || (offset % ADT_ALIGN))
        return -ADT_ERR_BADOFFSET;

    const struct adt_node_hdr *node = ADT_NODE(adt, offset);

    // Sanity check
    if (node->property_count > 2048 || !node->property_count || node->child_count > 2048)
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

const struct adt_property *adt_get_property_namelen(const void *adt, int offset, const char *name,
                                                    size_t namelen)
{
    dprintf("adt_get_property_namelen(%p, %d, \"%s\", %u)\n", adt, offset, name, namelen);

    ADT_FOREACH_PROPERTY(adt, offset, prop)
    {
        dprintf(" off=0x%x name=\"%s\"\n", offset, prop->name);
        if (_adt_string_eq(prop->name, name, namelen))
            return prop;
    }

    return NULL;
}

const struct adt_property *adt_get_property(const void *adt, int nodeoffset, const char *name)
{
    return adt_get_property_namelen(adt, nodeoffset, name, strlen(name));
}

const void *adt_getprop_namelen(const void *adt, int nodeoffset, const char *name, size_t namelen,
                                u32 *lenp)
{
    const struct adt_property *prop;

    prop = adt_get_property_namelen(adt, nodeoffset, name, namelen);

    if (!prop)
        return NULL;

    if (lenp)
        *lenp = prop->size;

    return prop->value;
}

const void *adt_getprop_by_offset(const void *adt, int offset, const char **namep, u32 *lenp)
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

const void *adt_getprop(const void *adt, int nodeoffset, const char *name, u32 *lenp)
{
    return adt_getprop_namelen(adt, nodeoffset, name, strlen(name), lenp);
}

int adt_setprop(void *adt, int nodeoffset, const char *name, void *value, size_t len)
{
    u32 plen;
    void *prop = (void *)adt_getprop(adt, nodeoffset, name, &plen);
    if (!prop)
        return -ADT_ERR_NOTFOUND;

    if (len != plen)
        return -ADT_ERR_BADLENGTH;

    memcpy(prop, value, len);
    return len;
}

int adt_getprop_copy(const void *adt, int nodeoffset, const char *name, void *out, size_t len)
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

int adt_subnode_offset_namelen(const void *adt, int offset, const char *name, size_t namelen)
{
    ADT_CHECK_HEADER(adt);

    ADT_FOREACH_CHILD(adt, offset)
    {
        const char *cname = adt_get_name(adt, offset);

        if (_adt_nodename_eq(cname, name, namelen))
            return offset;
    }

    return -ADT_ERR_NOTFOUND;
}

int adt_subnode_offset(const void *adt, int parentoffset, const char *name)
{
    return adt_subnode_offset_namelen(adt, parentoffset, name, strlen(name));
}

int adt_path_offset(const void *adt, const char *path)
{
    return adt_path_offset_trace(adt, path, NULL);
}

int adt_path_offset_trace(const void *adt, const char *path, int *offsets)
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
            break;
        q = strchr(p, '/');
        if (!q)
            q = end;

        offset = adt_subnode_offset_namelen(adt, offset, p, q - p);
        if (offset < 0)
            break;

        if (offsets)
            *offsets++ = offset;

        p = q;
    }

    if (offsets)
        *offsets++ = 0;

    return offset;
}

const char *adt_get_name(const void *adt, int nodeoffset)
{
    return adt_getprop(adt, nodeoffset, "name", NULL);
}

static void get_cells(u64 *dst, const u32 **src, int cells)
{
    *dst = 0;
    for (int i = 0; i < cells; i++)
        *dst |= ((u64) * ((*src)++)) << (32 * i);
}

int adt_get_reg(const void *adt, int *path, const char *prop, int idx, u64 *paddr, u64 *psize)
{
    int cur = 0;

    if (!*path)
        return -ADT_ERR_BADOFFSET;

    while (path[cur + 1])
        cur++;

    int node = path[cur];
    int parent = cur > 0 ? path[cur - 1] : 0;
    u32 a_cells = 2, s_cells = 1;

    ADT_GETPROP(adt, parent, "#address-cells", &a_cells);
    ADT_GETPROP(adt, parent, "#size-cells", &s_cells);

    dprintf("adt_get_reg: node '%s' @ %d, parent @ %d, address-cells=%d size-cells=%d idx=%d\n",
            adt_get_name(adt, node), node, parent, a_cells, s_cells, idx);

    if (a_cells < 1 || a_cells > 2 || s_cells > 2) {
        dprintf("bad n-cells\n");
        return ADT_ERR_BADNCELLS;
    }

    u32 reg_len = 0;
    const u32 *reg = adt_getprop(adt, node, prop, &reg_len);

    if (!reg || !reg_len) {
        dprintf("reg not found or empty\n");
        return -ADT_ERR_NOTFOUND;
    }

    if (reg_len < (idx + 1) * (a_cells + s_cells) * 4) {
        dprintf("bad reg property length %d\n", reg_len);
        return -ADT_ERR_BADVALUE;
    }

    reg += idx * (a_cells + s_cells);

    u64 addr, size = 0;
    get_cells(&addr, &reg, a_cells);
    get_cells(&size, &reg, s_cells);

    dprintf(" addr=0x%lx size=0x%lx\n", addr, size);

    while (parent) {
        cur--;
        node = parent;
        parent = cur > 0 ? path[cur - 1] : 0;

        dprintf(" walking up to %s\n", adt_get_name(adt, node));

        u32 ranges_len;
        const u32 *ranges = adt_getprop(adt, node, "ranges", &ranges_len);
        if (!ranges)
            break;

        u32 pa_cells = 2, ps_cells = 1;
        ADT_GETPROP(adt, parent, "#address-cells", &pa_cells);
        ADT_GETPROP(adt, parent, "#size-cells", &ps_cells);

        dprintf(" translate range to address-cells=%d size-cells=%d\n", pa_cells, ps_cells);

        if (pa_cells < 1 || pa_cells > 2 || ps_cells > 2)
            return ADT_ERR_BADNCELLS;

        int range_cnt = ranges_len / (4 * (pa_cells + a_cells + s_cells));

        while (range_cnt--) {
            u64 c_addr, p_addr, c_size;
            get_cells(&c_addr, &ranges, a_cells);
            get_cells(&p_addr, &ranges, pa_cells);
            get_cells(&c_size, &ranges, s_cells);

            dprintf(" ranges %lx %lx %lx\n", c_addr, p_addr, c_size);

            if (addr >= c_addr && (addr + size) <= (c_addr + c_size)) {
                dprintf(" translate %lx", addr);
                addr = addr - c_addr + p_addr;
                dprintf(" -> %lx\n", addr);
                break;
            }
        }

        a_cells = pa_cells;
        s_cells = ps_cells;
    }

    if (paddr)
        *paddr = addr;
    if (psize)
        *psize = size;

    return 0;
}

bool adt_is_compatible(const void *adt, int nodeoffset, const char *compat)
{
    u32 len;
    const char *list = adt_getprop(adt, nodeoffset, "compatible", &len);
    if (!list)
        return false;

    const char *end = list + len;

    while (list != end) {
        if (!strcmp(list, compat))
            return true;
        list += strlen(list) + 1;
    }

    return false;
}

/* SPDX-License-Identifier: (GPL-2.0-or-later OR BSD-2-Clause) */

#include "adt.h"
#include "string.h"
#include "xnuboot.h"

/* This API is designed to match libfdt's read-only API */

#define ADT_CHECK_HEADER(adt)                                                                      \
    {                                                                                              \
        int err;                                                                                   \
        if ((err = adt_check_header(adt)) != 0)                                                    \
            return err;                                                                            \
    }

// #define DEBUG

#ifdef DEBUG
#include "utils.h"
#define dprintf printf
#else
#define dprintf(...)                                                                               \
    do {                                                                                           \
    } while (0)
#endif

u32 adt_get_size(void)
{
    return cur_boot_args.devtree_size;
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

        u32 pa_cells = 2;
        ADT_GETPROP(adt, parent, "#address-cells", &pa_cells);

        dprintf(" translate range to address-cells=%d\n", pa_cells);

        if (pa_cells < 1 || pa_cells > 2 || s_cells > 2)
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

        ADT_GETPROP(adt, parent, "#size-cells", &s_cells);

        a_cells = pa_cells;
    }

    if (paddr)
        *paddr = addr;
    if (psize)
        *psize = size;

    return 0;
}

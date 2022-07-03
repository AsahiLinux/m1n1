/* SPDX-License-Identifier: MIT */

#include "dapf.h"
#include "adt.h"
#include "assert.h"
#include "malloc.h"
#include "memory.h"
#include "string.h"
#include "utils.h"

struct dapf_t8020_config {
    u64 start;
    u64 end;
    u8 unk1;
    u8 r0_hi;
    u8 r0_lo;
    u8 unk2;
    u32 r4;
} PACKED;

static int dapf_init_t8020(const char *path, u64 base, int node)
{
    u32 length;
    const char *prop = "filter-data-instance-0";
    const struct dapf_t8020_config *config = adt_getprop(adt, node, prop, &length);

    if (!config || !length || (length % sizeof(*config)) != 0) {
        printf("dapf: Error getting ADT node %s property %s.\n", path, prop);
        return -1;
    }

    int count = length / sizeof(*config);

    for (int i = 0; i < count; i++) {
        write32(base + 0x04, config[i].r4);
        write64(base + 0x08, config[i].start);
        write64(base + 0x10, config[i].end);
        write32(base + 0x00, (config[i].r0_hi << 4) | config[i].r0_lo);
        base += 0x40;
    }
    return 0;
}

struct dapf_t8110_config {
    u64 start;
    u64 end;
    u32 r20;
    u32 unk1;
    u32 r4;
    u32 unk2[5];
    u8 unk3;
    u8 r0_hi;
    u8 r0_lo;
    u8 unk4;
} PACKED;

static int dapf_init_t8110(const char *path, u64 base, int node)
{
    u32 length;
    const char *prop = "dapf-instance-0";
    const struct dapf_t8110_config *config = adt_getprop(adt, node, prop, &length);

    if (!config || !length) {
        printf("dapf: Error getting ADT node %s property %s.\n", path, prop);
        return -1;
    }

    if (length % sizeof(*config) != 0) {
        printf("dapf: Invalid length for %s property %s\n", path, prop);
        return -1;
    }

    int count = length / sizeof(*config);

    for (int i = 0; i < count; i++) {
        write32(base + 0x04, config[i].r4);
        write64(base + 0x08, config[i].start);
        write64(base + 0x10, config[i].end);
        write32(base + 0x00, (config[i].r0_hi << 4) | config[i].r0_lo);
        write32(base + 0x20, config[i].r20);
        base += 0x40;
    }
    return 0;
}

int dapf_init(const char *path)
{
    int ret;
    int dart_path[8];
    int node = adt_path_offset_trace(adt, path, dart_path);
    if (node < 0) {
        printf("dapf: Error getting DAPF %s node.\n", path);
        return -1;
    }

    u64 base;
    if (adt_get_reg(adt, dart_path, "reg", 1, &base, NULL) < 0) {
        printf("dapf: Error getting DAPF %s base address.\n", path);
        return -1;
    }

    if (adt_is_compatible(adt, node, "dart,t8020")) {
        ret = dapf_init_t8020(path, base, node);
    } else if (adt_is_compatible(adt, node, "dart,t6000")) {
        ret = dapf_init_t8020(path, base, node);
    } else if (adt_is_compatible(adt, node, "dart,t8110")) {
        ret = dapf_init_t8110(path, base, node);
    } else {
        printf("dapf: DAPF %s at 0x%lx is of an unknown type\n", path, base);
        return -1;
    }

    if (!ret)
        printf("dapf: Initialized %s\n", path);

    return ret;
}

const char *dapf_paths[] = {"/arm-io/dart-aop", "/arm-io/dart-mtp", "/arm-io/dart-pmp", NULL};

int dapf_init_all(void)
{
    int ret = 0;
    int count = 0;

    for (const char **path = dapf_paths; *path; path++) {
        if (adt_path_offset(adt, *path) < 0)
            continue;

        if (dapf_init(*path) < 0) {
            ret = -1;
        }
        count += 1;
    }

    return ret ? ret : count;
}

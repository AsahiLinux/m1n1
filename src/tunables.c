/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "tunables.h"
#include "types.h"
#include "utils.h"

struct tunable_info {
    int node_offset;
    int node_path[8];
    const u32 *tunable_raw;
    u32 tunable_len;
};

static int tunables_adt_find(const char *path, const char *prop, struct tunable_info *info,
                             u32 item_size)
{
    info->node_offset = adt_path_offset_trace(adt, path, info->node_path);
    if (info->node_offset < 0) {
        printf("tunable: unable to find ADT node %s.\n", path);
        return -1;
    }

    info->tunable_raw = adt_getprop(adt, info->node_offset, prop, &info->tunable_len);
    if (info->tunable_raw == NULL || info->tunable_len == 0) {
        printf("tunable: Error getting ADT node %s property %s .\n", path, prop);
        return -1;
    }

    if (info->tunable_len % item_size) {
        printf("tunable: tunable length needs to be a multiply of %d but is %d\n", item_size,
               info->tunable_len);
        return -1;
    }

    info->tunable_len /= item_size;

    return 0;
}

struct tunable_global {
    u32 reg_idx;
    u32 offset;
    u32 mask;
    u32 value;
} PACKED;

int tunables_apply_global(const char *path, const char *prop)
{
    struct tunable_info info;

    if (tunables_adt_find(path, prop, &info, sizeof(struct tunable_global)) < 0)
        return -1;

    const struct tunable_global *tunables = (const struct tunable_global *)info.tunable_raw;
    for (u32 i = 0; i < info.tunable_len; ++i) {
        const struct tunable_global *tunable = &tunables[i];

        u64 addr;
        if (adt_get_reg(adt, info.node_path, "reg", tunable->reg_idx, &addr, NULL) < 0) {
            printf("tunable: Error getting regs with index %d\n", tunable->reg_idx);
            return -1;
        }

        mask32(addr + tunable->offset, tunable->mask, tunable->value);
    }

    return 0;
}

struct tunable_local {
    u32 offset;
    u32 size;
    u64 mask;
    u64 value;
} PACKED;

int tunables_apply_local_addr(const char *path, const char *prop, uintptr_t base)
{
    struct tunable_info info;

    if (tunables_adt_find(path, prop, &info, sizeof(struct tunable_local)) < 0)
        return -1;

    const struct tunable_local *tunables = (const struct tunable_local *)info.tunable_raw;
    for (u32 i = 0; i < info.tunable_len; ++i) {
        const struct tunable_local *tunable = &tunables[i];

        switch (tunable->size) {
            case 1:
                mask8(base + tunable->offset, tunable->mask, tunable->value);
                break;
            case 2:
                mask16(base + tunable->offset, tunable->mask, tunable->value);
                break;
            case 4:
                mask32(base + tunable->offset, tunable->mask, tunable->value);
                break;
            case 8:
                mask64(base + tunable->offset, tunable->mask, tunable->value);
                break;
            default:
                printf("tunable: unknown tunable size 0x%08x\n", tunable->size);
                return -1;
        }
    }
    return 0;
}

int tunables_apply_local(const char *path, const char *prop, u32 reg_offset)
{
    struct tunable_info info;

    if (tunables_adt_find(path, prop, &info, sizeof(struct tunable_local)) < 0)
        return -1;

    u64 base;
    if (adt_get_reg(adt, info.node_path, "reg", reg_offset, &base, NULL) < 0) {
        printf("tunable: Error getting regs\n");
        return -1;
    }

    return tunables_apply_local_addr(path, prop, base);
}

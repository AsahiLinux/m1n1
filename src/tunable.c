#include "adt.h"
#include "tunable.h"
#include "types.h"
#include "utils.h"

struct tunable_mask32 {
    u32 reg_idx;
    u32 offset;
    u32 mask;
    u32 value;
} PACKED;

struct tunable_maskn {
    u32 offset;
    u32 size;
    u64 mask;
    u64 value;
} PACKED;

static int tunable_apply_mask32(int node_path[8], const u32 *tunable_node, u32 tunable_len)
{
    if (tunable_len % sizeof(struct tunable_mask32)) {
        printf("tunable-mask32: tunable length needs to be a multiply of %d but is %d\n",
               sizeof(struct tunable_mask32), tunable_len);
        return -1;
    }

    tunable_len /= sizeof(struct tunable_mask32);
    const struct tunable_mask32 *tunables = (const struct tunable_mask32 *)tunable_node;
    for (u32 i = 0; i < tunable_len; ++i) {
        const struct tunable_mask32 *tunable = &tunables[i];

        u64 addr;
        if (adt_get_reg(adt, node_path, "reg", tunable->reg_idx, &addr, NULL) < 0) {
            printf("tunable-mask32: Error getting regs with index %d\n", tunable->reg_idx);
            return -1;
        }

        mask32(addr + tunable->offset, tunable->mask, tunable->value);
    }
    return 0;
}

static int tunable_apply_maskn(int node_path[8], const u32 *tunable_node, u32 tunable_len)
{
    if (tunable_len % sizeof(struct tunable_maskn)) {
        printf("tunable-maskn: tunable length needs to be a multiply of %d but is %d\n",
               sizeof(struct tunable_maskn), tunable_len);
        return -1;
    }

    u64 base;
    if (adt_get_reg(adt, node_path, "reg", 0, &base, NULL) < 0) {
        printf("tunable-maskn: Error getting regs\n");
        return -1;
    }

    tunable_len /= sizeof(struct tunable_maskn);
    const struct tunable_maskn *tunables = (const struct tunable_maskn *)tunable_node;
    for (u32 i = 0; i < tunable_len; ++i) {
        const struct tunable_maskn *tunable = &tunables[i];

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
                printf("tunable-maskn: unknown tunable size 0x%08x\n", tunable->size);
                return -1;
        }
    }
    return 0;
}

int tunable_apply(const char *path, const char *prop, enum tunable_type type)
{
    int node_offset;
    int node_path[8];
    const u32 *tunable;
    u32 tunable_len;

    node_offset = adt_path_offset_trace(adt, path, node_path);
    if (node_offset < 0) {
        printf("tunable: unable to find %s node.\n", path);
        return -1;
    }

    tunable = adt_getprop(adt, node_offset, prop, &tunable_len);
    if (tunable == NULL || tunable_len == 0) {
        printf("tunable: Error getting %s %s.", path, prop);
        return -1;
    }

    switch (type) {
        case TUNABLE_TYPE_MASKN:
            return tunable_apply_maskn(node_path, tunable, tunable_len);
        case TUNABLE_TYPE_MASK32:
            return tunable_apply_mask32(node_path, tunable, tunable_len);
        default:
            printf("tunable: unknown type %d.\n", type);
            return -1;
    }
}

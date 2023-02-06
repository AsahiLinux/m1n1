/* SPDX-License-Identifier: MIT */

#include "mcc.h"
#include "adt.h"
#include "hv.h"
#include "memory.h"
#include "string.h"
#include "utils.h"

static bool mcc_initialized = false;

#define MAX_MCC_INSTANCES 16

#define T8103_PLANES       4
#define T8103_PLANE_STRIDE 0x40000
#define T8103_DCS_STRIDE   0x40000

#define T6000_PLANES        4
#define T6000_PLANE_OFFSET  0
#define T6000_PLANE_STRIDE  0x40000
#define T6000_GLOBAL_OFFSET 0x100000
#define T6000_DCS_OFFSET    0x200000
#define T6000_DCS_STRIDE    0x100000
#define T6000_DCS_COUNT     4

#define PLANE_TZ_START(i)  (0x6a0 + i * 0x10)
#define PLANE_TZ_END(i)    (0x6a4 + i * 0x10)
#define PLANE_TZ_ENABLE(i) (0x6a8 + i * 0x10)
#define PLANE_TZ_REGS      4

#define PLANE_CACHE_ENABLE 0x1c00
#define PLANE_CACHE_STATUS 0x1c04

#define T8103_CACHE_STATUS_DATA_COUNT GENMASK(14, 10)
#define T8103_CACHE_STATUS_TAG_COUNT  GENMASK(9, 5)

#define T6000_CACHE_STATUS_DATA_COUNT GENMASK(13, 9)
#define T6000_CACHE_STATUS_TAG_COUNT  GENMASK(8, 4)

#define T6000_CACHE_WAYS        12
#define T6000_CACHE_STATUS_MASK (T6000_CACHE_STATUS_DATA_COUNT | T6000_CACHE_STATUS_TAG_COUNT)
#define T6000_CACHE_STATUS_VAL                                                                     \
    (FIELD_PREP(T6000_CACHE_STATUS_DATA_COUNT, T6000_CACHE_WAYS) |                                 \
     FIELD_PREP(T6000_CACHE_STATUS_TAG_COUNT, T6000_CACHE_WAYS))

#define T8103_CACHE_WAYS        16
#define T8103_CACHE_STATUS_MASK (T8103_CACHE_STATUS_DATA_COUNT | T8103_CACHE_STATUS_TAG_COUNT)
#define T8103_CACHE_STATUS_VAL                                                                     \
    (FIELD_PREP(T8103_CACHE_STATUS_DATA_COUNT, T8103_CACHE_WAYS) |                                 \
     FIELD_PREP(T8103_CACHE_STATUS_TAG_COUNT, T8103_CACHE_WAYS))

#define CACHE_ENABLE_TIMEOUT 10000

#define T8103_DCC_DRAMCFG0         0xdc4
#define T8103_DCC_DRAMCFG1         0xdbc
#define T8103_DCC_DRAMCFG0_DEFAULT 0x813057f
#define T8103_DCC_DRAMCFG1_DEFAULT 0x1800180
#define T8103_DCC_DRAMCFG0_FAST    0x133
#define T8103_DCC_DRAMCFG1_FAST    0x55555340

#define T6000_DCC_DRAMCFG         0x13cc
#define T6000_DCC_DRAMCFG_DEFAULT 0x55551555
#define T6000_DCC_DRAMCFG_FAST    0xffff0000

size_t mcc_carveout_count;
struct mcc_carveout mcc_carveouts[PLANE_TZ_REGS + 1];

struct mcc_regs {
    u64 plane_base;
    u64 plane_stride;
    int plane_count;

    u64 global_base;

    u64 dcs_base;
    u64 dcs_stride;
    int dcs_count;

    int cache_ways;
    u32 cache_status_mask;
    u32 cache_status_val;
};

static int mcc_count;
static struct mcc_regs mcc_regs[MAX_MCC_INSTANCES];

static u32 plane_read32(int mcc, int plane, u64 offset)
{
    return read32(mcc_regs[mcc].plane_base + plane * mcc_regs[mcc].plane_stride + offset);
}

static void plane_write32(int mcc, int plane, u64 offset, u32 value)
{
    write32(mcc_regs[mcc].plane_base + plane * mcc_regs[mcc].plane_stride + offset, value);
}

static int plane_poll32(int mcc, int plane, u64 offset, u32 mask, u32 target, u32 timeout)
{
    return poll32(mcc_regs[mcc].plane_base + plane * mcc_regs[mcc].plane_stride + offset, mask,
                  target, timeout);
}

static void mcc_enable_cache(void)
{
    if (!mcc_initialized)
        return;

    for (int mcc = 0; mcc < mcc_count; mcc++) {
        for (int plane = 0; plane < mcc_regs[mcc].plane_count; plane++) {
            plane_write32(mcc, plane, PLANE_CACHE_ENABLE, mcc_regs[mcc].cache_ways);
            if (plane_poll32(mcc, plane, PLANE_CACHE_STATUS, mcc_regs[mcc].cache_status_mask,
                             mcc_regs[mcc].cache_status_val, CACHE_ENABLE_TIMEOUT))
                printf("MCC: timeout while enabling cache for MCC %d plane %d: 0x%x\n", mcc, plane,
                       plane_read32(mcc, plane, PLANE_CACHE_STATUS));
        }
    }
}

int mcc_unmap_carveouts(void)
{
    if (!mcc_initialized)
        return -1;

    mcc_carveout_count = 0;
    memset(mcc_carveouts, 0, sizeof mcc_carveouts);
    // All MCCs and planes should have identical configs
    for (int i = 0; i < PLANE_TZ_REGS; i++) {
        uint64_t start = plane_read32(0, 0, PLANE_TZ_START(i));
        uint64_t end = plane_read32(0, 0, PLANE_TZ_END(i));
        bool enabled = plane_read32(0, 0, PLANE_TZ_ENABLE(i));

        if (enabled) {
            if (!start || start == end) {
                printf("MMU: TZ%d region has bad bounds 0x%lx..0x%lx (iBoot bug?)\n", i, start,
                       end);
                continue;
            }

            start = start << 12;
            end = (end + 1) << 12;
            start |= ram_base;
            end |= ram_base;
            printf("MMU: Unmapping TZ%d region at 0x%lx..0x%lx\n", i, start, end);
            mmu_rm_mapping(start, end - start);
            mmu_rm_mapping(start | REGION_RWX_EL0, end - start);
            mmu_rm_mapping(start | REGION_RW_EL0, end - start);
            mmu_rm_mapping(start | REGION_RX_EL1, end - start);
            mcc_carveouts[mcc_carveout_count].base = start;
            mcc_carveouts[mcc_carveout_count].size = end - start;
            mcc_carveout_count++;
        }
    }

    return 0;
}

int mcc_init_t8103(int node, int *path)
{
    printf("MCC: Initializing T8103 MCC...\n");

    mcc_count = 1;
    mcc_regs[0].plane_stride = T8103_PLANE_STRIDE;
    mcc_regs[0].plane_count = T8103_PLANES;
    mcc_regs[0].dcs_stride = T8103_DCS_STRIDE;

    if (adt_get_reg(adt, path, "reg", 0, &mcc_regs[0].global_base, NULL)) {
        printf("MCC: Failed to get reg property 0!\n");
        return -1;
    }

    if (adt_get_reg(adt, path, "reg", 1, &mcc_regs[0].plane_base, NULL)) {
        printf("MCC: Failed to get reg property 1!\n");
        return -1;
    }

    if (adt_get_reg(adt, path, "reg", 2, &mcc_regs[0].dcs_base, NULL)) {
        printf("MCC: Failed to get reg property 2!\n");
        return -1;
    }

    u32 val;
    if (ADT_GETPROP(adt, node, "dcs_num_channels", &val) < 0) {
        printf("MCC: Failed to get dcs_num_channels property!\n");
        return -1;
    }

    mcc_regs[0].dcs_count = val;
    mcc_regs[0].cache_ways = T8103_CACHE_WAYS;
    mcc_regs[0].cache_status_mask = T8103_CACHE_STATUS_MASK;
    mcc_regs[0].cache_status_val = T8103_CACHE_STATUS_VAL;

    mcc_enable_cache();

    printf("MCC: Initialized T8103 MCC (%d channels)\n", val);

    mcc_initialized = true;

    return 0;
}

int mcc_init_t6000(int node, int *path)
{
    u32 reg_len;

    if (!adt_getprop(adt, node, "reg", &reg_len)) {
        printf("MCC: Failed to get reg property!\n");
        return -1;
    }

    mcc_count = reg_len / 16;

    printf("MCC: Initializing T6000 MCCs (%d instances)...\n", mcc_count);

    if (mcc_count > MAX_MCC_INSTANCES) {
        printf("MCC: Too many instances, increase MAX_MCC_INSTANCES!\n");
        mcc_count = MAX_MCC_INSTANCES;
    }

    for (int i = 0; i < mcc_count; i++) {
        u64 base;
        if (adt_get_reg(adt, path, "reg", 0, &base, NULL)) {
            printf("MCC: Failed to get reg index %d!\n", i);
            return -1;
        }

        mcc_regs[i].plane_base = base + T6000_PLANE_OFFSET;
        mcc_regs[i].plane_stride = T6000_PLANE_STRIDE;
        mcc_regs[i].plane_count = T6000_PLANES;

        mcc_regs[i].global_base = base + T6000_GLOBAL_OFFSET;

        mcc_regs[i].dcs_base = base + T6000_DCS_OFFSET;
        mcc_regs[i].dcs_stride = T6000_DCS_STRIDE;
        mcc_regs[i].dcs_count = T6000_DCS_COUNT;

        mcc_regs[i].cache_ways = T6000_CACHE_WAYS;
        mcc_regs[i].cache_status_mask = T6000_CACHE_STATUS_MASK;
        mcc_regs[i].cache_status_val = T6000_CACHE_STATUS_VAL;
    }

    mcc_enable_cache();

    printf("MCC: Initialized T6000 MCCs (%d instances, %d planes, %d channels)\n", mcc_count,
           mcc_regs[0].plane_count, mcc_regs[0].dcs_count);

    mcc_initialized = true;

    return 0;
}

int mcc_init(void)
{
    int path[8];
    int node = adt_path_offset_trace(adt, "/arm-io/mcc", path);

    if (node < 0) {
        printf("MCC: MCC node not found!\n");
        return -1;
    }

    if (adt_is_compatible(adt, node, "mcc,t8103")) {
        return mcc_init_t8103(node, path);
    } else if (adt_is_compatible(adt, node, "mcc,t8112")) {
        return mcc_init_t8103(node, path);
    } else if (adt_is_compatible(adt, node, "mcc,t6000")) {
        return mcc_init_t6000(node, path);
    } else if (adt_is_compatible(adt, node, "mcc,t6020")) {
        return mcc_init_t6000(node, path);
    } else {
        printf("MCC: Unsupported version\n");
        return -1;
    }
}

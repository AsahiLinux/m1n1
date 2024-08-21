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

#define T603X_PLANE_OFFSET  0
#define T603X_PLANE_STRIDE  0x40000
#define T603X_GLOBAL_OFFSET 0x100000
#define T603X_DCS_OFFSET    0x400000
#define T603X_DCS_STRIDE    0x200000

#define PLANE_TZ_MAX_REGS 4

struct tz_regs {
    u32 count;
    u32 stride;
    u32 start;
    u32 end;
    u32 enable;
};

struct tz_regs t8103_tz_regs = {
    .count = 4,
    .stride = 0x10,
    .start = 0x6a0,
    .end = 0x6a4,
    .enable = 0x6a8,
};

struct tz_regs t602x_tz_regs = {
    .count = 4,
    .stride = 0x14,
    .start = 0x6bc,
    .end = 0x6c0,
    .enable = 0x6c8,
};

struct tz_regs t6030_tz_regs = {
    .count = 4,
    .stride = 0x14,
    .start = 0x6dc,
    .end = 0x6e0,
    .enable = 0x6e8,
};

struct tz_regs t6031_tz_regs = {
    .count = 4,
    .stride = 0x14,
    .start = 0x6d8,
    .end = 0x6dc,
    .enable = 0x6e4,
};

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

#define T603X_CACHE_WAYS        12
#define T603X_CACHE_STATUS_MASK (T6000_CACHE_STATUS_DATA_COUNT | T6000_CACHE_STATUS_TAG_COUNT)
#define T603X_CACHE_STATUS_VAL                                                                     \
    (FIELD_PREP(T6000_CACHE_STATUS_DATA_COUNT, T603X_CACHE_WAYS) |                                 \
     FIELD_PREP(T6000_CACHE_STATUS_TAG_COUNT, T603X_CACHE_WAYS))

#define T8103_CACHE_WAYS        16
#define T8103_CACHE_STATUS_MASK (T8103_CACHE_STATUS_DATA_COUNT | T8103_CACHE_STATUS_TAG_COUNT)
#define T8103_CACHE_STATUS_VAL                                                                     \
    (FIELD_PREP(T8103_CACHE_STATUS_DATA_COUNT, T8103_CACHE_WAYS) |                                 \
     FIELD_PREP(T8103_CACHE_STATUS_TAG_COUNT, T8103_CACHE_WAYS))

#define T8112_CACHE_DISABLE 0x424

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
struct mcc_carveout mcc_carveouts[PLANE_TZ_MAX_REGS + 1];

struct mcc_regs {
    u64 plane_base;
    u64 plane_stride;
    int plane_count;

    u64 global_base;

    u64 dcs_base;
    u64 dcs_stride;
    int dcs_count;

    u32 cache_enable_val;
    int cache_ways;
    u32 cache_status_mask;
    u32 cache_status_val;
    u32 cache_disable;

    struct tz_regs *tz;
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

int mcc_enable_cache(void)
{
    int ret = 0;

    if (!mcc_initialized)
        return -1;

    /* The 6030 memory controller supports setting a waymask, but the desktop chips do not appear to
       use it */
    for (int mcc = 0; mcc < mcc_count; mcc++) {
        for (int plane = 0; plane < mcc_regs[mcc].plane_count; plane++) {
            plane_write32(mcc, plane, PLANE_CACHE_ENABLE, mcc_regs[mcc].cache_enable_val);
            if (plane_poll32(mcc, plane, PLANE_CACHE_STATUS, mcc_regs[mcc].cache_status_mask,
                             mcc_regs[mcc].cache_status_val, CACHE_ENABLE_TIMEOUT)) {
                printf("MCC: timeout while enabling cache for MCC %d plane %d: 0x%x\n", mcc, plane,
                       plane_read32(mcc, plane, PLANE_CACHE_STATUS));
                ret = -1;
            } else if (mcc_regs[mcc].cache_disable) {
                plane_write32(mcc, plane, mcc_regs[mcc].cache_disable, 0);
            }
        }
    }

    if (!ret)
        printf("MCC: System level cache enabled\n");

    return ret;
}

int mcc_unmap_carveouts(void)
{
    if (!mcc_initialized)
        return -1;

    mcc_carveout_count = 0;
    memset(mcc_carveouts, 0, sizeof mcc_carveouts);

    // All MCCs and planes should have identical configs
    // Note: For unhandled machines, the TZ regions can be found (on m1, m2, m3) by looking at
    // region-id-2 and region-id-4 on a booted macos, in the /chosen/carveout-memory-map DT node.
    // This can be used along with dumping the mcc reg space to find the correct start/end/enable
    // above.
    for (u32 i = 0; i < mcc_regs[0].tz->count; i++) {
        uint64_t off = mcc_regs[0].tz->stride * i;
        uint64_t start = plane_read32(0, 0, mcc_regs[0].tz->start + off);
        uint64_t end = plane_read32(0, 0, mcc_regs[0].tz->end + off);
        bool enabled = plane_read32(0, 0, mcc_regs[0].tz->enable + off);

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

int mcc_init_t8103(int node, int *path, bool t8112)
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
    mcc_regs[0].cache_enable_val = T8103_CACHE_WAYS;
    mcc_regs[0].cache_ways = T8103_CACHE_WAYS;
    mcc_regs[0].cache_status_mask = T8103_CACHE_STATUS_MASK;
    mcc_regs[0].cache_status_val = T8103_CACHE_STATUS_VAL;
    mcc_regs[0].cache_disable = t8112 ? T8112_CACHE_DISABLE : 0;
    mcc_regs[0].tz = &t8103_tz_regs;

    printf("MCC: Initialized T8103 MCC (%d channels)\n", val);

    mcc_initialized = true;

    return 0;
}

int mcc_init_t6000(int node, int *path, bool t602x)
{
    u32 reg_len;
    u32 reg_offset = t602x ? 2 : 0;

    if (!adt_getprop(adt, node, "reg", &reg_len)) {
        printf("MCC: Failed to get reg property!\n");
        return -1;
    }

    mcc_count = reg_len / 16 - reg_offset;

    printf("MCC: Initializing T%x MCCs (%d instances)...\n", t602x ? 0x6020 : 0x6000, mcc_count);

    if (mcc_count > MAX_MCC_INSTANCES) {
        printf("MCC: Too many instances, increase MAX_MCC_INSTANCES!\n");
        mcc_count = MAX_MCC_INSTANCES;
    }

    for (int i = 0; i < mcc_count; i++) {
        u64 base;
        if (adt_get_reg(adt, path, "reg", i + reg_offset, &base, NULL)) {
            printf("MCC: Failed to get reg index %d!\n", i + reg_offset);
            return -1;
        }

        mcc_regs[i].plane_base = base + T6000_PLANE_OFFSET;
        mcc_regs[i].plane_stride = T6000_PLANE_STRIDE;
        mcc_regs[i].plane_count = T6000_PLANES;

        mcc_regs[i].global_base = base + T6000_GLOBAL_OFFSET;

        mcc_regs[i].dcs_base = base + T6000_DCS_OFFSET;
        mcc_regs[i].dcs_stride = T6000_DCS_STRIDE;
        mcc_regs[i].dcs_count = T6000_DCS_COUNT;

        mcc_regs[i].cache_enable_val = t602x ? 1 : T6000_CACHE_WAYS;
        mcc_regs[i].cache_ways = T6000_CACHE_WAYS;
        mcc_regs[i].cache_status_mask = T6000_CACHE_STATUS_MASK;
        mcc_regs[i].cache_status_val = T6000_CACHE_STATUS_VAL;
        mcc_regs[i].cache_disable = 0;

        mcc_regs[i].tz = t602x ? &t602x_tz_regs : &t8103_tz_regs;
    }

    printf("MCC: Initialized T%x MCCs (%d instances, %d planes, %d channels)\n",
           t602x ? 0x6020 : 0x6000, mcc_count, mcc_regs[0].plane_count, mcc_regs[0].dcs_count);

    mcc_initialized = true;

    return 0;
}

int mcc_init_t603x(int node, int *path, int lsn)
{
    u32 reg_len;
    u32 reg_offset = 3;

    if (!adt_getprop(adt, node, "reg", &reg_len)) {
        printf("MCC: Failed to get reg property!\n");
        return -1;
    }

    mcc_count = reg_len / 16 - reg_offset;

    printf("MCC: Initializing T603%x MCCs (%d instances)...\n", lsn, mcc_count);

    if (mcc_count > MAX_MCC_INSTANCES) {
        printf("MCC: Too many instances, increase MAX_MCC_INSTANCES!\n");
        mcc_count = MAX_MCC_INSTANCES;
    }

    u32 plane_count = 0;
    u32 dcs_count = 0;

    if (!ADT_GETPROP(adt, node, "dcs-count-per-amcc", &dcs_count)) {
        printf("MCC: Failed to get dcs count!\n");
        return -1;
    }

    if (!ADT_GETPROP(adt, node, "plane-count-per-amcc", &plane_count)) {
        printf("MCC: Failed to get plane count!\n");
        return -1;
    }

    for (int i = 0; i < mcc_count; i++) {
        u64 base;
        if (adt_get_reg(adt, path, "reg", i + reg_offset, &base, NULL)) {
            printf("MCC: Failed to get reg index %d!\n", i + reg_offset);
            return -1;
        }

        mcc_regs[i].plane_base = base + T603X_PLANE_OFFSET;
        mcc_regs[i].plane_stride = T603X_PLANE_STRIDE;
        mcc_regs[i].plane_count = plane_count;

        mcc_regs[i].global_base = base + T603X_GLOBAL_OFFSET;

        mcc_regs[i].dcs_base = base + T603X_DCS_OFFSET;
        mcc_regs[i].dcs_stride = T603X_DCS_STRIDE;
        mcc_regs[i].dcs_count = dcs_count;

        mcc_regs[i].cache_enable_val = 1;
        mcc_regs[i].cache_ways = T603X_CACHE_WAYS;
        mcc_regs[i].cache_status_mask = T603X_CACHE_STATUS_MASK;
        mcc_regs[i].cache_status_val = T603X_CACHE_STATUS_VAL;
        mcc_regs[i].cache_disable = 0;

        if(lsn == 0){
            mcc_regs[i].tz = &t6030_tz_regs;
        } else if(lsn == 1){
            mcc_regs[i].tz = &t6031_tz_regs;
        } else {
            printf("MCC: Unsupported chip (T603%x)", lsn);
            return -1;
        }
    }

    printf("MCC: Initialized T603%x MCCs (%d instances, %d planes, %d channels)\n", lsn, mcc_count,
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
        return mcc_init_t8103(node, path, false);
    } else if (adt_is_compatible(adt, node, "mcc,t8112")) {
        return mcc_init_t8103(node, path, true);
    } else if (adt_is_compatible(adt, node, "mcc,t6000")) {
        return mcc_init_t6000(node, path, false);
    } else if (adt_is_compatible(adt, node, "mcc,t6020")) {
        return mcc_init_t6000(node, path, true);
    } else if (adt_is_compatible(adt, node, "mcc,t6030")) {
        return mcc_init_t603x(node, path, 0);
    } else if (adt_is_compatible(adt, node, "mcc,t6031")) {
        return mcc_init_t603x(node, path, 1);
    } else {
        printf("MCC: Unsupported version:%s\n", adt_get_property(adt, node, "compatible")->value);
        return -1;
    }
}

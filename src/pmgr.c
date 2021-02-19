/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "pmgr.h"
#include "string.h"
#include "types.h"
#include "utils.h"

#define PMGR_POLL_TIMEOUT 10000

#define PMGR_TARGET_MODE_MASK 0x0f
#define PMGR_TARGET_MODE(m)   (((m)&0xf))
#define PMGR_ACTUAL_MODE_MASK 0xf0
#define PMGR_ACTUAL_MODE(m)   (((m)&0xf) << 4)

#define PMGR_MODE_ENABLE  0xf
#define PMGR_MODE_DISABLE 0

#define PMGR_FLAG_VIRTUAL 0x10

#define PMGR_FIND_DEVICE_EIGNORE -2

struct pmgr_device {
    u32 flags;
    u16 alias;
    u8 unk1[4];
    u8 addr_offset;
    u8 psreg_idx;
    u8 unk2[14];
    u16 id;
    u8 unk3[4];
    const char name[0x10];
} PACKED;

static int pmgr_initialized = 0;

static int pmgr_path[8];
static int pmgr_offset;

static const u32 *pmgr_ps_regs = NULL;
static u32 pmgr_ps_regs_len = 0;

static const struct pmgr_device *pmgr_devices = NULL;
static u32 pmgr_devices_len = 0;

int pmgr_init(void)
{
    pmgr_offset = adt_path_offset_trace(adt, "/arm-io/pmgr", pmgr_path);
    if (pmgr_offset < 0) {
        printf("pmgr: Error getting /arm-io/pmgr node\n");
        return -1;
    }

    pmgr_ps_regs = adt_getprop(adt, pmgr_offset, "ps-regs", &pmgr_ps_regs_len);
    if (pmgr_ps_regs == NULL || pmgr_ps_regs_len == 0) {
        printf("pmgr: Error getting /arm-io/pmgr ps-regs\n.");
        return -1;
    }

    pmgr_devices = adt_getprop(adt, pmgr_offset, "devices", &pmgr_devices_len);
    if (pmgr_devices == NULL || pmgr_devices_len == 0) {
        printf("pmgr: Error getting /arm-io/pmgr devices.\n");
        return -1;
    }

    pmgr_devices_len /= sizeof(*pmgr_devices);
    pmgr_initialized = 1;

    printf("pmgr: initialized, %d devices found.\n", pmgr_devices_len);

    return 0;
}

static uintptr_t pmgr_get_psreg(u8 idx)
{
    if (idx * 12 >= pmgr_ps_regs_len) {
        printf("pmgr: Index %d is out of bounds for ps-regs\n", idx);
        return 0;
    }

    u32 reg_idx = pmgr_ps_regs[3 * idx];
    u32 reg_offset = pmgr_ps_regs[3 * idx + 1];

    u64 pmgr_reg;
    if (adt_get_reg(adt, pmgr_path, "reg", reg_idx, &pmgr_reg, NULL) < 0) {
        printf("pmgr: Error getting /arm-io/pmgr regs\n");
        return 0;
    }

    return pmgr_reg + reg_offset;
}

static int pmgr_find_device(u16 id, uintptr_t *base)
{
    for (u32 i = 0; i < pmgr_devices_len; ++i) {
        const struct pmgr_device *device = &pmgr_devices[i];

        if (device->id != id)
            continue;
        if (device->flags & PMGR_FLAG_VIRTUAL) {
            /*
             * FIXME/TODO:
             * There are some virtual devices (e.g. USB-AUDIO-V) that lead to
             * a non-existing device with index zero. Work around
             * this by returning a specific error code that will let the
             * callers know to just ignore this device for now.
             */
            if (device->alias == 0)
                return PMGR_FIND_DEVICE_EIGNORE;
            return pmgr_find_device(device->alias, base);
        }

        uintptr_t addr = pmgr_get_psreg(device->psreg_idx);
        if (addr == 0)
            return -1;

        *base = addr + (device->addr_offset << 3);
        return 0;
    }

    return -1;
}

static int pmgr_set_mode(u16 id, u8 target_mode)
{
    if (!pmgr_initialized) {
        printf("pmgr: pmgr_set_mode() called before successful pmgr_init()\n");
        return -1;
    }

    uintptr_t addr;
    int res = pmgr_find_device(id, &addr);
    if (res == PMGR_FIND_DEVICE_EIGNORE) {
        return 0;
    } else if (res < 0) {
        printf("pmgr: Unable to find device with id %d\n", id);
        return -1;
    }

    mask32(addr, PMGR_TARGET_MODE_MASK, PMGR_TARGET_MODE(target_mode));
    if (poll32(addr, PMGR_ACTUAL_MODE_MASK, PMGR_ACTUAL_MODE(target_mode), PMGR_POLL_TIMEOUT) < 0) {
        printf("pmgr: timeout while trying to set mode %x for device %d at %p: %x\n", target_mode,
               id, addr, read32(addr));
        return -1;
    }

    return 0;
}

int pmgr_clock_enable(u16 id)
{
    return pmgr_set_mode(id, PMGR_MODE_ENABLE);
}

int pmgr_clock_disable(u16 id)
{
    return pmgr_set_mode(id, PMGR_MODE_DISABLE);
}

static int pmgr_adt_find_clocks(const char *path, const u32 **clocks, u32 *n_clocks)
{
    int node_offset = adt_path_offset(adt, path);
    if (node_offset < 0) {
        printf("pmgr: Error getting node %s\n", path);
        return -1;
    }

    *clocks = adt_getprop(adt, node_offset, "clock-gates", n_clocks);
    if (*clocks == NULL || *n_clocks == 0) {
        printf("pmgr: Error getting %s clock-gates.\n", path);
        return -1;
    }

    *n_clocks /= 4;

    return 0;
}

static int pmgr_adt_clocks_set_mode(const char *path, u8 target_mode)
{
    const u32 *clocks;
    u32 n_clocks;
    int ret = 0;

    if (pmgr_adt_find_clocks(path, &clocks, &n_clocks) < 0)
        return -1;

    for (u32 i = 0; i < n_clocks; ++i) {
        if (pmgr_set_mode(clocks[i], target_mode))
            ret = -1;
    }

    return ret;
}

int pmgr_adt_clocks_enable(const char *path)
{
    return pmgr_adt_clocks_set_mode(path, PMGR_MODE_ENABLE);
}

int pmgr_adt_clocks_disable(const char *path)
{
    return pmgr_adt_clocks_set_mode(path, PMGR_MODE_DISABLE);
}

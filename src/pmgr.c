/* SPDX-License-Identifier: MIT */

#include "pmgr.h"
#include "adt.h"
#include "string.h"
#include "types.h"
#include "utils.h"

#define PMGR_RESET        BIT(31)
#define PMGR_AUTO_ENABLE  BIT(28)
#define PMGR_PS_AUTO      GENMASK(27, 24)
#define PMGR_PARENT_OFF   BIT(11)
#define PMGR_DEV_DISABLE  BIT(10)
#define PMGR_WAS_CLKGATED BIT(9)
#define PMGR_WAS_PWRGATED BIT(8)
#define PMGR_PS_ACTUAL    GENMASK(7, 4)
#define PMGR_PS_TARGET    GENMASK(3, 0)

#define PMGR_PS_ACTIVE  0xf
#define PMGR_PS_CLKGATE 0x4
#define PMGR_PS_PWRGATE 0x0

#define PMGR_POLL_TIMEOUT 10000

#define PMGR_FLAG_VIRTUAL 0x10

struct pmgr_device {
    u32 flags;
    u16 parent[2];
    u8 unk1[2];
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
static int pmgr_dies;

static const u32 *pmgr_ps_regs = NULL;
static u32 pmgr_ps_regs_len = 0;

static const struct pmgr_device *pmgr_devices = NULL;
static u32 pmgr_devices_len = 0;

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

static int pmgr_set_mode(uintptr_t addr, u8 target_mode)
{
    mask32(addr, PMGR_PS_TARGET, FIELD_PREP(PMGR_PS_TARGET, target_mode));
    if (poll32(addr, PMGR_PS_ACTUAL, FIELD_PREP(PMGR_PS_ACTUAL, target_mode), PMGR_POLL_TIMEOUT) <
        0) {
        printf("pmgr: timeout while trying to set mode %x for device at 0x%lx: %x\n", target_mode,
               addr, read32(addr));
        return -1;
    }

    return 0;
}

static int pmgr_find_device(u16 id, const struct pmgr_device **device)
{
    for (size_t i = 0; i < pmgr_devices_len; ++i) {
        const struct pmgr_device *i_device = &pmgr_devices[i];
        if (i_device->id != id)
            continue;

        *device = i_device;
        return 0;
    }

    return -1;
}

static uintptr_t pmgr_device_get_addr(u8 die, const struct pmgr_device *device)
{
    uintptr_t addr = pmgr_get_psreg(device->psreg_idx);
    if (addr == 0)
        return 0;

    addr += PMGR_DIE_OFFSET * die;

    addr += (device->addr_offset << 3);
    return addr;
}

static int pmgr_set_mode_recursive(u8 die, u16 id, u8 target_mode, bool recurse)
{
    if (!pmgr_initialized) {
        printf("pmgr: pmgr_set_mode_recursive() called before successful pmgr_init()\n");
        return -1;
    }

    if (id == 0)
        return -1;

    const struct pmgr_device *device;

    if (pmgr_find_device(id, &device))
        return -1;

    if (!(device->flags & PMGR_FLAG_VIRTUAL)) {
        uintptr_t addr = pmgr_device_get_addr(die, device);
        if (!addr)
            return -1;
        if (pmgr_set_mode(addr, target_mode))
            return -1;
    }
    if (!recurse)
        return 0;

    for (int i = 0; i < 2; i++) {
        if (device->parent[i]) {
            u16 parent = FIELD_GET(PMGR_DEVICE_ID, device->parent[i]);
            int ret = pmgr_set_mode_recursive(die, parent, target_mode, true);
            if (ret < 0)
                return ret;
        }
    }

    return 0;
}

int pmgr_power_enable(u32 id)
{
    u16 device = FIELD_GET(PMGR_DEVICE_ID, id);
    u8 die = FIELD_GET(PMGR_DIE_ID, id);
    return pmgr_set_mode_recursive(die, device, PMGR_PS_ACTIVE, true);
}

int pmgr_power_disable(u32 id)
{
    u16 device = FIELD_GET(PMGR_DEVICE_ID, id);
    u8 die = FIELD_GET(PMGR_DIE_ID, id);
    return pmgr_set_mode_recursive(die, device, PMGR_PS_PWRGATE, false);
}

static int pmgr_adt_find_devices(const char *path, const u32 **devices, u32 *n_devices)
{
    int node_offset = adt_path_offset(adt, path);
    if (node_offset < 0) {
        printf("pmgr: Error getting node %s\n", path);
        return -1;
    }

    *devices = adt_getprop(adt, node_offset, "clock-gates", n_devices);
    if (*devices == NULL || *n_devices == 0) {
        printf("pmgr: Error getting %s clock-gates.\n", path);
        return -1;
    }

    *n_devices /= 4;

    return 0;
}

static int pmgr_adt_devices_set_mode(const char *path, u8 target_mode, int recurse)
{
    const u32 *devices;
    u32 n_devices;
    int ret = 0;

    if (pmgr_adt_find_devices(path, &devices, &n_devices) < 0)
        return -1;

    for (u32 i = 0; i < n_devices; ++i) {
        u16 device = FIELD_GET(PMGR_DEVICE_ID, devices[i]);
        u8 die = FIELD_GET(PMGR_DIE_ID, devices[i]);
        if (pmgr_set_mode_recursive(die, device, target_mode, recurse))
            ret = -1;
    }

    return ret;
}

int pmgr_adt_power_enable(const char *path)
{
    int ret = pmgr_adt_devices_set_mode(path, PMGR_PS_ACTIVE, true);
    return ret;
}

int pmgr_adt_power_disable(const char *path)
{
    return pmgr_adt_devices_set_mode(path, PMGR_PS_PWRGATE, false);
}

static int pmgr_reset_device(int die, const struct pmgr_device *dev)
{
    if (die < 0 || die > 16) {
        printf("pmgr: invalid die id %d for device %s\n", die, dev->name);
        return -1;
    }

    uintptr_t addr = pmgr_device_get_addr(die, dev);

    u32 reg = read32(addr);
    if (FIELD_GET(PMGR_PS_ACTUAL, reg) != PMGR_PS_ACTIVE) {
        printf("pmgr: will not reset disabled device %d.%s\n", die, dev->name);
        return -1;
    }

    printf("pmgr: resetting device %d.%s\n", die, dev->name);

    set32(addr, PMGR_DEV_DISABLE);
    set32(addr, PMGR_RESET);
    udelay(10);
    clear32(addr, PMGR_RESET);
    clear32(addr, PMGR_DEV_DISABLE);

    return 0;
}

int pmgr_adt_reset(const char *path)
{
    const u32 *devices;
    u32 n_devices;
    int ret = 0;

    if (pmgr_adt_find_devices(path, &devices, &n_devices) < 0)
        return -1;

    for (u32 i = 0; i < n_devices; ++i) {
        const struct pmgr_device *device;
        u16 id = FIELD_GET(PMGR_DEVICE_ID, devices[i]);
        u8 die = FIELD_GET(PMGR_DIE_ID, devices[i]);

        if (pmgr_find_device(id, &device)) {
            ret = -1;
            continue;
        }

        if (pmgr_reset_device(die, device))
            ret = -1;
    }

    return ret;
}

int pmgr_reset(int die, const char *name)
{
    const struct pmgr_device *dev = NULL;

    for (unsigned int i = 0; i < pmgr_devices_len; ++i) {
        if (strncmp(pmgr_devices[i].name, name, 0x10) == 0) {
            dev = &pmgr_devices[i];
            break;
        }
    }

    if (!dev)
        return -1;

    return pmgr_reset_device(die, dev);
}

int pmgr_init(void)
{
    int node = adt_path_offset(adt, "/arm-io");
    if (node < 0) {
        printf("pmgr: Error getting /arm-io node\n");
        return -1;
    }
    if (ADT_GETPROP(adt, node, "die-count", &pmgr_dies) < 0)
        pmgr_dies = 1;

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

    printf("pmgr: Cleaning up device states...\n");

    for (u8 die = 0; die < pmgr_dies; ++die) {
        for (size_t i = 0; i < pmgr_devices_len; ++i) {
            const struct pmgr_device *device = &pmgr_devices[i];

            if ((device->flags & PMGR_FLAG_VIRTUAL))
                continue;

            uintptr_t addr = pmgr_device_get_addr(die, device);
            if (!addr)
                continue;

            u32 reg = read32(addr);

            if (reg & PMGR_AUTO_ENABLE || FIELD_GET(PMGR_PS_TARGET, reg) == PMGR_PS_ACTIVE) {
                for (int j = 0; j < 2; j++) {
                    if (device->parent[j]) {
                        const struct pmgr_device *pdevice;
                        if (pmgr_find_device(device->parent[j], &pdevice)) {
                            printf("pmgr: Failed to find parent #%d for %s\n", device->parent[j],
                                   device->name);
                            continue;
                        }

                        if ((pdevice->flags & PMGR_FLAG_VIRTUAL))
                            continue;

                        addr = pmgr_device_get_addr(die, pdevice);
                        if (!addr)
                            continue;

                        reg = read32(addr);

                        if (!(reg & PMGR_AUTO_ENABLE) &&
                            FIELD_GET(PMGR_PS_TARGET, reg) != PMGR_PS_ACTIVE) {
                            printf("pmgr: Enabling %d.%s, parent of active device %s\n", die,
                                   pdevice->name, device->name);
                            pmgr_set_mode(addr, PMGR_PS_ACTIVE);
                        }
                    }
                }
            }
        }
    }

    printf("pmgr: initialized, %d devices on %u dies found.\n", pmgr_devices_len, pmgr_dies);

    return 0;
}

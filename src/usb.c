/* SPDX-License-Identifier: MIT */

#include "usb.h"
#include "adt.h"
#include "dart.h"
#include "i2c.h"
#include "iodev.h"
#include "malloc.h"
#include "pmgr.h"
#include "tps6598x.h"
#include "types.h"
#include "usb_dwc3.h"
#include "usb_dwc3_regs.h"
#include "utils.h"

#define USB_INSTANCES 2

struct usb_drd_regs {
    int initialized;
    uintptr_t drd_regs;
    uintptr_t drd_regs_unk3;
    uintptr_t atc;
};

static const struct {
    const char *dart_path;
    const char *dart_mapper_path;
    const char *atc_path;
    const char *drd_path;
    const char *hpm_path;
} usb_drd_paths[2] = {
    {
        .dart_path = "/arm-io/dart-usb0",
        .dart_mapper_path = "/arm-io/dart-usb0/mapper-usb0",
        .atc_path = "/arm-io/atc-phy0",
        .drd_path = "/arm-io/usb-drd0",
        .hpm_path = "/arm-io/i2c0/hpmBusManager/hpm0",
    },
    {
        .dart_path = "/arm-io/dart-usb1",
        .dart_mapper_path = "/arm-io/dart-usb1/mapper-usb1",
        .atc_path = "/arm-io/atc-phy1",
        .drd_path = "/arm-io/usb-drd1",
        .hpm_path = "/arm-io/i2c0/hpmBusManager/hpm1",
    },
};

static tps6598x_irq_state_t tps6598x_irq_state[USB_INSTANCES];
static bool usb_is_initialized = false;
struct usb_drd_regs usb_regs[USB_INSTANCES];

static dart_dev_t *usb_dart_init(const char *path, const char *mapper_path)
{
    int mapper_offset;

    mapper_offset = adt_path_offset(adt, mapper_path);
    if (mapper_offset < 0) {
        printf("usb: Error getting DART mapper node %s\n", mapper_path);
        return NULL;
    }

    u32 dart_idx;
    if (ADT_GETPROP(adt, mapper_offset, "reg", &dart_idx) < 0) {
        printf("usb: Error getting DART %s device index/\n", mapper_path);
        return NULL;
    }

    return dart_init_adt(path, dart_idx);
}

static int usb_drd_get_regs(const char *phy_path, const char *drd_path, struct usb_drd_regs *regs)
{
    int adt_drd_path[8];
    int adt_drd_offset;
    int adt_phy_path[8];
    int adt_phy_offset;

    adt_drd_offset = adt_path_offset_trace(adt, drd_path, adt_drd_path);
    if (adt_drd_offset < 0) {
        // Nonexistent device
        // printf("usb: Error getting drd node %s\n", drd_path);
        return -1;
    }

    adt_phy_offset = adt_path_offset_trace(adt, phy_path, adt_phy_path);
    if (adt_phy_offset < 0) {
        printf("usb: Error getting phy node %s\n", phy_path);
        return -1;
    }

    if (adt_get_reg(adt, adt_phy_path, "reg", 0, &regs->atc, NULL) < 0) {
        printf("usb: Error getting reg with index 0 for %s.\n", phy_path);
        return -1;
    }
    if (adt_get_reg(adt, adt_drd_path, "reg", 0, &regs->drd_regs, NULL) < 0) {
        printf("usb: Error getting reg with index 0 for %s.\n", drd_path);
        return -1;
    }
    if (adt_get_reg(adt, adt_drd_path, "reg", 3, &regs->drd_regs_unk3, NULL) < 0) {
        printf("usb: Error getting reg with index 3 for %s.\n", drd_path);
        return -1;
    }

    return 0;
}

static int usb_phy_bringup(u32 idx)
{
    if (idx >= USB_INSTANCES)
        return -1;

    if (pmgr_adt_clocks_enable(usb_drd_paths[idx].atc_path) < 0)
        return -1;

    if (pmgr_adt_clocks_enable(usb_drd_paths[idx].dart_path) < 0)
        return -1;

    if (pmgr_adt_clocks_enable(usb_drd_paths[idx].drd_path) < 0)
        return -1;

    write32(usb_regs[idx].atc + 0x08, 0x01c1000f);
    write32(usb_regs[idx].atc + 0x04, 0x00000003);
    write32(usb_regs[idx].atc + 0x04, 0x00000000);
    write32(usb_regs[idx].atc + 0x1c, 0x008c0813);
    write32(usb_regs[idx].atc + 0x00, 0x00000002);

    write32(usb_regs[idx].drd_regs_unk3 + 0x0c, 0x00000002);
    write32(usb_regs[idx].drd_regs_unk3 + 0x0c, 0x00000022);
    write32(usb_regs[idx].drd_regs_unk3 + 0x1c, 0x00000021);
    write32(usb_regs[idx].drd_regs_unk3 + 0x20, 0x00009332);

    return 0;
}

static dwc3_dev_t *usb_iodev_bringup(u32 idx)
{
    dart_dev_t *usb_dart =
        usb_dart_init(usb_drd_paths[idx].dart_path, usb_drd_paths[idx].dart_mapper_path);
    if (!usb_dart)
        return NULL;

    struct usb_drd_regs usb_regs;
    if (usb_drd_get_regs(usb_drd_paths[idx].atc_path, usb_drd_paths[idx].drd_path, &usb_regs) < 0)
        return NULL;

    return usb_dwc3_init(usb_regs.drd_regs, usb_dart);
}

#define USB_IODEV_WRAPPER(name, pipe)                                                              \
    static ssize_t usb_##name##_can_read(void *dev)                                                \
    {                                                                                              \
        return usb_dwc3_can_read(dev, pipe);                                                       \
    }                                                                                              \
                                                                                                   \
    static bool usb_##name##_can_write(void *dev)                                                  \
    {                                                                                              \
        return usb_dwc3_can_write(dev, pipe);                                                      \
    }                                                                                              \
                                                                                                   \
    static ssize_t usb_##name##_read(void *dev, void *buf, size_t count)                           \
    {                                                                                              \
        return usb_dwc3_read(dev, pipe, buf, count);                                               \
    }                                                                                              \
                                                                                                   \
    static ssize_t usb_##name##_write(void *dev, const void *buf, size_t count)                    \
    {                                                                                              \
        return usb_dwc3_write(dev, pipe, buf, count);                                              \
    }                                                                                              \
                                                                                                   \
    static ssize_t usb_##name##_queue(void *dev, const void *buf, size_t count)                    \
    {                                                                                              \
        return usb_dwc3_queue(dev, pipe, buf, count);                                              \
    }                                                                                              \
                                                                                                   \
    static void usb_##name##_handle_events(void *dev)                                              \
    {                                                                                              \
        usb_dwc3_handle_events(dev);                                                               \
    }                                                                                              \
                                                                                                   \
    static void usb_##name##_flush(void *dev)                                                      \
    {                                                                                              \
        usb_dwc3_flush(dev, pipe);                                                                 \
    }

USB_IODEV_WRAPPER(0, CDC_ACM_PIPE_0)
USB_IODEV_WRAPPER(1, CDC_ACM_PIPE_1)

static struct iodev_ops iodev_usb_ops = {
    .can_read = usb_0_can_read,
    .can_write = usb_0_can_write,
    .read = usb_0_read,
    .write = usb_0_write,
    .queue = usb_0_queue,
    .flush = usb_0_flush,
    .handle_events = usb_0_handle_events,
};

static struct iodev_ops iodev_usb_sec_ops = {
    .can_read = usb_1_can_read,
    .can_write = usb_1_can_write,
    .read = usb_1_read,
    .write = usb_1_write,
    .queue = usb_1_queue,
    .flush = usb_1_flush,
    .handle_events = usb_1_handle_events,
};

struct iodev iodev_usb[USB_INSTANCES] = {
    {
        .ops = &iodev_usb_ops,
        .usage = USAGE_CONSOLE | USAGE_UARTPROXY,
        .lock = SPINLOCK_INIT,
    },
    {
        .ops = &iodev_usb_ops,
        .usage = USAGE_CONSOLE | USAGE_UARTPROXY,
        .lock = SPINLOCK_INIT,
    },
};

struct iodev iodev_usb_vuart = {
    .ops = &iodev_usb_sec_ops,
    .usage = 0,
    .lock = SPINLOCK_INIT,
};

static tps6598x_dev_t *hpm_init(i2c_dev_t *i2c, int idx)
{
    const char *hpm_path = usb_drd_paths[idx].hpm_path;
    tps6598x_dev_t *tps = tps6598x_init(hpm_path, i2c);
    if (!tps) {
        printf("usb: tps6598x_init failed for %s.\n", hpm_path);
        return NULL;
    }

    if (tps6598x_powerup(tps) < 0) {
        printf("usb: tps6598x_powerup failed for %s.\n", hpm_path);
        tps6598x_shutdown(tps);
        return NULL;
    }

    return tps;
}

static int usb_init_regs(int idx)
{
    int ret;

    if (!usb_regs[idx].initialized) {
        ret = usb_drd_get_regs(usb_drd_paths[idx].atc_path, usb_drd_paths[idx].drd_path,
                               &usb_regs[idx]);
        if (ret >= 0)
            usb_regs[idx].initialized = 1;
        else
            usb_regs[idx].initialized = ret;
    } else {
        ret = min(usb_regs[idx].initialized, 0);
    }

    return ret;
}

void usb_init(void)
{
    if (usb_is_initialized)
        return;

    i2c_dev_t *i2c = i2c_init("/arm-io/i2c0");
    if (!i2c) {
        printf("usb: i2c init failed.\n");
        return;
    }

    for (int idx = 0; idx < USB_INSTANCES; ++idx) {
        tps6598x_dev_t *tps = hpm_init(i2c, idx);
        if (!tps) {
            printf("usb: failed to init hpm%d\n", idx);
            continue;
        }

        if (tps6598x_disable_irqs(tps, &tps6598x_irq_state[idx]))
            printf("usb: unable to disable IRQ masks for hpm%d\n", idx);

        tps6598x_shutdown(tps);
    }

    i2c_shutdown(i2c);

    for (int idx = 0; idx < 2; ++idx) {
        if (usb_init_regs(idx) < 0)
            continue; // Missing instance

        if (usb_phy_bringup(idx) < 0)
            printf("usb: unable to bringup the phy with index %d\n", idx);
    }

    usb_is_initialized = true;
}

void usb_hpm_restore_irqs(bool force)
{
    i2c_dev_t *i2c = i2c_init("/arm-io/i2c0");
    if (!i2c) {
        printf("usb: i2c init failed.\n");
        return;
    }

    for (int idx = 0; idx < USB_INSTANCES; ++idx) {
        if (iodev_usb[idx].usage && !force)
            continue;

        if (tps6598x_irq_state[idx].valid) {
            tps6598x_dev_t *tps = hpm_init(i2c, idx);
            if (!tps)
                continue;

            if (tps6598x_restore_irqs(tps, &tps6598x_irq_state[idx]))
                printf("usb: unable to restore IRQ masks for hpm%d\n", idx);

            tps6598x_shutdown(tps);
        }
    }

    i2c_shutdown(i2c);
}

void usb_iodev_init(void)
{
    for (int i = 0; i < USB_INSTANCES; i++) {
        iodev_usb[i].opaque = usb_iodev_bringup(i);
        if (!iodev_usb[i].opaque)
            continue;

        printf("USB%d: initialized at %p\n", i, iodev_usb[i].opaque);
    }
}

void usb_iodev_shutdown(void)
{
    for (int i = 0; i < USB_INSTANCES; i++) {
        if (!iodev_usb[i].opaque)
            continue;

        printf("USB%d: shutdown\n", i);
        usb_dwc3_shutdown(iodev_usb[i].opaque);

        iodev_usb[i].opaque = NULL;
    }
}

int usb_idx_from_address(u64 drd_base)
{

    for (int i = 0; i < USB_INSTANCES; i++) {
        if (usb_init_regs(i) < 0)
            continue;
        if (usb_regs[i].drd_regs == drd_base)
            return i;
    }
    return -1;
}

void usb_iodev_vuart_setup(iodev_id_t iodev)
{
    if (iodev < IODEV_USB0 || iodev >= IODEV_USB0 + USB_INSTANCES)
        return;

    iodev_usb_vuart.opaque = iodev_usb[iodev - IODEV_USB0].opaque;
}

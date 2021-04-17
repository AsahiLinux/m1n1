/* SPDX-License-Identifier: MIT */

#include "usb.h"
#include "adt.h"
#include "dart.h"
#include "iodev.h"
#include "malloc.h"
#include "pmgr.h"
#include "types.h"
#include "usb_dwc3.h"
#include "usb_dwc3_regs.h"
#include "utils.h"

#define USB_INSTANCES 2

struct usb_drd_regs {
    uintptr_t drd_regs;
    uintptr_t drd_regs_unk3;
    uintptr_t atc;
};

static const struct {
    const char *dart_path;
    const char *dart_mapper_path;
    const char *atc_path;
    const char *drd_path;
} usb_drd_paths[2] = {
    {
        .dart_path = "/arm-io/dart-usb0",
        .dart_mapper_path = "/arm-io/dart-usb0/mapper-usb0",
        .atc_path = "/arm-io/atc-phy0",
        .drd_path = "/arm-io/usb-drd0",
    },
    {
        .dart_path = "/arm-io/dart-usb1",
        .dart_mapper_path = "/arm-io/dart-usb1/mapper-usb1",
        .atc_path = "/arm-io/atc-phy1",
        .drd_path = "/arm-io/usb-drd1",
    },
};

static dart_dev_t *usb_dart_init(const char *path, const char *mapper_path)
{
    int dart_path[8];
    int dart_offset;
    int mapper_offset;

    dart_offset = adt_path_offset_trace(adt, path, dart_path);
    if (dart_offset < 0) {
        printf("usb: Error getting DART node %s\n", path);
        return NULL;
    }

    mapper_offset = adt_path_offset(adt, mapper_path);
    if (mapper_offset < 0) {
        printf("usb: Error getting DART mapper node %s\n", mapper_path);
        return NULL;
    }

    u64 dart_base;
    if (adt_get_reg(adt, dart_path, "reg", 1, &dart_base, NULL) < 0) {
        printf("usb: Error getting DART %s base address.\n", path);
        return NULL;
    }

    u32 dart_idx;
    if (ADT_GETPROP(adt, mapper_offset, "reg", &dart_idx) < 0) {
        printf("usb: Error getting DART %s device index/\n", mapper_path);
        return NULL;
    }

    return dart_init(dart_base, dart_idx);
}

static int usb_drd_get_regs(const char *phy_path, const char *drd_path, struct usb_drd_regs *regs)
{
    int adt_drd_path[8];
    int adt_drd_offset;
    int adt_phy_path[8];
    int adt_phy_offset;

    adt_drd_offset = adt_path_offset_trace(adt, drd_path, adt_drd_path);
    if (adt_drd_offset < 0) {
        printf("usb: Error getting drd node %s\n", drd_path);
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

static void usb_phy_bringup(struct usb_drd_regs *usb_regs)
{
    write32(usb_regs->atc + 0x08, 0x01c1000f);
    write32(usb_regs->atc + 0x04, 0x00000003);
    write32(usb_regs->atc + 0x04, 0x00000000);
    write32(usb_regs->atc + 0x1c, 0x008c0813);
    write32(usb_regs->atc + 0x00, 0x00000002);

    write32(usb_regs->drd_regs_unk3 + 0x0c, 0x00000002);
    write32(usb_regs->drd_regs_unk3 + 0x0c, 0x00000022);
    write32(usb_regs->drd_regs_unk3 + 0x1c, 0x00000021);
    write32(usb_regs->drd_regs_unk3 + 0x20, 0x00009332);
}

dwc3_dev_t *usb_bringup(u32 idx)
{
    if (idx >= 2)
        return NULL;

    if (pmgr_adt_clocks_enable(usb_drd_paths[idx].atc_path) < 0)
        return NULL;

    if (pmgr_adt_clocks_enable(usb_drd_paths[idx].dart_path) < 0)
        return NULL;

    if (pmgr_adt_clocks_enable(usb_drd_paths[idx].drd_path) < 0)
        return NULL;

    dart_dev_t *usb_dart =
        usb_dart_init(usb_drd_paths[idx].dart_path, usb_drd_paths[idx].dart_mapper_path);
    if (!usb_dart)
        return NULL;

    struct usb_drd_regs usb_regs;
    if (usb_drd_get_regs(usb_drd_paths[idx].atc_path, usb_drd_paths[idx].drd_path, &usb_regs) < 0)
        return NULL;

    usb_phy_bringup(&usb_regs);

    return usb_dwc3_init(usb_regs.drd_regs, usb_dart);
}

static struct iodev_ops iodev_usb_ops = {
    .can_read = (bool (*)(void *))usb_dwc3_can_read,
    .can_write = (bool (*)(void *))usb_dwc3_can_write,
    .read = (ssize_t(*)(void *, void *, size_t))usb_dwc3_read,
    .write = (ssize_t(*)(void *, const void *, size_t))usb_dwc3_write,
    .handle_events = (void (*)(void *))usb_dwc3_handle_events,
};

struct iodev iodev_usb[USB_INSTANCES] = {
    {
        .ops = &iodev_usb_ops,
        .usage = USAGE_CONSOLE | USAGE_UARTPROXY,
    },
    {
        .ops = &iodev_usb_ops,
        .usage = USAGE_CONSOLE | USAGE_UARTPROXY,
    },
};

void usb_init(void)
{
    for (int i = 0; i < USB_INSTANCES; i++) {
        iodev_usb[i].opaque = usb_bringup(i);
        if (!iodev_usb[i].opaque)
            continue;

        printf("USB%d: initialized at %p\n", i, iodev_usb[i].opaque);
    }
}

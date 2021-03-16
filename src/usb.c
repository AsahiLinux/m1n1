/* SPDX-License-Identifier: MIT */

#include "usb.h"
#include "adt.h"
#include "dart.h"
#include "malloc.h"
#include "pmgr.h"
#include "string.h"
#include "types.h"
#include "usb_dwc3.h"
#include "usb_dwc3_regs.h"
#include "utils.h"

#define EARLYCON_BUFFER_SIZE SZ_2K

static dart_dev_t *usb_dart_port0;
dwc3_dev_t *usb_dwc3_port0;

static dart_dev_t *usb_dart_port1;
dwc3_dev_t *usb_dwc3_port1;

struct usb_drd_regs {
    uintptr_t drd_regs;
    uintptr_t atc;
};

static struct {
    char bfr[EARLYCON_BUFFER_SIZE];
    u32 offset;
    u32 overflow;
    u32 flushed;
} earlycon;

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

    return 0;
}

static void usb_phy_bringup(struct usb_drd_regs *usb_regs)
{
    /* TODO */
}

static int usb_bringup(u32 idx, dart_dev_t **dart_dev, dwc3_dev_t **usb_dev)
{
    *dart_dev = NULL;
    *usb_dev = NULL;

    if (idx >= 2)
        goto error;

    if (pmgr_adt_clocks_enable(usb_drd_paths[idx].atc_path) < 0)
        goto error;

    if (pmgr_adt_clocks_enable(usb_drd_paths[idx].dart_path) < 0)
        goto error;

    if (pmgr_adt_clocks_enable(usb_drd_paths[idx].drd_path) < 0)
        goto error;

    *dart_dev = usb_dart_init(usb_drd_paths[idx].dart_path, usb_drd_paths[idx].dart_mapper_path);
    if (!*dart_dev)
        goto error;

    struct usb_drd_regs usb_regs;
    if (usb_drd_get_regs(usb_drd_paths[idx].atc_path, usb_drd_paths[idx].drd_path, &usb_regs) < 0)
        goto error;

    usb_phy_bringup(&usb_regs);

    *usb_dev = usb_dwc3_init(usb_regs.drd_regs, *dart_dev);

    if (!*usb_dev)
        goto error;

    return 0;

error:
    if (*dart_dev)
        dart_shutdown(*dart_dev);
    return -1;
}

static void usb_dev_shutdown(dart_dev_t *dart_dev, dwc3_dev_t *usb_dev)
{
    usb_dwc3_shutdown(usb_dev);
    dart_shutdown(dart_dev);
}

int usb_init(void)
{
    if (usb_bringup(0, &usb_dart_port0, &usb_dwc3_port0) < 0)
        return -1;
    if (usb_bringup(1, &usb_dart_port1, &usb_dwc3_port1) < 0) {
        usb_dev_shutdown(usb_dart_port0, usb_dwc3_port0);
        return -1;
    }

    return 0;
}

void usb_shutdown(void)
{
    usb_dev_shutdown(usb_dart_port0, usb_dwc3_port0);
    usb_dev_shutdown(usb_dart_port1, usb_dwc3_port1);
}

void usb_console_write(const char *bfr, size_t len)
{
    if (!is_primary_core())
        return;

    /*
     * we only need to check for port0 since usb_init guarantees
     * that either both ports or no port is up and running
     */
    if (!usb_dwc3_port0) {
        u32 copy = min(EARLYCON_BUFFER_SIZE - earlycon.offset, len);

        memcpy(earlycon.bfr + earlycon.offset, bfr, copy);
        earlycon.offset += copy;

        if (copy != len)
            earlycon.overflow = 1;
        return;
    }

    if (!earlycon.flushed) {
        if (earlycon.overflow) {
            static const char overflow_msg[] =
                "earlycon: buffer has overflown; some messages above are missing.\n";
            usb_dwc3_write_unsafe(usb_dwc3_port0, overflow_msg, sizeof(overflow_msg));
            usb_dwc3_write_unsafe(usb_dwc3_port1, overflow_msg, sizeof(overflow_msg));
        }
        usb_dwc3_write_unsafe(usb_dwc3_port0, earlycon.bfr, earlycon.offset);
        usb_dwc3_write_unsafe(usb_dwc3_port1, earlycon.bfr, earlycon.offset);
        earlycon.flushed = 1;
    }

    usb_dwc3_write_unsafe(usb_dwc3_port0, bfr, len);
    usb_dwc3_write_unsafe(usb_dwc3_port1, bfr, len);
}

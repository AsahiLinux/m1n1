/* SPDX-License-Identifier: GPL-2.0-or-later */

#include "adt.h"
#include "hv.h"
#include "hv_sprr.h"
#include "utils.h"

#define AMCC_MAX_PLANES       64
#define AMCC_UNEXP_RT_HIT_DIR BIT(8)

static struct {
    u64 base;
    u64 controller_base;
    u32 irq;
} amcc_planes[AMCC_MAX_PLANES];
static u32 amcc_plane_count;
static u32 amcc_intsts;
static u32 amcc_status_count;
static bool amcc_shared_irqs;

bool hv_amcc_handle_irq(u32 irq)
{
    if (hv_sptm_mode != SPTM_EMULATION)
        return false;

    bool consumed = false;
    u32 pending = 0;
    for (u32 i = 0; i < amcc_plane_count; i++) {
        if (amcc_planes[i].irq != irq)
            continue;

        u64 base = amcc_planes[i].base;
        u32 status = read32(base + amcc_intsts + 8);
        if (status & AMCC_UNEXP_RT_HIT_DIR) {
            printf("hv_amcc: Got UNEXP_RT_HIT_DIR interrupt for plane %d\n", i);
            /* ACK only the emulation-related error, leaving other bits intact. */
            write32(base + amcc_intsts + 8, AMCC_UNEXP_RT_HIT_DIR);
            sysop("dsb sy");
            consumed = true;
        }

        /*
         * Only forward the interrupt to the guest if there are any other pending AMCC
         * interrupts because XNU will also panic if it gets an interrupt but then
         * finds nothing in the AMCC registers.
         */
        for (u32 j = 0; j < amcc_status_count; j++) {
            u32 value = read32(base + amcc_intsts + 8 * j);
            if (j == 1)
                value &= ~AMCC_UNEXP_RT_HIT_DIR;
            pending |= value;
        }

        /* T8132's IRQ also covers the other plane and controller-wide errors. */
        if (amcc_shared_irqs) {
            for (u32 j = 0; j < 3; j++)
                pending |= read32(amcc_planes[i].controller_base + 0x155004 + 8 * j);
        }
    }

    return consumed && !pending;
}

bool hv_amcc_init(void)
{
    amcc_plane_count = 0;

    if (hv_sptm_mode != SPTM_EMULATION)
        return true;

    amcc_shared_irqs = chip_id == T8132;
    amcc_intsts = amcc_shared_irqs ? 0x21004 : 0x25004;
    amcc_status_count = amcc_shared_irqs ? 3 : 7;

    int path[8];
    int error_handler_node = adt_path_offset_trace(adt, "/arm-io/error-handler", path);
    if (error_handler_node < 0)
        return false;

    int amcc_node = adt_path_offset(adt, "/chosen/lock-regs/amcc");
    if (amcc_node < 0)
        return false;

    struct {
        u32 tag, reg_start, count, irq_start, irq_count, unk;
    } metadata;
    u32 enabled, planes, stride;

    if (ADT_GETPROP(adt, error_handler_node, "amcc-metadata", &metadata) != sizeof(metadata) ||
        ADT_GETPROP(adt, amcc_node, "plane-count", &planes) != sizeof(planes) ||
        ADT_GETPROP(adt, amcc_node, "plane-stride", &stride) != sizeof(stride))
        return false;

    /* T8132 lists all controllers and has no enable-mask property. */
    enabled = ~0U;
    if (!amcc_shared_irqs &&
        ADT_GETPROP(adt, error_handler_node, "amcc-enable-mask", &enabled) != sizeof(enabled))
        return false;

    u32 irq_len;
    const u32 *irqs = adt_getprop(adt, error_handler_node, "interrupts", &irq_len);
    u64 required_irqs = (u64)metadata.count * (amcc_shared_irqs ? 1 : planes);
    if (!irqs || metadata.count > 32 || !planes || required_irqs > metadata.irq_count ||
        (u64)metadata.irq_start + required_irqs > irq_len / sizeof(*irqs))
        return false;

    for (u32 instance = 0; instance < metadata.count; instance++) {
        if (!(enabled & BIT(instance)))
            continue;

        u64 base;
        if (adt_get_reg(adt, path, "reg", metadata.reg_start + instance, &base, NULL) < 0)
            return false;

        for (u32 plane = 0; plane < planes; plane++) {
            if (amcc_plane_count == ARRAY_SIZE(amcc_planes))
                return false;
            u32 irq_index = amcc_shared_irqs ? instance : instance * planes + plane;
            u32 irq = irqs[metadata.irq_start + irq_index];
            amcc_planes[amcc_plane_count].irq = irq;
            amcc_planes[amcc_plane_count].controller_base = base;
            amcc_planes[amcc_plane_count++].base = base + (u64)plane * stride;
        }
    }

    if (!amcc_plane_count)
        return true;

    if (!hv_aic_hook())
        return false;
    return true;
}

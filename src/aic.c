/* SPDX-License-Identifier: MIT */

#include "aic.h"
#include "adt.h"
#include "aic_regs.h"
#include "assert.h"
#include "utils.h"

u64 aic_base;

#define MASK_REG(x) (4 * ((x) >> 5))
#define MASK_BIT(x) BIT((x)&GENMASK(4, 0))

static const struct aic_regs aic1_regs = {
    .reg_size = AIC_REG_SIZE,
    .event = AIC_EVENT,
    .tgt_cpu = AIC_TARGET_CPU,
    .sw_set = AIC_SW_SET,
    .sw_clr = AIC_SW_CLR,
    .mask_set = AIC_MASK_SET,
    .mask_clr = AIC_MASK_CLR,
};

static const struct aic_regs aic2_regs = {
    .reg_size = AIC2_REG_SIZE,
    .event = AIC2_EVENT,
    .config = AIC2_IRQ_CFG,
    .sw_set = AIC2_SW_SET,
    .sw_clr = AIC2_SW_CLR,
    .mask_set = AIC2_MASK_SET,
    .mask_clr = AIC2_MASK_CLR,
};

const struct aic_regs *aic_regs;

static void aic2_init(int node)
{
    u32 ext_intr_config_len;
    const u8 *ext_intr_config = adt_getprop(adt, node, "aic-ext-intr-cfg", &ext_intr_config_len);

    if (ext_intr_config) {
        printf("AIC: Configuring %d external interrupts\n", ext_intr_config_len / 3);
        for (u32 i = 0; i < ext_intr_config_len; i += 3) {
            u16 irq = ext_intr_config[i] | (ext_intr_config[i + 1] << 8);
            u8 target = ext_intr_config[i + 2];
            assert(irq < 0x1000); // Will probably need updating for multi-die
            mask32(aic_base + aic_regs->config + 4 * irq, AIC2_IRQ_CFG_TARGET,
                   FIELD_PREP(AIC2_IRQ_CFG_TARGET, target));
        }
    }
    return;
}

void aic_init(void)
{
    int path[8];
    int node = adt_path_offset_trace(adt, "/arm-io/aic", path);

    if (node < 0) {
        printf("AIC node not found!\n");
        return;
    }

    if (adt_get_reg(adt, path, "reg", 0, &aic_base, NULL)) {
        printf("Failed to get AIC reg property!\n");
        return;
    }

    if (adt_is_compatible(adt, node, "aic,1")) {
        printf("AIC: Version 1 @ 0x%lx\n", aic_base);
        aic_regs = &aic1_regs;
    } else if (adt_is_compatible(adt, node, "aic,2")) {
        printf("AIC: Version 2 @ 0x%lx\n", aic_base);
        aic_regs = &aic2_regs;
        aic2_init(node);
    } else {
        printf("AIC: Error: Unsupported version @ 0x%lx\n", aic_base);
    }
}

void aic_set_sw(int irq, bool active)
{
    if (active)
        write32(aic_base + aic_regs->sw_set + MASK_REG(irq), MASK_BIT(irq));
    else
        write32(aic_base + aic_regs->sw_clr + MASK_REG(irq), MASK_BIT(irq));
}

uint32_t aic_ack(void)
{
    return read32(aic_base + aic_regs->event);
}

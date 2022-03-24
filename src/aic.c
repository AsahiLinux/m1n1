/* SPDX-License-Identifier: MIT */

#include "aic.h"
#include "adt.h"
#include "aic_regs.h"
#include "assert.h"
#include "utils.h"

#define MASK_REG(x) (4 * ((x) >> 5))
#define MASK_BIT(x) BIT((x)&GENMASK(4, 0))

static struct aic aic1 = {
    .version = 1,
    .nr_die = 1,
    .max_die = 1,
    .regs =
        {
            .reg_size = AIC_REG_SIZE,
            .event = AIC_EVENT,
            .tgt_cpu = AIC_TARGET_CPU,
            .sw_set = AIC_SW_SET,
            .sw_clr = AIC_SW_CLR,
            .mask_set = AIC_MASK_SET,
            .mask_clr = AIC_MASK_CLR,
        },
};

static struct aic aic2 = {
    .version = 2,
    .regs =
        {
            .config = AIC2_IRQ_CFG,
        },
};

struct aic *aic;

static int aic2_init(int node)
{
    int ret = ADT_GETPROP(adt, node, "aic-iack-offset", &aic->regs.event);
    if (ret < 0) {
        printf("AIC: failed to get property aic-iack-offset\n");
        return ret;
    }

    u32 info1 = read32(aic->base + AIC2_INFO1);
    aic->nr_die = FIELD_GET(AIC2_INFO1_LAST_DIE, info1) + 1;
    aic->nr_irq = FIELD_GET(AIC2_INFO1_NR_IRQ, info1);

    u32 info3 = read32(aic->base + AIC2_INFO3);
    aic->max_die = FIELD_GET(AIC2_INFO3_MAX_DIE, info3);
    aic->max_irq = FIELD_GET(AIC2_INFO3_MAX_IRQ, info3);

    if (aic->nr_die > AIC_MAX_DIES) {
        printf("AIC: more dies than supported: %u\n", aic->max_die);
        return -1;
    }

    if (aic->max_irq > AIC_MAX_HW_NUM) {
        printf("AIC: more IRQs than supported: %u\n", aic->max_irq);
        return -1;
    }

    const u64 start_off = aic->regs.config;
    u64 off = start_off + sizeof(u32) * aic->max_irq; /* IRQ_CFG */

    aic->regs.sw_set = off;
    off += sizeof(u32) * (aic->max_irq >> 5); /* SW_SET */
    aic->regs.sw_clr = off;
    off += sizeof(u32) * (aic->max_irq >> 5); /* SW_CLR */
    aic->regs.mask_set = off;
    off += sizeof(u32) * (aic->max_irq >> 5); /* MASK_SET */
    aic->regs.mask_clr = off;
    off += sizeof(u32) * (aic->max_irq >> 5); /* MASK_CLR */
    off += sizeof(u32) * (aic->max_irq >> 5); /* HW_STATE */

    aic->die_stride = off - start_off;
    aic->regs.reg_size = aic->regs.event + 4;

    printf("AIC: AIC2 with %u/%u dies, %u/%u IRQs, reg_size:%05lx die_stride:%05x\n", aic->nr_die,
           aic->max_die, aic->nr_irq, aic->max_irq, aic->regs.reg_size, aic->die_stride);

    u32 ext_intr_config_len;
    const u8 *ext_intr_config = adt_getprop(adt, node, "aic-ext-intr-cfg", &ext_intr_config_len);

    if (ext_intr_config) {
        printf("AIC: Configuring %d external interrupts\n", ext_intr_config_len / 3);
        for (u32 i = 0; i < ext_intr_config_len; i += 3) {
            u8 die = ext_intr_config[i + 1] >> 4;
            u16 irq = ext_intr_config[i] | ((ext_intr_config[i + 1] & 0xf) << 8);
            u8 target = ext_intr_config[i + 2];
            assert(die < aic->nr_die);
            assert(irq < aic->nr_irq);
            mask32(aic->base + aic->regs.config + die * aic->die_stride + 4 * irq,
                   AIC2_IRQ_CFG_TARGET, FIELD_PREP(AIC2_IRQ_CFG_TARGET, target));
        }
    }

    return 0;
}

void aic_init(void)
{
    int path[8];
    int node = adt_path_offset_trace(adt, "/arm-io/aic", path);

    if (node < 0) {
        printf("AIC node not found!\n");
        return;
    }

    if (adt_is_compatible(adt, node, "aic,1")) {
        aic = &aic1;
    } else if (adt_is_compatible(adt, node, "aic,2")) {
        aic = &aic2;
    } else {
        printf("AIC: Error: Unsupported version\n");
        return;
    }

    if (adt_get_reg(adt, path, "reg", 0, &aic->base, NULL)) {
        printf("Failed to get AIC reg property!\n");
        return;
    }

    if (aic->version == 1) {
        printf("AIC: Version 1 @ 0x%lx\n", aic->base);
        aic->nr_irq = FIELD_GET(AIC_INFO_NR_HW, read32(aic->base + AIC_INFO));
        aic->max_irq = AIC1_MAX_IRQ;
    } else if (aic->version == 2) {
        printf("AIC: Version 2 @ 0x%lx\n", aic->base);
        int ret = aic2_init(node);
        if (ret < 0)
            aic = NULL;
    }
}

void aic_set_sw(int irq, bool active)
{
    u32 die = irq / aic->max_irq;
    irq = irq % aic->max_irq;
    if (active)
        write32(aic->base + aic->regs.sw_set + die * aic->die_stride + MASK_REG(irq),
                MASK_BIT(irq));
    else
        write32(aic->base + aic->regs.sw_clr + die * aic->die_stride + MASK_REG(irq),
                MASK_BIT(irq));
}

uint32_t aic_ack(void)
{
    return read32(aic->base + aic->regs.event);
}

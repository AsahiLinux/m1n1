/* SPDX-License-Identifier: MIT */

#include "aic.h"
#include "adt.h"
#include "aic_regs.h"
#include "utils.h"

u64 aic_base;

#define MASK_REG(x) (4 * ((x) >> 5))
#define MASK_BIT(x) BIT((x)&GENMASK(4, 0))

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

    printf("AIC registers @ 0x%lx\n", aic_base);
}

void aic_set_sw(int irq, bool active)
{
    if (active)
        write32(aic_base + AIC_SW_SET + MASK_REG(irq), MASK_BIT(irq));
    else
        write32(aic_base + AIC_SW_CLR + MASK_REG(irq), MASK_BIT(irq));
}

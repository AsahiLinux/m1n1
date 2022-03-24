/* SPDX-License-Identifier: MIT */

#ifndef AIC_H
#define AIC_H

#include "types.h"

#define AIC_MAX_DIES 4

struct aic_regs {
    uint64_t reg_size;
    uint64_t event;
    uint64_t tgt_cpu;
    uint64_t config;
    uint64_t sw_set;
    uint64_t sw_clr;
    uint64_t mask_set;
    uint64_t mask_clr;
};

struct aic {
    uint64_t base;
    uint32_t version;

    uint32_t nr_irq;
    uint32_t nr_die;
    uint32_t max_irq;
    uint32_t max_die;
    uint32_t die_stride;

    struct aic_regs regs;
};

extern struct aic *aic;

void aic_init(void);
void aic_set_sw(int irq, bool active);
uint32_t aic_ack(void);

#endif

/* SPDX-License-Identifier: MIT */

#ifndef AIC_H
#define AIC_H

#include "types.h"

extern u64 aic_base;

struct aic_regs {
    uint64_t reg_size;
    uint64_t event;
    uint64_t tgt_cpu;
    uint64_t sw_set;
    uint64_t sw_clr;
    uint64_t mask_set;
    uint64_t mask_clr;
};

extern const struct aic_regs *aic_regs;

void aic_init(void);
void aic_set_sw(int irq, bool active);
uint32_t aic_ack(void);

#endif

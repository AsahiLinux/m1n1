/* SPDX-License-Identifier: MIT */

#ifndef AIC_H
#define AIC_H

#include "types.h"

extern u64 aic_base;

void aic_init(void);
void aic_set_sw(int irq, bool active);
uint32_t aic_ack(void);

#endif

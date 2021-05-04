/* SPDX-License-Identifier: MIT */

#ifndef HV_H
#define HV_H

#include "types.h"

/* VM */
void hv_pt_init(void);
int hv_map(u64 from, u64 to, u64 size, u64 incr);
int hv_unmap(u64 from, u64 size);
int hv_map_hw(u64 from, u64 to, u64 size);
int hv_map_sw(u64 from, u64 to, u64 size);
int hv_map_hook(u64 from, void *hook, u64 size);
u64 hv_translate(u64 addr);

/* HV main */
void hv_init(void);
void hv_start(void *entry, u64 regs[4]);

#endif

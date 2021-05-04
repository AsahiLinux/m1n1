/* SPDX-License-Identifier: MIT */

#ifndef HV_H
#define HV_H

#include "types.h"

typedef bool(hv_hook_t)(u64 addr, u64 *val, bool write, int width);

/* VM */
void hv_pt_init(void);
int hv_map(u64 from, u64 to, u64 size, u64 incr);
int hv_unmap(u64 from, u64 size);
int hv_map_hw(u64 from, u64 to, u64 size);
int hv_map_sw(u64 from, u64 to, u64 size);
int hv_map_hook(u64 from, hv_hook_t *hook, u64 size);
u64 hv_translate(u64 addr, bool s1only, bool w);
u64 hv_pt_walk(u64 addr);
bool hv_handle_dabort(u64 *regs);

/* Virtual peripherals */
void hv_map_vuart(u64 base);

/* HV main */
void hv_init(void);
void hv_start(void *entry, u64 regs[4]);

#endif

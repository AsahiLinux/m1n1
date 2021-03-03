/* SPDX-License-Identifier: MIT */

#ifndef MEMORY_H
#define MEMORY_H

#include "types.h"

#define SZ_16K 0x4000

void ic_ivau_range(void *addr, size_t length);
void dc_ivac_range(void *addr, size_t length);
void dc_zva_range(void *addr, size_t length);
void dc_cvac_range(void *addr, size_t length);
void dc_cvau_range(void *addr, size_t length);
void dc_civac_range(void *addr, size_t length);

#define DCSW_OP_DCISW  0x0
#define DCSW_OP_DCCISW 0x1
#define DCSW_OP_DCCSW  0x2
void dcsw_op_all(u64 op_type);

void mmu_init(void);
void mmu_shutdown(void);
#endif

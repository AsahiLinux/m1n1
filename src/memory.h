/* SPDX-License-Identifier: MIT */

#ifndef MEMORY_H
#define MEMORY_H

#include "types.h"

#define REGION_RWX_EL0 0x8000000000
#define REGION_RW_EL0  0x9000000000
#define REGION_RX_EL1  0xa000000000

#ifndef __ASSEMBLER__

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
void mmu_init_secondary(int cpu);
void mmu_shutdown(void);

u64 mmu_disable(void);
void mmu_restore(u64 state);

#endif

#endif

/* SPDX-License-Identifier: MIT */

#ifndef MEMORY_H
#define MEMORY_H

#include "types.h"

void ic_ivau_range(void *addr, size_t length);
void dc_ivac_range(void *addr, size_t length);
void dc_zva_range(void *addr, size_t length);
void dc_cvac_range(void *addr, size_t length);
void dc_cvau_range(void *addr, size_t length);
void dc_civac_range(void *addr, size_t length);

void mmu_init(void);
void mmu_shutdown(void);
#endif

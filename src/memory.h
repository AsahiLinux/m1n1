/* SPDX-License-Identifier: MIT */

#ifndef MEMORY_H
#define MEMORY_H

#include "cpu_regs.h"
#include "types.h"

#define REGION_RWX_EL0 0x80000000000
#define REGION_RW_EL0  0xa0000000000
#define REGION_RX_EL1  0xc0000000000

/*
 * https://armv8-ref.codingbelief.com/en/chapter_d4/d43_2_armv8_translation_table_level_3_descriptor_formats.html
 * PTE_TYPE:PTE_BLOCK indicates that the page table entry (PTE) points to a physical memory block
 * PTE_TYPE:PTE_TABLE indicates that the PTE points to another PTE
 * PTE_TYPE:PTE_PAGE indicates that the PTE points to a single page
 * PTE_FLAG_ACCESS is required to allow access to the memory region
 * PTE_MAIR_IDX sets the MAIR index to be used for this PTE
 */
#define PTE_VALID       BIT(0)
#define PTE_TYPE        BIT(1)
#define PTE_BLOCK       0
#define PTE_TABLE       1
#define PTE_PAGE        1
#define PTE_ACCESS      BIT(10)
#define PTE_MAIR_IDX(i) ((i & 7) << 2)
#define PTE_PXN         BIT(53)
#define PTE_UXN         BIT(54)
#define PTE_AP_RO       BIT(7)
#define PTE_AP_EL0      BIT(6)
#define PTE_SH_NS       (0b00 << 8)
#define PTE_SH_OS       (0b10 << 8)
#define PTE_SH_IS       (0b11 << 8)

#define PERM_RO_EL0  PTE_AP_EL0 | PTE_AP_RO | PTE_PXN | PTE_UXN
#define PERM_RW_EL0  PTE_AP_EL0 | PTE_PXN | PTE_UXN
#define PERM_RX_EL0  PTE_AP_EL0 | PTE_AP_RO
#define PERM_RWX_EL0 PTE_AP_EL0

#define PERM_RO  PTE_AP_RO | PTE_PXN | PTE_UXN
#define PERM_RW  PTE_PXN | PTE_UXN
#define PERM_RX  PTE_AP_RO | PTE_UXN
#define PERM_RWX 0

#define MAIR_IDX_NORMAL        0
#define MAIR_IDX_NORMAL_NC     1
#define MAIR_IDX_DEVICE_nGnRnE 2
#define MAIR_IDX_DEVICE_nGnRE  3
#define MAIR_IDX_DEVICE_nGRE   4
#define MAIR_IDX_DEVICE_GRE    5

#ifndef __ASSEMBLER__

#include "utils.h"

extern uint64_t ram_base;

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
void mmu_add_mapping(u64 from, u64 to, size_t size, u8 attribute_index, u64 perms);
void mmu_rm_mapping(u64 from, size_t size);
void mmu_map_framebuffer(u64 addr, size_t size);

u64 mmu_disable(void);
void mmu_restore(u64 state);

static inline bool mmu_active(void)
{
    return mrs(SCTLR_EL1) & SCTLR_M;
}

#endif

#endif

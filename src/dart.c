/* SPDX-License-Identifier: MIT */

#include "dart.h"
#include "assert.h"
#include "malloc.h"
#include "memory.h"
#include "string.h"
#include "types.h"
#include "utils.h"

#define DART_MAX_DEVICES 16
#define DART_PAGE_SIZE   0x4000

#define DART_TCR(device)      (0x100 + 4 * (device))
#define DART_TCR_TRANSLATE_EN 0x80

#define DART_TTBR(device, idx) (0x200 + 16 * (device) + 4 * (idx))

#define DART_TTBR_VALID (1 << 31)
#define DART_TTBR_SHIFT 12

#define DART_DEVICE_INDEX_MAP0 0x80
#define DART_DEVICE_INDEX_MAP1 0x84
#define DART_DEVICE_INDEX_MAP2 0x88
#define DART_DEVICE_INDEX_MAP3 0x8c

#define DART_DEVICE_ENABLE     0xfc
#define DART_DEVICE_EN(device) (1 << device)
#define DART_DEVICE_EN_ALL     0xffff

#define DART_ERROR_STATUS 0x00000040
#define DART_ERROR_FLAG   0x80000000

#define DART_PTE_VALID 0b11
#define DART_PTE_MASK  ~((1 << 14) - 1)

static void dart_invalidate(uintptr_t base)
{
    // TODO :-)
    UNUSED(base);
}

void dart_init(uintptr_t base)
{
    // clear TCR and TTBR
    for (u32 device = 0; device < DART_MAX_DEVICES; ++device) {
        write32(base + DART_TCR(device), 0);
        for (u32 ttbr = 0; ttbr < 4; ++ttbr)
            write32(base + DART_TTBR(device, ttbr), 0);
    }

    // reset device index mapping to linear
    write32(base + DART_DEVICE_INDEX_MAP0, 0x3020100);
    write32(base + DART_DEVICE_INDEX_MAP1, 0x7060504);
    write32(base + DART_DEVICE_INDEX_MAP2, 0xb0a0908);
    write32(base + DART_DEVICE_INDEX_MAP3, 0xf0e0d0c);

    // clear all errors and enable all devices
    set32(base + DART_ERROR_STATUS, DART_ERROR_FLAG);
    write32(base + DART_DEVICE_ENABLE, DART_DEVICE_EN_ALL);
    dart_invalidate(base);
}

static void dart_deallocate_ttbr(u64 *l0)
{
    for (u32 idx = 0; idx < 2048; ++idx) {
        if (!(l0[idx] & DART_PTE_VALID))
            continue;

        void *l1_ptr = (void *)(l0[idx] & ~DART_PTE_VALID);
        memset(l1_ptr, 0, DART_PAGE_SIZE);
        free(l1_ptr);
    }
}

void dart_shutdown_device(uintptr_t base, u8 device)
{
    clear32(base + DART_TCR(device), DART_TCR_TRANSLATE_EN);
    dart_invalidate(base);

    for (u32 ttbr_idx = 0; ttbr_idx < 4; ++ttbr_idx) {
        u32 ttbr = read32(base + DART_TTBR(device, ttbr_idx));
        if (ttbr & DART_TTBR_VALID)
            dart_deallocate_ttbr((u64 *)(((u64)ttbr & ~DART_TTBR_VALID) << DART_TTBR_SHIFT));

        write32(base + DART_TTBR(device, ttbr_idx), 0);
    }

    // clear all errors
    set32(base + DART_ERROR_STATUS, DART_ERROR_FLAG);
}

void dart_shutdown(uintptr_t base)
{
    for (u32 device = 0; device < DART_MAX_DEVICES; ++device)
        dart_shutdown_device(base, device);
}

typedef struct {
    u8 ttbr;
    u32 l0_idx;
    u32 l1_idx;
} dart_vaddr_idx_t;

static void dart_get_idx(u64 vaddr, dart_vaddr_idx_t *idx)
{
    assert(vaddr >> 38 == 0);

    idx->ttbr = (vaddr >> 36) & 3;
    idx->l0_idx = (vaddr >> 25) & 0x7ff;
    idx->l1_idx = (vaddr >> 14) & 0x7ff;
}

static u64 *dart_get_pte(uintptr_t base, u8 device, u64 vaddr)
{
    dart_vaddr_idx_t idx;
    dart_get_idx(vaddr, &idx);

    u64 *l0_table = NULL;
    if (!(read32(base + DART_TTBR(device, idx.ttbr)) & DART_TTBR_VALID)) {
        l0_table = memalign(DART_PAGE_SIZE, DART_PAGE_SIZE);
        memset(l0_table, 0, DART_PAGE_SIZE);
        write32(base + DART_TTBR(device, idx.ttbr),
                ((u64)l0_table >> DART_TTBR_SHIFT) | DART_TTBR_VALID);
    } else {
        u32 l0_table_shifted = (read32(base + DART_TTBR(device, idx.ttbr)) & ~DART_TTBR_VALID);
        l0_table = (u64 *)((u64)l0_table_shifted << DART_TTBR_SHIFT);
    }

    u64 *l1_table = NULL;
    if (!(l0_table[idx.l0_idx] & DART_PTE_VALID)) {
        l1_table = memalign(DART_PAGE_SIZE, DART_PAGE_SIZE);
        memset(l1_table, 0, DART_PAGE_SIZE);
        l0_table[idx.l0_idx] = ((u64)l1_table) | DART_PTE_VALID;
    } else {
        l1_table = (u64 *)(l0_table[idx.l0_idx] & ~DART_PTE_VALID);
    }

    return &l1_table[idx.l1_idx];
}

void dart_map_page(uintptr_t base, u8 device, u64 vaddr, u64 paddr)
{
    u64 *pte_addr = dart_get_pte(base, device, vaddr);
    assert(*pte_addr & DART_PTE_VALID == 0);
    *pte_addr = (paddr & DART_PTE_MASK) | DART_PTE_VALID;
}

void dart_unmap_page(uintptr_t base, u8 device, u64 vaddr)
{
    u64 *pte_addr = dart_get_pte(base, device, vaddr);
    assert(*pte_addr & DART_PTE_VALID == DART_PTE_VALID);
    *pte_addr = 0;
}

void dart_map(uintptr_t base, u8 device, u64 vaddr, u64 paddr, u64 size)
{
    assert(size % DART_PAGE_SIZE == 0);

    for (u64 offset = 0; offset < size; offset += DART_PAGE_SIZE)
        dart_map_page(base, device, vaddr + offset, paddr + offset);
}

void dart_unmap(uintptr_t base, u8 device, u64 vaddr, u64 size)
{
    assert(size % DART_PAGE_SIZE == 0);

    for (u64 offset = 0; offset < size; offset += DART_PAGE_SIZE)
        dart_unmap_page(base, device, vaddr + offset);
}

void dart_enable_device(uintptr_t base, u8 device)
{
    set32(base + DART_TCR(device), DART_TCR_TRANSLATE_EN);
}

void dart_disable_device(uintptr_t base, u8 device)
{
    clear32(base + DART_TCR(device), DART_TCR_TRANSLATE_EN);
}
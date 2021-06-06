/* SPDX-License-Identifier: MIT */

#include "dart.h"
#include "assert.h"
#include "malloc.h"
#include "memory.h"
#include "string.h"
#include "utils.h"

#define DART_CONFIG      0x60
#define DART_CONFIG_LOCK BIT(15)

#define DART_ERROR              0x40
#define DART_ERROR_STREAM_SHIFT 24
#define DART_ERROR_STREAM_MASK  0xf
#define DART_ERROR_CODE_MASK    0xffffff
#define DART_ERROR_FLAG         BIT(31)
#define DART_ERROR_READ_FAULT   BIT(4)
#define DART_ERROR_WRITE_FAULT  BIT(3)
#define DART_ERROR_NO_PTE       BIT(2)
#define DART_ERROR_NO_PMD       BIT(1)
#define DART_ERROR_NO_TTBR      BIT(0)

#define DART_STREAM_SELECT 0x34

#define DART_STREAM_COMMAND            0x20
#define DART_STREAM_COMMAND_BUSY       BIT(2)
#define DART_STREAM_COMMAND_INVALIDATE BIT(20)

#define DART_STREAM_COMMAND_BUSY_TIMEOUT 100

#define DART_STREAM_REMAP 0x80

#define DART_ERROR_ADDR_HI 0x54
#define DART_ERROR_ADDR_LO 0x50

#define DART_TCR(sid)             (0x100 + 4 * (sid))
#define DART_TCR_TRANSLATE_ENABLE BIT(7)
#define DART_TCR_BYPASS_DART      BIT(8)
#define DART_TCR_BYPASS_DAPF      BIT(12)

#define DART_TTBR(sid, idx) (0x200 + 16 * (sid) + 4 * (idx))
#define DART_TTBR_VALID     BIT(31)
#define DART_TTBR_SHIFT     12

#define DART_PTE_VALID 0b11

struct dart_dev {
    uintptr_t regs;
    u8 device;

    u64 *l1;
};

static void dart_tlb_invalidate(dart_dev_t *dart)
{
    write32(dart->regs + DART_STREAM_SELECT, BIT(dart->device));

    /* ensure that the DART can see the updated pagetables before invalidating */
    dma_wmb();
    write32(dart->regs + DART_STREAM_COMMAND, DART_STREAM_COMMAND_INVALIDATE);

    if (poll32(dart->regs + DART_STREAM_COMMAND, DART_STREAM_COMMAND_BUSY, 0, 100))
        printf("dart: DART_STREAM_COMMAND_BUSY did not clear.\n");
}

dart_dev_t *dart_init(uintptr_t base, u8 device)
{
    dart_dev_t *dart = malloc(sizeof(*dart));
    if (!dart)
        return NULL;

    dart->regs = base;
    dart->device = device;
    dart->l1 = NULL;

    if (read32(dart->regs + DART_CONFIG) & DART_CONFIG_LOCK) {
        printf("dart: dart at 0x%lx is locked\n", dart->regs);
        goto error;
    }

    dart->l1 = memalign(SZ_16K, 4 * SZ_16K);
    if (!dart->l1)
        goto error;
    memset(dart->l1, 0, 4 * SZ_16K);

    write32(dart->regs + DART_TTBR(device, 0),
            DART_TTBR_VALID | (((uintptr_t)dart->l1) >> DART_TTBR_SHIFT));
    write32(dart->regs + DART_TTBR(device, 1),
            DART_TTBR_VALID | (((uintptr_t)dart->l1 + SZ_16K) >> DART_TTBR_SHIFT));
    write32(dart->regs + DART_TTBR(device, 2),
            DART_TTBR_VALID | (((uintptr_t)dart->l1 + 2 * SZ_16K) >> DART_TTBR_SHIFT));
    write32(dart->regs + DART_TTBR(device, 3),
            DART_TTBR_VALID | (((uintptr_t)dart->l1 + 3 * SZ_16K) >> DART_TTBR_SHIFT));

    write32(dart->regs + DART_TCR(device), DART_TCR_TRANSLATE_ENABLE);
    dart_tlb_invalidate(dart);

    return dart;

error:
    free(dart->l1);
    free(dart);
    return NULL;
}

static u64 *dart_get_l2(dart_dev_t *dart, u32 idx)
{
    if (dart->l1[idx] & DART_PTE_VALID)
        return (u64 *)(dart->l1[idx] & ~DART_PTE_VALID);

    u64 *tbl = memalign(SZ_16K, SZ_16K);
    if (!tbl)
        return NULL;

    memset(tbl, 0, SZ_16K);
    dart->l1[idx] = (uintptr_t)tbl | DART_PTE_VALID;
    return tbl;
}

static int dart_map_page(dart_dev_t *dart, uintptr_t iova, uintptr_t paddr)
{
    u32 l1_index = (iova >> 25) & 0x1fff;
    u32 l2_index = (iova >> 14) & 0x7ff;

    u64 *l2 = dart_get_l2(dart, l1_index);
    if (!l2) {
        printf("dart: couldn't create l2 for iova %lx\n", iova);
        return -1;
    }

    if (l2[l2_index] & DART_PTE_VALID) {
        printf("dart: iova %lx already has a valid PTE: %lx\n", iova, l2[l2_index]);
        return -1;
    }

    l2[l2_index] = (uintptr_t)paddr | DART_PTE_VALID;

    return 0;
}

int dart_map(dart_dev_t *dart, uintptr_t iova, void *bfr, size_t len)
{
    uintptr_t paddr = (uintptr_t)bfr;
    u64 offset = 0;

    if (len % SZ_16K)
        return -1;
    if (paddr % SZ_16K)
        return -1;
    if (iova % SZ_16K)
        return -1;

    while (offset < len) {
        int ret = dart_map_page(dart, iova + offset, paddr + offset);

        if (ret) {
            dart_unmap(dart, iova, offset);
            return ret;
        }

        offset += SZ_16K;
    }

    dart_tlb_invalidate(dart);
    return 0;
}

static void dart_unmap_page(dart_dev_t *dart, uintptr_t iova)
{
    u32 l1_index = (iova >> 25) & 0x1fff;
    u32 l2_index = (iova >> 14) & 0x7ff;

    if (!(dart->l1[l1_index] & DART_PTE_VALID))
        return;

    u64 *l2 = (u64 *)(dart->l1[l1_index] & ~DART_PTE_VALID);
    l2[l2_index] = 0;
}

void dart_unmap(dart_dev_t *dart, uintptr_t iova, size_t len)
{
    if (len % SZ_16K)
        return;
    if (iova % SZ_16K)
        return;

    while (len) {
        dart_unmap_page(dart, iova);

        len -= SZ_16K;
        iova += SZ_16K;
    }

    dart_tlb_invalidate(dart);
}

void dart_shutdown(dart_dev_t *dart)
{
    write32(dart->regs + DART_TCR(dart->device), DART_TCR_BYPASS_DART | DART_TCR_BYPASS_DAPF);
    for (int i = 0; i < 4; ++i)
        write32(dart->regs + DART_TTBR(dart->device, i), 0);
    dart_tlb_invalidate(dart);

    for (int i = 0; i < SZ_16K / 8; ++i) {
        if (dart->l1[i] & DART_PTE_VALID)
            free((void *)(dart->l1[i] & ~DART_PTE_VALID));
    }

    free(dart->l1);
    free(dart);
}

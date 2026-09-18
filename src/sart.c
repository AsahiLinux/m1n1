/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "malloc.h"
#include "sart.h"
#include "string.h"
#include "utils.h"

struct sart_dev {
    uintptr_t base;
    u32 protected_entries;
    /* This is probably a bitfield but the exact meaning of each bit is unknown. */
    u32 flags_allow;

    u64 config_offset;
    u64 config_stride;
    u64 config_size_max;
    u64 paddr_offset;
    u64 paddr_stride;
    u64 paddr_shift;
    u64 size_shift;

    /* unused for v3/v4 */
    u64 config_flags_mask;
    u64 config_size_mask;

    /* unused for v0/v2 */
    u64 size_offset;
    u64 size_stride;

    void (*get_entry)(sart_dev_t *sart, int index, u8 *flags, void **paddr, size_t *size);
    bool (*set_entry)(sart_dev_t *sart, int index, u8 flags, void *paddr, size_t size);
};

#define APPLE_SART_MAX_ENTRIES 16

static void sart0_get_entry(sart_dev_t *sart, int index, u8 *flags, void **paddr, size_t *size)
{
    u32 cfg = read32(sart->base + sart->config_offset + index * sart->config_stride);
    *flags = FIELD_GET(sart->config_flags_mask, cfg);
    *size = (size_t)FIELD_GET(sart->config_size_mask, cfg) << sart->size_shift;
    *paddr = (void *)((u64)read32(sart->base + sart->paddr_offset + index * sart->paddr_stride)
                      << sart->paddr_shift);
}

static bool sart0_set_entry(sart_dev_t *sart, int index, u8 flags, void *paddr_, size_t size)
{
    u32 cfg;
    u64 paddr = (u64)paddr_;

    if (size & ((1 << sart->size_shift) - 1))
        return false;
    if (paddr & ((1 << sart->paddr_shift) - 1))
        return false;

    size >>= sart->size_shift;
    paddr >>= sart->paddr_shift;

    if (size > sart->config_size_max)
        return false;

    cfg = FIELD_PREP(sart->config_flags_mask, flags);
    cfg |= FIELD_PREP(sart->config_size_mask, size);

    write32(sart->base + sart->paddr_offset + index * sart->paddr_stride, paddr);
    write32(sart->base + sart->config_offset + index * sart->config_stride, cfg);

    return true;
}

static void sart3_get_entry(sart_dev_t *sart, int index, u8 *flags, void **paddr, size_t *size)
{
    *flags = read32(sart->base + sart->config_offset + index * sart->config_stride);
    *size = (size_t)read32(sart->base + sart->size_offset + index * sart->size_stride)
            << sart->size_shift;
    *paddr = (void *)((u64)read32(sart->base + sart->paddr_offset + index * sart->paddr_stride)
                      << sart->paddr_shift);
}

static bool sart3_set_entry(sart_dev_t *sart, int index, u8 flags, void *paddr_, size_t size)
{
    u64 paddr = (u64)paddr_;

    if (size & ((1 << sart->size_shift) - 1))
        return false;
    if (paddr & ((1 << sart->paddr_shift) - 1))
        return false;

    size >>= sart->size_shift;
    paddr >>= sart->paddr_shift;

    if (size > sart->config_size_max)
        return false;

    write32(sart->base + sart->paddr_offset + index * sart->paddr_stride, paddr);
    write32(sart->base + sart->size_offset + index * sart->size_stride, size);
    write32(sart->base + sart->config_offset + index * sart->config_stride, flags);

    return true;
}

sart_dev_t *sart_init(const char *adt_path)
{
    int sart_path[8];
    int node = adt_path_offset_trace(adt, adt_path, sart_path);
    if (node < 0) {
        printf("sart: Error getting SART node %s\n", adt_path);
        return NULL;
    }

    u64 base;
    if (adt_get_reg(adt, sart_path, "reg", 0, &base, NULL) < 0) {
        printf("sart: Error getting SART %s base address.\n", adt_path);
        return NULL;
    }

    const u32 *sart_version = adt_getprop(adt, node, "sart-version", NULL);
    const u32 sart_version_zero = 0;
    if (!sart_version) {
        if (adt_is_compatible(adt, node, "sart,t8015")) {
            sart_version = &sart_version_zero;
        } else {
            printf("sart: SART %s has no sart-version property\n", adt_path);
            return NULL;
        }
    }

    sart_dev_t *sart = calloc(1, sizeof(*sart));
    if (!sart)
        return NULL;

    sart->base = base;

    switch (*sart_version) {
        case 0:
            sart->get_entry = sart0_get_entry;
            sart->set_entry = sart0_set_entry;
            sart->flags_allow = 0xf;
            sart->config_offset = 0;
            sart->config_stride = 4;
            sart->config_flags_mask = GENMASK(28, 24);
            sart->config_size_mask = GENMASK(18, 0);
            sart->config_size_max = GENMASK(18, 0);
            sart->paddr_offset = 0x40;
            sart->paddr_stride = 4;
            sart->paddr_shift = 12;
            sart->size_shift = 12;
            break;
        case 2:
            sart->get_entry = sart0_get_entry;
            sart->set_entry = sart0_set_entry;
            sart->flags_allow = 0xff;
            sart->config_offset = 0;
            sart->config_stride = 4;
            sart->config_flags_mask = GENMASK(31, 24);
            sart->config_size_mask = GENMASK(23, 0);
            sart->config_size_max = GENMASK(23, 0);
            sart->paddr_offset = 0x40;
            sart->paddr_stride = 4;
            sart->paddr_shift = 12;
            sart->size_shift = 12;
            break;
        case 3:
            sart->get_entry = sart3_get_entry;
            sart->set_entry = sart3_set_entry;
            sart->flags_allow = 0xff;
            sart->config_offset = 0;
            sart->config_stride = 4;
            sart->config_size_max = GENMASK(29, 0);
            sart->paddr_offset = 0x40;
            sart->paddr_stride = 4;
            sart->paddr_shift = 12;
            sart->size_offset = 0x80;
            sart->size_stride = 4;
            sart->size_shift = 12;
            break;
        case 4:
            sart->get_entry = sart3_get_entry;
            sart->set_entry = sart3_set_entry;
            sart->flags_allow = 0xff;
            sart->config_offset = 0;
            sart->config_stride = 4;
            sart->config_size_max = GENMASK(29, 0);
            sart->paddr_offset = 0x60;
            sart->paddr_stride = 4;
            sart->paddr_shift = 12;
            sart->size_offset = 0xc0;
            sart->size_stride = 4;
            sart->size_shift = 12;
            break;
        default:
            printf("sart: SART %s has unknown version %d\n", adt_path, *sart_version);
            free(sart);
            return NULL;
    }

    printf("sart: SARTv%d %s at 0x%lx\n", *sart_version, adt_path, base);

    sart->protected_entries = 0;
    for (unsigned int i = 0; i < APPLE_SART_MAX_ENTRIES; ++i) {
        void *paddr;
        u8 flags;
        size_t sz;

        sart->get_entry(sart, i, &flags, &paddr, &sz);
        if (flags)
            sart->protected_entries |= 1 << i;
    }

    return sart;
}

void sart_free(sart_dev_t *sart)
{
    for (unsigned int i = 0; i < APPLE_SART_MAX_ENTRIES; ++i) {
        if (sart->protected_entries & (1 << i))
            continue;
        sart->set_entry(sart, i, 0, NULL, 0);
    }

    free(sart);
}

bool sart_add_allowed_region(sart_dev_t *sart, void *paddr, size_t sz)
{
    for (unsigned int i = 0; i < APPLE_SART_MAX_ENTRIES; ++i) {
        void *e_paddr;
        u8 e_flags;
        size_t e_sz;

        if (sart->protected_entries & (1 << i))
            continue;

        sart->get_entry(sart, i, &e_flags, &e_paddr, &e_sz);
        if (e_flags)
            continue;

        return sart->set_entry(sart, i, sart->flags_allow, paddr, sz);
    }

    printf("sart: no more free entries\n");
    return false;
}

bool sart_remove_allowed_region(sart_dev_t *sart, void *paddr, size_t sz)
{
    for (unsigned int i = 0; i < APPLE_SART_MAX_ENTRIES; ++i) {
        void *e_paddr;
        u8 e_flags;
        size_t e_sz;

        if (sart->protected_entries & (1 << i))
            continue;

        sart->get_entry(sart, i, &e_flags, &e_paddr, &e_sz);
        if (!e_flags)
            continue;
        if (e_paddr != paddr)
            continue;
        if (e_sz != sz)
            continue;

        return sart->set_entry(sart, i, 0, NULL, 0);
    }

    printf("sart: could not find entry to be removed\n");
    return false;
}

/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "malloc.h"
#include "sart.h"
#include "string.h"
#include "utils.h"

struct sart_dev {
    uintptr_t base;
    u32 protected_entries;

    void (*get_entry)(sart_dev_t *sart, int index, u8 *flags, void **paddr, size_t *size);
    bool (*set_entry)(sart_dev_t *sart, int index, u8 flags, void *paddr, size_t size);
};

#define APPLE_SART_MAX_ENTRIES 16

/* This is probably a bitfield but the exact meaning of each bit is unknown. */
#define APPLE_SART_FLAGS_ALLOW 0xff

/* SARTv2 registers */
#define APPLE_SART2_CONFIG(idx)       (0x00 + 4 * (idx))
#define APPLE_SART2_CONFIG_FLAGS      GENMASK(31, 24)
#define APPLE_SART2_CONFIG_SIZE       GENMASK(23, 0)
#define APPLE_SART2_CONFIG_SIZE_SHIFT 12
#define APPLE_SART2_CONFIG_SIZE_MAX   GENMASK(23, 0)

#define APPLE_SART2_PADDR(idx)  (0x40 + 4 * (idx))
#define APPLE_SART2_PADDR_SHIFT 12

/* SARTv3 registers */
#define APPLE_SART3_CONFIG(idx) (0x00 + 4 * (idx))

#define APPLE_SART3_PADDR(idx)  (0x40 + 4 * (idx))
#define APPLE_SART3_PADDR_SHIFT 12

#define APPLE_SART3_SIZE(idx)  (0x80 + 4 * (idx))
#define APPLE_SART3_SIZE_SHIFT 12
#define APPLE_SART3_SIZE_MAX   GENMASK(29, 0)

static void sart2_get_entry(sart_dev_t *sart, int index, u8 *flags, void **paddr, size_t *size)
{
    u32 cfg = read32(sart->base + APPLE_SART2_CONFIG(index));
    *flags = FIELD_GET(APPLE_SART2_CONFIG_FLAGS, cfg);
    *size = (size_t)FIELD_GET(APPLE_SART2_CONFIG_SIZE, cfg) << APPLE_SART2_CONFIG_SIZE_SHIFT;
    *paddr =
        (void *)((u64)read32(sart->base + APPLE_SART2_PADDR(index)) << APPLE_SART2_PADDR_SHIFT);
}

static bool sart2_set_entry(sart_dev_t *sart, int index, u8 flags, void *paddr_, size_t size)
{
    u32 cfg;
    u64 paddr = (u64)paddr_;

    if (size & ((1 << APPLE_SART2_CONFIG_SIZE_SHIFT) - 1))
        return false;
    if (paddr & ((1 << APPLE_SART2_PADDR_SHIFT) - 1))
        return false;

    size >>= APPLE_SART2_CONFIG_SIZE_SHIFT;
    paddr >>= APPLE_SART2_PADDR_SHIFT;

    if (size > APPLE_SART2_CONFIG_SIZE_MAX)
        return false;

    cfg = FIELD_PREP(APPLE_SART2_CONFIG_FLAGS, flags);
    cfg |= FIELD_PREP(APPLE_SART2_CONFIG_SIZE, size);

    write32(sart->base + APPLE_SART2_PADDR(index), paddr);
    write32(sart->base + APPLE_SART2_CONFIG(index), cfg);

    return true;
}

static void sart3_get_entry(sart_dev_t *sart, int index, u8 *flags, void **paddr, size_t *size)
{
    *flags = read32(sart->base + APPLE_SART3_CONFIG(index));
    *size = (size_t)read32(sart->base + APPLE_SART3_SIZE(index)) << APPLE_SART3_SIZE_SHIFT;
    *paddr =
        (void *)((u64)read32(sart->base + APPLE_SART3_PADDR(index)) << APPLE_SART3_PADDR_SHIFT);
}

static bool sart3_set_entry(sart_dev_t *sart, int index, u8 flags, void *paddr_, size_t size)
{
    u64 paddr = (u64)paddr_;
    if (size & ((1 << APPLE_SART3_SIZE_SHIFT) - 1))
        return false;
    if (paddr & ((1 << APPLE_SART3_PADDR_SHIFT) - 1))
        return false;

    paddr >>= APPLE_SART3_PADDR_SHIFT;
    size >>= APPLE_SART3_SIZE_SHIFT;

    if (size > APPLE_SART3_SIZE_MAX)
        return false;

    write32(sart->base + APPLE_SART3_PADDR(index), paddr);
    write32(sart->base + APPLE_SART3_SIZE(index), size);
    write32(sart->base + APPLE_SART3_CONFIG(index), flags);

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
    if (!sart_version) {
        printf("sart: SART %s has no sart-version property\n", adt_path);
        return NULL;
    }

    sart_dev_t *sart = malloc(sizeof(*sart));
    if (!sart)
        return NULL;

    memset(sart, 0, sizeof(*sart));
    sart->base = base;

    switch (*sart_version) {
        case 2:
            sart->get_entry = sart2_get_entry;
            sart->set_entry = sart2_set_entry;
            break;
        case 3:
            sart->get_entry = sart3_get_entry;
            sart->set_entry = sart3_set_entry;
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

        return sart->set_entry(sart, i, APPLE_SART_FLAGS_ALLOW, paddr, sz);
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

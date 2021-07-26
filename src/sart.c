/* SPDX-License-Identifier: MIT */

#include "sart.h"
#include "utils.h"

#define SART_CONFIG(id) (0x0000 + 4 * (id))
#define SART_PADDR(id)  (0x0040 + 4 * (id))

#define SART_CONFIG_FLAGS GENMASK(31, 24)
#define SART_CONFIG_SIZE  GENMASK(23, 0)

#define SART_PADDR_SHIFT 12
#define SART_SIZE_SHIFT  12
#define SART_MAX_ENTRIES 16

bool sart_allow_dma(uintptr_t sart_base, void *paddr, size_t sz)
{
    u32 config;

    for (int i = 0; i < SART_MAX_ENTRIES; ++i) {
        config = read32(sart_base + SART_CONFIG(i));
        if (FIELD_GET(SART_CONFIG_FLAGS, config) != 0)
            continue;

        config = FIELD_PREP(SART_CONFIG_FLAGS, 0xff);
        config |= FIELD_PREP(SART_CONFIG_SIZE, sz >> SART_SIZE_SHIFT);

        write32(sart_base + SART_PADDR(i), ((uintptr_t)paddr) >> SART_PADDR_SHIFT);
        write32(sart_base + SART_CONFIG(i), config);
        return true;
    }

    printf("sart: no more free fields to allow 0x%lx bytes at %p\n", sz, paddr);
    return false;
}

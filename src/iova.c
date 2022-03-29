/* SPDX-License-Identifier: MIT */

#include "iova.h"
#include "malloc.h"
#include "string.h"
#include "utils.h"

struct iova_block {
    u64 iova;
    size_t sz;
    struct iova_block *next;
};

struct iova_domain {
    u64 base;
    u64 limit;
    struct iova_block *free_list;
};

iova_domain_t *iovad_init(u64 base, u64 limit)
{
    if (base != ALIGN_UP(base, SZ_32M)) {
        printf("iovad_init: base it not is not aligned to SZ_32M\n");
        return NULL;
    }

    iova_domain_t *iovad = malloc(sizeof(*iovad));
    if (!iovad)
        return NULL;

    memset(iovad, 0, sizeof(*iovad));

    struct iova_block *blk = malloc(sizeof(*blk));
    if (!blk) {
        free(iovad);
        return NULL;
    }

    /* don't hand out NULL pointers */
    blk->iova = base;
    blk->sz = limit - SZ_16K;
    blk->next = NULL;
    iovad->base = base;
    iovad->limit = limit;
    iovad->free_list = blk;

    return iovad;
}

void iovad_shutdown(iova_domain_t *iovad, dart_dev_t *dart)
{
    struct iova_block *blk = iovad->free_list;

    while (blk != NULL) {
        struct iova_block *blk_free = blk;
        blk = blk->next;

        free(blk_free);
    }

    if (dart)
        for (u64 addr = iovad->base; addr < iovad->limit; addr += SZ_32M)
            dart_free_l2(dart, addr);

    free(iovad);
}

bool iova_reserve(iova_domain_t *iovad, u64 iova, size_t sz)
{
    iova = ALIGN_DOWN(iova, SZ_16K);
    sz = ALIGN_UP(sz, SZ_16K);

    if (iova == 0) {
        iova += SZ_16K;
        sz -= SZ_16K;
    }
    if (sz == 0)
        return true;

    if (!iovad->free_list) {
        printf("iova_reserve: trying to reserve iova range but empty free list\n");
        return false;
    }

    struct iova_block *blk = iovad->free_list;
    struct iova_block *blk_prev = NULL;
    while (blk != NULL) {
        if (iova >= blk->iova && iova < (blk->iova + blk->sz)) {
            if (iova + sz >= (blk->iova + blk->sz)) {
                printf("iova_reserve: tried to reserve [%lx; +%lx] but block in free list has "
                       "range [%lx; +%lx]\n",
                       iova, sz, blk->iova, blk->sz);
                return false;
            }

            if (iova == blk->iova && sz == blk->sz) {
                /* if the to-be-reserved range is present as a single block in the free list we just
                 * need to remove it */
                if (blk_prev)
                    blk_prev->next = blk->next;
                else
                    iovad->free_list = NULL;

                free(blk);
                return true;
            } else if (iova == blk->iova) {
                /* cut off the reserved range from the beginning */
                blk->iova += sz;
                blk->sz -= sz;
                return true;
            } else if (iova + sz == blk->iova + blk->sz) {
                /* cut off the reserved range from the end */
                blk->sz -= sz;
                return true;
            } else {
                /* the to-be-reserved range is in the middle and we'll have to split this block */
                struct iova_block *blk_new = malloc(sizeof(*blk_new));
                if (!blk_new) {
                    printf("iova_reserve: out of memory.\n");
                    return false;
                }

                blk_new->iova = iova + sz;
                blk_new->sz = blk->iova + blk->sz - blk_new->iova;
                blk_new->next = blk->next;
                blk->next = blk_new;
                blk->sz = iova - blk->iova;
                return true;
            }
        }

        blk_prev = blk;
        blk = blk->next;
    }

    printf("iova_reserve: tried to reserve [%lx; +%lx] but range is already used.\n", iova, sz);
    return false;
}

u64 iova_alloc(iova_domain_t *iovad, size_t sz)
{
    sz = ALIGN_UP(sz, SZ_16K);

    struct iova_block *blk_prev = NULL;
    struct iova_block *blk = iovad->free_list;
    while (blk != NULL) {
        if (blk->sz == sz) {
            u64 iova = blk->iova;

            if (blk_prev)
                blk_prev->next = blk->next;
            else
                iovad->free_list = blk->next;

            free(blk);
            return iova;
        } else if (blk->sz > sz) {
            u64 iova = blk->iova;

            blk->iova += sz;
            blk->sz -= sz;

            return iova;
        }

        blk_prev = blk;
        blk = blk->next;
    }

    return 0;
}

void iova_free(iova_domain_t *iovad, u64 iova, size_t sz)
{
    sz = ALIGN_UP(sz, SZ_16K);

    struct iova_block *blk_prev = NULL;
    struct iova_block *blk = iovad->free_list;

    /* create a new free list if it's empty */
    if (!blk) {
        blk = malloc(sizeof(*blk));
        if (!blk)
            panic("out of memory in iovad_free");
        blk->iova = iova;
        blk->sz = sz;
        blk->next = NULL;
        iovad->free_list = blk;
        return;
    }

    while (blk != NULL) {
        if ((iova + sz) == blk->iova) {
            /* extend the block at the beginning */
            blk->iova -= sz;
            blk->sz += sz;

            /* if we have just extended the start of the free list we're already done */
            if (!blk_prev)
                return;

            /* check if we can merge two blocks otherwise */
            if ((blk_prev->iova + blk_prev->sz) == blk->iova) {
                blk_prev->sz += blk->sz;
                blk_prev->next = blk->next;
                free(blk);
            }

            return;
        } else if ((iova + sz) < blk->iova) {
            /* create a new block */
            struct iova_block *blk_new = malloc(sizeof(*blk_new));
            if (!blk_new)
                panic("iova_free: out of memory\n");

            blk_new->iova = iova;
            blk_new->sz = sz;
            blk_new->next = blk;

            if (blk_prev)
                blk_prev->next = blk_new;
            else
                iovad->free_list = blk_new;

            return;
        }

        blk_prev = blk;
        blk = blk->next;
    }

    panic("iovad_free: corruption detected, unable to insert freed range\n");
}

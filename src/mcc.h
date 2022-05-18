/* SPDX-License-Identifier: MIT */

#ifndef MCC_H
#define MCC_H

#include "types.h"

struct mcc_carveout {
    u64 base;
    u64 size;
};

extern size_t mcc_carveout_count;
extern struct mcc_carveout mcc_carveouts[];

int mcc_init(void);
int mcc_unmap_carveouts(void);

#endif

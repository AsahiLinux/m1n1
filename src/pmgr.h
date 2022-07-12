/* SPDX-License-Identifier: MIT */

#ifndef PMGR_H
#define PMGR_H

#include "types.h"

#define PMGR_DIE_OFFSET 0x2000000000

#define PMGR_DEVICE_ID GENMASK(15, 0)
#define PMGR_DIE_ID    GENMASK(31, 28)

int pmgr_init(void);

int pmgr_power_enable(u32 id);
int pmgr_power_disable(u32 id);

int pmgr_adt_power_enable(const char *path);
int pmgr_adt_power_disable(const char *path);
int pmgr_adt_reset(const char *path);

int pmgr_reset(int die, const char *name);

#endif

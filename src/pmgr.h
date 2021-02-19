/* SPDX-License-Identifier: MIT */

#ifndef PMGR_H
#define PMGR_H

#include "types.h"

int pmgr_init(void);

int pmgr_clock_enable(u16 id);
int pmgr_clock_disable(u16 id);

int pmgr_adt_clocks_enable(const char *path);
int pmgr_adt_clocks_disable(const char *path);

#endif

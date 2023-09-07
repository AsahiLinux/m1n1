/* SPDX-License-Identifier: MIT */

#ifndef ISP_H
#define ISP_H

#include "types.h"

int isp_init(void);
int isp_get_heap(u64 *phys, u64 *iova, u64 *size);

#endif

/* SPDX-License-Identifier: GPL-2.0-or-later */

#ifndef ISP_H
#define ISP_H

#include "types.h"

int isp_init(void);
int isp_get_heap(u64 *phys, u64 *iova, u64 *size);
u64 isp_iova_base(void);

#endif

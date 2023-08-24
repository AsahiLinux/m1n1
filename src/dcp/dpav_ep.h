// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* Copyright 2023 Janne Grunau <j@jannau.net> */

#ifndef __APPLE_DCP_DPAV_EP_H__
#define __APPLE_DCP_DPAV_EP_H__

#include "../types.h"

typedef struct dcp_dev dcp_dev_t;

typedef struct dcp_dpav_if dcp_dpav_if_t;

dcp_dpav_if_t *dcp_dpav_init(dcp_dev_t *dcp);
int dcp_dpav_shutdown(dcp_dpav_if_t *dpav);

#endif

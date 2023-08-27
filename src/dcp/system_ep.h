// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* Copyright 2023 Janne Grunau <j@jannau.net> */

#ifndef DCP_SYSTEM_EP_H
#define DCP_SYSTEM_EP_H

#include "../types.h"

typedef struct dcp_dev dcp_dev_t;

typedef struct dcp_system_if dcp_system_if_t;

dcp_system_if_t *dcp_system_init(dcp_dev_t *dcp);
int dcp_system_set_property_u64(dcp_system_if_t *system, const char *name, u64 value);
int dcp_system_shutdown(dcp_system_if_t *system);

#endif

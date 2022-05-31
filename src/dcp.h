/* SPDX-License-Identifier: MIT */

#ifndef DCP_H
#define DCP_H

#include "asc.h"
#include "dart.h"
#include "rtkit.h"

typedef struct {
    dart_dev_t *dart_dcp;
    dart_dev_t *dart_disp;
    iova_domain_t *iovad_dcp;
    asc_dev_t *asc;
    rtkit_dev_t *rtkit;
} dcp_dev_t;

dcp_dev_t *dcp_init(const char *dcp_path, const char *dcp_dart_path, const char *disp_dart_path);

int dcp_shutdown(dcp_dev_t *dcp, bool sleep);

#endif

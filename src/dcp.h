/* SPDX-License-Identifier: MIT */

#ifndef DCP_H
#define DCP_H

#include "afk.h"
#include "asc.h"
#include "dart.h"
#include "rtkit.h"

typedef struct dcp_dev {
    dart_dev_t *dart_dcp;
    dart_dev_t *dart_disp;
    iova_domain_t *iovad_dcp;
    asc_dev_t *asc;
    rtkit_dev_t *rtkit;
    afk_epic_t *afk;
} dcp_dev_t;

dcp_dev_t *dcp_init(const char *dcp_path, const char *dcp_dart_path, const char *disp_dart_path);

int dcp_shutdown(dcp_dev_t *dcp, bool sleep);

#endif

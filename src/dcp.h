/* SPDX-License-Identifier: MIT */

#ifndef DCP_H
#define DCP_H

#include "asc.h"
#include "dart.h"
#include "rtkit.h"

typedef struct dp_phy_configure_opts {
    u32 link_rate;
    u32 lanes;
    bool set_rate;
    bool set_lanes;
} dp_phy_configure_opts_t;

typedef struct dptx_phy dptx_phy_t;
typedef struct afk_epic_service afk_epic_service_t;

typedef struct dptx_port {
    bool enabled;
    u32 unit;
    afk_epic_service_t *service;
    dp_phy_configure_opts_t phy_opts;
    dptx_phy_t *phy;
    u32 link_rate, pending_link_rate;
} dptx_port_t;

typedef struct {
    dart_dev_t *dart_dcp;
    dart_dev_t *dart_disp;
    iova_domain_t *iovad_dcp;
    asc_dev_t *asc;
    rtkit_dev_t *rtkit;

    dptx_port_t *port;
} dcp_dev_t;

dcp_dev_t *dcp_init(const char *dcp_path, const char *dcp_dart_path, const char *disp_dart_path);

int dcp_shutdown(dcp_dev_t *dcp, bool sleep);

#endif

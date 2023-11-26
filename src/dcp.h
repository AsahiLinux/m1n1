/* SPDX-License-Identifier: MIT */

#ifndef DCP_H
#define DCP_H

#include "afk.h"
#include "asc.h"
#include "dart.h"
#include "rtkit.h"

#include "dcp/dpav_ep.h"
#include "dcp/dptx_port_ep.h"
#include "dcp/system_ep.h"

typedef struct {
    const char dcp[24];
    const char dcp_dart[24];
    const char disp_dart[24];
    const char dptx_phy[24];
    const char dp2hdmi_gpio[24];
    const char pmgr_dev[24];
    const char dcp_alias[8];
    u32 dcp_index;
    u8 num_dptxports;
    u8 die;
} display_config_t;

typedef struct dcp_dev {
    dart_dev_t *dart_dcp;
    dart_dev_t *dart_disp;
    iova_domain_t *iovad_dcp;
    asc_dev_t *asc;
    rtkit_dev_t *rtkit;
    afk_epic_t *afk;
    dcp_system_if_t *system_ep;
    dcp_dpav_if_t *dpav_ep;
    dcp_dptx_if_t *dptx_ep;
    dptx_phy_t *phy;
    u32 die;
    u32 dp2hdmi_pwr_gpio;
    u32 hdmi_pwr_gpio;
} dcp_dev_t;

int dcp_connect_dptx(dcp_dev_t *dcp);
int dcp_work(dcp_dev_t *dcp);

dcp_dev_t *dcp_init(const display_config_t *config);

int dcp_shutdown(dcp_dev_t *dcp, bool sleep);

#endif

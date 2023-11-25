// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* Copyright 2022 Sven Peter <sven@svenpeter.dev> */

#ifndef __APPLE_DCP_DPTX_PORT_EP_H__
#define __APPLE_DCP_DPTX_PORT_EP_H__

#include "../types.h"

typedef struct dcp_dev dcp_dev_t;

typedef struct dptx_phy dptx_phy_t;

typedef struct dcp_dptx_if dcp_dptx_if_t;

enum dptx_apcall {
    DPTX_APCALL_ACTIVATE = 0,
    DPTX_APCALL_DEACTIVATE = 1,
    DPTX_APCALL_GET_MAX_DRIVE_SETTINGS = 2,
    DPTX_APCALL_SET_DRIVE_SETTINGS = 3,
    DPTX_APCALL_GET_DRIVE_SETTINGS = 4,
    DPTX_APCALL_WILL_CHANGE_LINKG_CONFIG = 5,
    DPTX_APCALL_DID_CHANGE_LINK_CONFIG = 6,
    DPTX_APCALL_GET_MAX_LINK_RATE = 7,
    DPTX_APCALL_GET_LINK_RATE = 8,
    DPTX_APCALL_SET_LINK_RATE = 9,
    DPTX_APCALL_GET_MAX_LANE_COUNT = 10,
    DPTX_APCALL_GET_ACTIVE_LANE_COUNT = 11,
    DPTX_APCALL_SET_ACTIVE_LANE_COUNT = 12,
    DPTX_APCALL_GET_SUPPORTS_DOWN_SPREAD = 13,
    DPTX_APCALL_GET_DOWN_SPREAD = 14,
    DPTX_APCALL_SET_DOWN_SPREAD = 15,
    DPTX_APCALL_GET_SUPPORTS_LANE_MAPPING = 16,
    DPTX_APCALL_SET_LANE_MAP = 17,
    DPTX_APCALL_GET_SUPPORTS_HPD = 18,
    DPTX_APCALL_FORCE_HOTPLUG_DETECT = 19,
    DPTX_APCALL_INACTIVE_SINK_DETECTED = 20,
    DPTX_APCALL_SET_TILED_DISPLAY_HINTS = 21,
    DPTX_APCALL_DEVICE_NOT_RESPONDING = 22,
    DPTX_APCALL_DEVICE_BUSY_TIMEOUT = 23,
    DPTX_APCALL_DEVICE_NOT_STARTED = 24,
};

#define DCPDPTX_REMOTE_PORT_CORE      GENMASK(3, 0)
#define DCPDPTX_REMOTE_PORT_DFP       GENMASK(7, 4)
#define DCPDPTX_REMOTE_PORT_DIE       GENMASK(11, 8)
#define DCPDPTX_REMOTE_PORT_CONNECTED BIT(15)

enum dptx_link_rate {
    LINK_RATE_RBR = 0x06,
    LINK_RATE_HBR = 0x0a,
    LINK_RATE_HBR2 = 0x14,
    LINK_RATE_HBR3 = 0x1e,
};

dcp_dptx_if_t *dcp_dptx_init(dcp_dev_t *dcp, u32 num_dptxports);
int dcp_dptx_shutdown(dcp_dptx_if_t *dptx);

int dcp_dptx_connect(dcp_dptx_if_t *dptx, dptx_phy_t *phy, u32 die, u32 port);
int dcp_dptx_hpd(dcp_dptx_if_t *dptx, u32 port, bool hpd);
int dcp_dptx_disconnect(dcp_dptx_if_t *dptx, u32 port);
int dcp_dptx_hpd(dcp_dptx_if_t *dptx, u32 port, bool hpd);

#endif

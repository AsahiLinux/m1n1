/* SPDX-License-Identifier: MIT */

#ifndef DCP_DPTX_PHY_H
#define DCP_DPTX_PHY_H

#include "../types.h"

typedef struct dptx_phy dptx_phy_t;

int dptx_phy_activate(dptx_phy_t *phy);
int dptx_phy_set_active_lane_count(dptx_phy_t *phy, u32 num_lanes);
int dptx_phy_set_link_rate(dptx_phy_t *phy, u32 link_rate);

u32 dptx_phy_dcp_output(dptx_phy_t *phy);

dptx_phy_t *dptx_phy_init(const char *phy_path, u32 dcp_index);
void dptx_phy_shutdown(dptx_phy_t *phy);

#endif /* DCP_DPTX_PHY_H */

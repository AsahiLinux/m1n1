/* SPDX-License-Identifier: MIT */

#ifndef DCP_DP_PHY_H
#define DCP_DP_PHY_H

typedef struct dptx_phy dptx_phy_t;

int dptx_phy_configure(dptx_phy_t *phy, int state);
dptx_phy_t *dptx_phy_init(const char *phy_path);
void dptx_phy_shutdown(dptx_phy_t *phy);

#endif /* DCP_DP_PHY_H */

# SPDX-License-Identifier: GPL-2.0-or-later

for phy in ["dptx-phy", "lpdptx-phy0", "lpdptx-phy1"]:
    if phy in hv.adt["/arm-io"]:
        trace_device("/arm-io/" + phy)

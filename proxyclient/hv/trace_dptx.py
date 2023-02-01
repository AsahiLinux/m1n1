# SPDX-License-Identifier: MIT

for phy in ["dptx-phy", "lpdptx-phy0", "lpdptx-phy1"]:
    if phy in hv.adt["/arm-io"]:
        trace_device("/arm-io/" + phy)

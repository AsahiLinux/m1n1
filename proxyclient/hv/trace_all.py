# SPDX-License-Identifier: MIT

from m1n1.utils import irange

# Map the entire MMIO range as traceable
for r in hv.adt["/arm-io"].ranges:
    trace_range(irange(r.parent_addr, r.size), mode=TraceMode.ASYNC)

# Skip some noisy devices
try:
    trace_device("/arm-io/usb-drd0", False)
except KeyError:
    pass
try:
    trace_device("/arm-io/usb-drd1", False)
except KeyError:
    pass
try:
    trace_device("/arm-io/uart2", False)
except KeyError:
    pass
trace_device("/arm-io/error-handler", False)
trace_device("/arm-io/aic", False)
trace_device("/arm-io/spi1", False)
trace_device("/arm-io/pmgr", False)

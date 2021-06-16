# SPDX-License-Identifier: MIT

# Map the entire MMIO range as traceable
trace_range(range(0x2_00000000, 0x7_00000000))

# Skip some noisy devices
try:
    trace_device("/arm-io/usb-drd0", False)
except KeyError:
    pass
try:
    trace_device("/arm-io/usb-drd1", False)
except KeyError:
    pass
trace_device("/arm-io/uart2", False)
trace_device("/arm-io/error-handler", False)
trace_device("/arm-io/aic", False)
trace_device("/arm-io/spi1", False)
trace_device("/arm-io/pmgr", False)

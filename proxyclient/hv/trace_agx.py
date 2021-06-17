# SPDX-License-Identifier: MIT

trace_device("/arm-io/sgx", False)
trace_device("/arm-io/pmp", False)
trace_device("/arm-io/gfx-asc", False)

from m1n1.trace.asc import ASCTracer

ASCTracer = ASCTracer._reloadcls()
gfx_tracer = ASCTracer(hv, "/arm-io/gfx-asc", verbose=True)
gfx_tracer.start()

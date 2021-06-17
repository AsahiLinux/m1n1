# SPDX-License-Identifier: MIT

trace_device("/arm-io/dcp", True, ranges=[1])

from m1n1.trace.asc import ASCTracer

ASCTracer = ASCTracer._reloadcls()
dcp_tracer = ASCTracer(hv, "/arm-io/dcp", verbose=1)
dcp_tracer.start()

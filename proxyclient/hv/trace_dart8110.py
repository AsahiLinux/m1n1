# SPDX-License-Identifier: MIT

from m1n1.trace.dart8110 import DART8110Tracer

DART8110Tracer = DART8110Tracer._reloadcls()

DEVICES = [
    "/arm-io/dart-apr0",
    "/arm-io/dart-apr1",
]

dart_tracers = {}

for i in DEVICES:
    p.pmgr_adt_clocks_enable(i)
    tracer = DART8110Tracer(hv, i, verbose=3)
    tracer.start()

    dart_tracers[i.split("-")[-1]] = tracer

del tracer

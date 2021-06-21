# SPDX-License-Identifier: MIT

from m1n1.trace.dart import DARTTracer

DARTTracer = DARTTracer._reloadcls()

DEVICES = [
    "/arm-io/dart-pmp",
    "/arm-io/dart-sep",
    "/arm-io/dart-sio",
    "/arm-io/dart-usb1",
    "/arm-io/dart-disp0",
    "/arm-io/dart-dcp",
    "/arm-io/dart-dispext0",
    "/arm-io/dart-dcpext",
    "/arm-io/dart-scaler",
]

dart_tracers = {}

for i in DEVICES:
    tracer = DARTTracer(hv, i, verbose=3)
    tracer.start()

    dart_tracers[i.split("-")[-1]] = tracer

del tracer

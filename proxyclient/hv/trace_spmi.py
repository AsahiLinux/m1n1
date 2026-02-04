# SPDX-License-Identifier: MIT

from m1n1.utils import *
from m1n1.trace.spmi import SPMITracer, SPMIDevTracer, ACE3SPMIDevTracer
from m1n1.hw.spmi import SPMIRegs

def make_dev_tracers(tracer):
    for dev in tracer.dev:
        if not hasattr(dev, "reg"):
            continue
        addr = dev.reg[0]
        if dev.name.startswith('hpm'):
            devtracer = ACE3SPMIDevTracer(addr, dev.name)
        else:
            devtracer = SPMIDevTracer(addr, dev.name)
        tracer.add_device(addr, devtracer)

for dname in ["/arm-io/nub-spmi-a0", "/arm-io/nub-spmi0", "/arm-io/nub-spmi1"]:
    spmi_tracer = SPMITracer(hv, dname, verbose=0)
    make_dev_tracers(spmi_tracer)
    spmi_tracer.start()

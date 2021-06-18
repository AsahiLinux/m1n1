# SPDX-License-Identifier: MIT

from m1n1.trace.gpio import GPIOTracer

#trace_device("/arm-io/gpio", True)

# trace gpio interrups, useful to follow the cascaded interrupts
aic_phandle = getattr(hv.adt["/arm-io/aic"], "AAPL,phandle")
node = hv.adt["/arm-io/gpio"]
if getattr(node, "interrupt-parent") == aic_phandle:
    for irq in getattr(node, "interrupts"):
        hv.trace_irq(node.name, irq, 1, hv.IRQTRACE_IRQ)

GPIOTracer = GPIOTracer._reloadcls()
gpio_tracer = GPIOTracer(hv, "/arm-io/gpio", verbose=0)
gpio_tracer.start()

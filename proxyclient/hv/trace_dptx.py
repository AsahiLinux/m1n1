# SPDX-License-Identifier: MIT

from m1n1.trace.gpio import GPIOTracer

# trace gpio interrups, useful to follow the cascaded interrupts
aic_phandle = getattr(hv.adt["/arm-io/aic"], "AAPL,phandle")
node = hv.adt["/arm-io/aop-gpio"]
path = "/arm-io/aop-gpio"

if getattr(node, "interrupt-parent") == aic_phandle:
    for irq in getattr(node, "interrupts"):
        hv.trace_irq(node.name, irq, 1, hv.IRQTRACE_IRQ)

PIN_NAMES_DP2HDMI_J473 = {
    0x28: "force_dfp",
    0x31: "hdmi_hpd",
}

GPIOTracer = GPIOTracer._reloadcls()
gpio_tracer = GPIOTracer(hv, path, PIN_NAMES_DP2HDMI_J473, verbose=0)
gpio_tracer.start()

trace_device("/arm-io/dptx-phy")


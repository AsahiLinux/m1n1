# SPDX-License-Identifier: MIT

from m1n1.trace.gpio import GPIOTracer

#trace_device("/arm-io/gpio", True)

# trace gpio interrups, useful to follow the cascaded interrupts
aic_phandle = getattr(hv.adt["/arm-io/aic"], "AAPL,phandle")
try:
    node = hv.adt["/arm-io/gpio0"]
    path = "/arm-io/gpio0"
except:
    node = hv.adt["/arm-io/gpio"]
    path = "/arm-io/gpio"

if getattr(node, "interrupt-parent") == aic_phandle:
    for irq in getattr(node, "interrupts"):
        hv.trace_irq(node.name, irq, 1, hv.IRQTRACE_IRQ)

PIN_NAMES_j274 = {
    0xC0: "i2c0:scl",
    0xBC: "i2c0:sda",
    0xC9: "i2c1:scl",
    0xC7: "i2c1:sda",
    0xA3: "i2c2:scl",
    0xA2: "i2c2:sda",
    106:  "hpm:irq",
    136:  "bluetooth:irq",
    196:  "wlan:irq",
    183:  "cs42l83:irq",
    182:  "tas5770:irq",
    152:  "pci@0,0",
    153:  "pci@1,0",
    33:   "pci@2,0",
    #0x2D: "spi_nor:CS",
}

GPIOTracer = GPIOTracer._reloadcls()
gpio_tracer = GPIOTracer(hv, path, PIN_NAMES_j274, verbose=0)
gpio_tracer.start()

# SPDX-License-Identifier: MIT
from construct import *

GpioPin = BitStruct(
    "u_top"    / BitsInteger(13),
    "group"    / BitsInteger(3),
    "u15"      / Bit,
    "u14"      / Bit,
    "u13"      / Bit,
    "u12"      / Bit,
    "u11"      / Bit,
    "u10"      / Bit,
    "cfg_done" / Bit,
    "u8"       / Bit,
    "u7"       / Bit,
    "u6"       / Bit,
    "periph"   / Bit,
    "u4"       / Bit,
    "irq"      / BitsInteger(3),
    "value"    / Bit,
    )

class MmioTraceGpio:

    def __init__(self, name, nr_pins):
        self.name = name
        self.nr_pins = nr_pins
        self.pins = [0 for x in range(nr_pins)]
        self.pn = {
            0xc0: "i2c0:scl",
            0xbc: "i2c0:sda",
            0xc9: "i2c1:scl",
            0xc7: "i2c1:sda",
            0xa3: "i2c2:scl",
            0xa2: "i2c2:sda",
            106:  "hpm:irq",
            136:  "bluetooth:irq",
            196:  "wlan:irq",
            183:  "cs42l83:irq",
            182:  "tas5770:irq",
            152:  "pci@0,0",
            153:  "pci@1,0",
            33:   "pci@2,0",
        }
        self.IRQ_ACT = 0x800
        self.IRQ_GRP_SZ = 0x40


    def handle_pin(self, pin, data, write):
        # ignore noisy SPI NOR chip select?
        if pin == 45:
            return

        if data != self.pins[pin]:
            p = GpioPin.parse(Int32ub.build(data))
            if not write and not p.cfg_done:
                return

            config = f"top:{p.u_top:#04x} group:{p.group} u15:{p.u15} u14:{p.u14} " + \
                f"u13:{p.u13} u12:{p.u12} u11:{p.u11} u10:{p.u10} " + \
                f"cfg_done:{p.cfg_done} u8:{p.u8} u7:{p.u7} u6:{p.u6} " + \
                f"periph:{p.periph} u4:{p.u4} irq:{p.irq:#3x} val:{p.value}"

            t = "W" if write else "R"
            print(f"{self.name} {self.pn.get(pin, pin):>15}: {t}   {config}")
            self.pins[pin] = data


    def handle_irq(self, group, start, data, write):
        desc = "masking" if write else "active"
        if data == 0xFFFFFFFF:
            print(f"{self.name}: IRQ group {group} {desc:>7}: {start:>3} - {start + 31:>3}")
        else:
            irqs = [self.pn.get(start + i, start + i) for i in range(32) if (data >> i) & 0x1]
            print(f"{self.name}: IRQ group {group} {desc:>7}: " + " ".join(irqs))


    def handle_mmiotrace(self, evt, zone):
        offset = evt.addr - zone.start

        if evt.flags.WIDTH != 2:
            print(f"GPIO: unexpected width {evt.flags.WIDTH}")
            return

        if offset >= 0 and offset < 4 * self.nr_pins:
            self.handle_pin(offset // 4, int(evt.data), evt.flags.WRITE)

        elif offset >= self.IRQ_ACT and offset < self.IRQ_ACT + 7 * self.IRQ_GRP_SZ:
            if evt.data:
                group = (offset - self.IRQ_ACT) // self.IRQ_GRP_SZ
                start = (offset & (self.IRQ_GRP_SZ - 1)) * 8
                self.handle_irq(group, start, evt.data, evt.flags.WRITE)

        else:
            t = "W" if evt.flags.WRITE else "R"
            m = "+" if evt.flags.MULTI else " "
            print(f"{self.name}: {t}.{1<<evt.flags.WIDTH:<2}{m} unknown offset {offset:#06x}) = {evt.data:#x}")


# trace gpio interrups, useful to follow the cascaded interrupts
aic_phandle = getattr(hv.adt["/arm-io/aic"], "AAPL,phandle")
node = hv.adt["/arm-io/gpio"]
if getattr(node, "interrupt-parent") == aic_phandle:
    for irq in getattr(node, "interrupts"):
        hv.trace_irq(node.name, irq, 1, hv.IRQTRACE_IRQ)

gpio_trace = MmioTraceGpio(node.name, getattr(node, "#gpio-pins"))

hv.trace_device("/arm-io/gpio", handler=gpio_trace)

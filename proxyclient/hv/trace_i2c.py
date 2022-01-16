# SPDX-License-Identifier: MIT

from m1n1.trace.i2c import I2CTracer

I2CTracer = I2CTracer._reloadcls()

i2c_tracers = {}

for node in hv.adt["/arm-io"]:
    if node.name.startswith("i2c"):
        n = int(node.name[3:])
        i2c_tracers[n] = I2CTracer(hv, f"/arm-io/i2c{n}", verbose=0)
        i2c_tracers[n].stop()
        i2c_tracers[n].start()
        if hv.ctx:
            for irq in getattr(node, "interrupts"):
                hv.trace_irq(node.name, irq, 1, hv.IRQTRACE_IRQ)

from m1n1.gpiola import GPIOLogicAnalyzer

if not hv.started:
    for cpu in list(hv.adt["cpus"]):
        if cpu.name == "cpu3":
            print(f"Removing ADT node {cpu._path}")
            del hv.adt["cpus"][cpu.name]

if not hv.started or hv.ctx is not None:
    m = GPIOLogicAnalyzer(u, "arm-io/gpio",
                        pins={"scl": 0xc9, "sda": 0xc7},
                        div=1, on_pin_change=True, cpu=3)

    m.load_regmap(list(i2c_tracers[1].regmaps.values())[0],
                  regs={"SMSTA", "XFSTA"})

def start_la():
    m.start(1000000, bufsize=0x80000)
    hv.cont()

def stop_la():
    m.complete()
    m.show()

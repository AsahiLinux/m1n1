import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1 import asm
from m1n1.shell import run_shell
from m1n1.gpiola import GPIOLogicAnalyzer
from m1n1.hw.spi import *

p.smp_start_secondaries()

spi = u.adt["arm-io/spi2"].get_reg(0)[0] + 0x8000
regs = SPIRegs(u, spi)

aic = u.adt["arm-io/aic"].get_reg(0)[0]

gpio = u.adt["arm-io/gpio0"].get_reg(0)[0]
count = u.adt["arm-io/gpio0"].getprop("#gpio-pins")

pins={}
for i in range(150, 150+32):
    pins[f"pin{i}"] = i

m = GPIOLogicAnalyzer(u, "arm-io/gpio0",
                      pins=pins,
                      regs={"a": gpio},
                      div=1,
                      cpu=1,
                      on_pin_change=True,
                      on_reg_change=False)

regs.CTRL.val = 0xc
regs.PIN.val = 0x2
regs.CFG.val = 0x20 | (1<<15) | 6
regs.CFG.val = 0x20 | (1<<15) | 4
regs.CFG.val = 0x20 | (1<<15) | 2
regs.CFG.val = 0x20 | (3<<15) | 0

m.regs = {}

m.start(30000000, bufsize=0x80000)

regs.STATUS.val = 0xffffffff
regs.IF_XFER.val = 0xffffffff
regs.IF_FIFO.val = 0xffffffff

regs.CLKDIV.val = 0xfff
regs.INTER_DELAY.val = 0x1000

regs.SHIFTCFG.val = 0x21fcf7

regs.PIN.val = 0x2
print("pinconfig", hex(regs.PINCFG.val))
regs.PINCFG.val = 0x100
#regs.PINCONFIG.val = 0x2-7
print("pinconfig", hex(regs.PINCFG.val))
print("shiftconfig", hex(regs.SHIFTCFG.val))

p.write32(spi + 0x3c, 0xffffffff)

regs.PINCFG.val = 0x002
regs.PINCFG.val = 0x200

#p.write32(0x28e0380bc, 0x80100000)
#p.write32(0x28e0380c4, 0x80100000)

data = b"\xff\xff\xff\xff\x00\x00\xff\xff"

for i in range(2):
    for j in data:
        regs.TXDATA.val = j | 0xffffff00
    regs.RXCNT.val = len(data)
    regs.TXCNT.val = len(data)

    regs.STATUS.val = 0xffffffff
    regs.IF_XFER.val = 0xffffffff
    regs.IF_FIFO.val = 0xffffffff

    regs.PIN.val = 0x0
    regs.CTRL.val = 0x1
    #regs.TXDATA.val = 0xff
    #regs.TXDATA.val = 0xff

    i = 0
    while regs.TXCNT.val != 0:
        print(f"{regs.TXCNT.val:#x} {regs.FIFOSTAT.reg} {regs.STATUS.val:#x} {regs.IF_FIFO.val:#x} {p.read32(spi + 0x134):#x}")
        regs.STATUS.val = 0xffffffff
        regs.IF_XFER.val = 0xffffffff
        regs.IF_FIFO.val = 0xffffffff
        #regs.CTRL.val = 0x0
        #time.sleep(0.1)
        #regs.CTRL.val = 0x1[
        print(hex(i))
        #p.write32(spi + i, 0xffffffff)
        #p.write32(spi + i, 0)
        i += 4
        if i > 0x100:
            break
    time.sleep(0.001)
    print(f"{regs.RXCNT.val:#x} {regs.FIFOSTAT.reg} {regs.STATUS.val:#x} {regs.IF_FIFO.val:#x}")
    regs.STATUS.val = 0xffffffff
    regs.IF_XFER.val = 0xffffffff
    regs.IF_FIFO.val = 0xffffffff

    mon.poll()
    
    while regs.FIFOSTAT.reg.LEVEL_RX:
        print("RX", hex(regs.RXDATA.val))

    regs.CTRL.val = 0

m.complete()
m.show()

#run_shell(globals(), msg="Have fun!")



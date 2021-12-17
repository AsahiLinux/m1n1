import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1 import asm
from m1n1.shell import run_shell
from m1n1.gpiola import GPIOLogicAnalyzer
from m1n1.hw.spi import *

p.smp_start_secondaries()

p.set32(0x28e580208, 1<<31)
p.clear32(0x28e580208, 1<<31)

spi = u.adt["arm-io/spi3"].get_reg(0)[0]
regs = SPIRegs(u, spi)

mon.add(spi, 0x10)
mon.add(spi + 0x30, 0x10)
mon.add(spi + 0x40, 0x400)

aic = u.adt["arm-io/aic"].get_reg(0)[0]
mon.add(aic + 0x6800 + (1109 // 32) * 4, 4)

gpio = u.adt["arm-io/gpio0"].get_reg(0)[0]

mon.add(gpio, 0x1c8)
mon.add(gpio+0x1e0, 0x300)

mon.poll()

m = GPIOLogicAnalyzer(u, "arm-io/gpio0",
                      pins={"miso": 0x34, "mosi": 0x35, "clk": 0x36, "cs": 0x37},
                      #pins={"miso": 0xa, "mosi": 0xb, "clk": 0x20, "cs": 0x21},
                      #pins={"clk": 46, "mosi": 47, "miso": 48, "cs": 49},
                      div=1, on_pin_change=False)

#p.write32(spi + 0x100, 0xffffffff)

regs.CTRL.val = 0xc
regs.PIN.val = 0x2
regs.CONFIG.val = 0x20 | (1<<15) | 6
regs.CONFIG.val = 0x20 | (1<<15) | 4
regs.CONFIG.val = 0x20 | (1<<15) | 2
regs.CONFIG.val = 0x20 | (3<<15) | 0

def try_all_bits():
    for i in range(0, 0x200, 4):
        v = p.read32(spi + i)
        for j in range(32):
            p.write32(spi + i, v ^ (1<<j))
            print(f"{i:4x}:{v:8x}:{j:2d} FIFO level:", regs.FIFO_LEVEL.reg.LEVEL_TX)
            mon.poll()
        p.write32(spi + i, v)


m.regs = {
    "CTRL": (spi + 0x00, R_CTRL),
    "STATUS": (spi + 0x08, R_STATUS),
    "RXCNT": (spi + 0x34),
    "TXCNT": (spi + 0x4c),
    "FIFO_STAT": (spi + 0x10c, R_FIFO_STAT),
    "ISTATUS1": (spi + 0x134, R_ISTATUS1),
    "ISTATUS2": (spi + 0x13c, R_ISTATUS2),
    "XFSTATUS": (spi + 0x1c0),
    "SHIFTCONFIG": (spi + 0x150),
    "PINCONFIG": (spi + 0x154),
    "PIN": (spi + 0xc),
    "3c": (spi + 0x3c),
    "DIVSTATUS": (spi + 0x1e0, R_DIVSTATUS)
}

m.regs = {}

m.start(300000, bufsize=0x80000)


regs.STATUS.val = 0xffffffff
regs.ISTATUS1.val = 0xffffffff
regs.ISTATUS2.val = 0xffffffff

regs.CLKDIV.val = 0xfff
regs.INTER_DLY.val = 0x1000

regs.SHIFTCONFIG.val = 0x20fcf7

regs.PIN.val = 0x2
print("pinconfig", hex(regs.PINCONFIG.val))
regs.PINCONFIG.val = 0x100
#regs.PINCONFIG.val = 0x2-7
print("pinconfig", hex(regs.PINCONFIG.val))
print("shiftconfig", hex(regs.SHIFTCONFIG.val))

#regs.PIN.val = 0x0
#regs.PIN.val = 0x2
# auto_cs OR pin_cs

#p.write32(spi + 0x150, 0x80c07)
#p.write32(spi + 0x150, 0x88c07)
print(hex(p.read32(spi + 0x150)))

#p.write32(spi + 0x160, 0)
p.write32(spi + 0x160, 0xfff0020)
p.write32(spi + 0x168, 0xffffb20)
#p.write32(spi + 0x164, 0x06000210)
#p.write32(spi + 0x180, 0x02000000)
#p.write32(spi + 0x18c, 0x500)
#regs.INTER_DLY2 = 0x20000001

p.write32(spi + 0x200, 0x0010)

p.write32(spi + 0x3c, 0xffffffff)

regs.PINCONFIG.val = 0x002
regs.PINCONFIG.val = 0x200


#p.write32(0x28e0380bc, 0x80100000)
#p.write32(0x28e0380c4, 0x80100000)

data = b"Asahi Linux"

for i in range(2):
    for j in data:
        regs.TXDATA.val = j
    regs.RXCNT.val = len(data)
    regs.TXCNT.val = len(data)

    regs.STATUS.val = 0xffffffff
    regs.ISTATUS1.val = 0xffffffff
    regs.ISTATUS2.val = 0xffffffff

    regs.PIN.val = 0x0
    regs.CTRL.val = 0x1
    #regs.TXDATA.val = 0xff
    #regs.TXDATA.val = 0xff

    i = 0
    while regs.TXCNT.val != 0:
        print(f"{regs.TXCNT.val:#x} {regs.FIFO_STAT.reg} {regs.STATUS.val:#x} {regs.ISTATUS2.val:#x} {p.read32(spi + 0x134):#x}")
        regs.STATUS.val = 0xffffffff
        regs.ISTATUS1.val = 0xffffffff
        regs.ISTATUS2.val = 0xffffffff
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
    print(f"{regs.RXCNT.val:#x} {regs.FIFO_STAT.reg} {regs.STATUS.val:#x} {regs.ISTATUS2.val:#x}")
    regs.STATUS.val = 0xffffffff
    regs.ISTATUS1.val = 0xffffffff
    regs.ISTATUS2.val = 0xffffffff

    mon.poll()
    
    while regs.FIFO_STAT.reg.LEVEL_RX:
        print("RX", hex(regs.RXDATA.val))

    regs.CTRL.val = 0

m.complete()
m.show()

def poll(count=1000):
    lval = None
    for i in range(count):
        pins = 0x35, 0x36, 0x37
        vals = [p.read32(gpio + 4 * pin) & 1 for pin in pins]
        if vals != lval:
            print(f"{i:6d}: {vals}")
        lval = vals

mon.poll()

#run_shell(globals(), msg="Have fun!")



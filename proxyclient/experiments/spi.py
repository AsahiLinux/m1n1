import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1 import asm
from m1n1.shell import run_shell
from m1n1.gpiola import GPIOLogicAnalyzer

class R_CTRL(Register32):
    RX_FIFO_RESET   = 3
    TX_FIFO_RESET   = 2
    RUN             = 0

class R_PIN(Register32):
    CS              = 1
    KEEP_MOSI       = 0
    
class R_CONFIG(Register32):
    # impl: 002fb1e6
    IE_TX_COMPLETE  = 21
    b19             = 19
    FIFO_THRESH     = 18, 17
        # 0 = 8 bytes
        # 1 = 4 bytes
        # 2 = 1 byte
        # 3 = disabled
    WORD_SIZE       = 16, 15
        # 0 = 8bit
        # 1 = 16bit
        # 2 = 32bit
    LSB_FIRST       = 13
    b12             = 12
    IE_RX_THRESH    = 8
    IE_RX_COMPLETE  = 7
    MODE            = 6, 5
        # 0 = polled
        # 1 = irq
    CPOL            = 2
    CPHA            = 1

class R_STATUS(Register32):
    TX_COMPLETE     = 22
    TXRX_THRESH     = 1     # updated if MODE == 1
    RX_COMPLETE     = 0

class R_FIFO_STAT(Register32):
    LEVEL_RX        = 31, 24
    RX_EMPTY        = 20
    LEVEL_TX        = 15, 8
    TX_FULL         = 4

class R_ISTATUS1(Register32):
    TX_XFER_DONE    = 1
    RX_XFER_DONE    = 0

class R_ISTATUS2(Register32):
    TX_OVERFLOW     = 17
    RX_UNDERRUN     = 16
    TX_EMPTY        = 9
    RX_FULL         = 8
    TX_THRESH       = 5
    RX_THRESH       = 4

class R_CLKDIV(Register32):
    DIVIDER         = 10, 0 # SPI freq = CLK / (DIVIDER + 1)

class R_INTER_DLY(Register32):
    DELAY           = 15, 0

# FIFO size: 16 bytes
# backend FIFO: TX 2 bytes, RX 1 byte?

class R_XFSTATUS(Register32):
    SR_FULL         = 26
    SHIFTING        = 20
    STATE           = 17, 16
    UNK             = 0

class R_DIVSTATUS(Register32):
    COUNT2          = 31, 16
    COUNT1          = 15, 0

class R_SHIFTCONFIG(Register32):
    OVERRIDE_CS     = 24
    BITS            = 21, 16
    RX_ENABLE       = 11
    TX_ENABLE       = 10
    CS_AS_DATA      = 9
    AND_CLK_DATA    = 8
    #?              = 2  # needs to be 1 for RX to not break
    CS_ENABLE       = 1
    CLK_ENABLE      = 0

class R_PINCONFIG(Register32):
    CLK_IDLE_VAL    = 8
    KEEP_MOSI       = 2
    NO_AUTO_CS      = 1

class R_DELAY(Register32):
    DELAY           = 31, 16
    MOSI_VAL        = 12
    SCK_VAL         = 8
    SET_MOSI        = 6
    SET_SCK         = 4
    NO_INTERBYTE    = 1
    ENABLE          = 0

class R_SCK_CONFIG(Register32):
    PERIOD          = 31, 16
    PHASE1          = 9
    PHASE0          = 8
    RESET_TO_IDLE   = 4

class R_SCK_PHASES(Register32):
    PHASE1_START   = 31, 16
    PHASE0_START   = 15, 0

class SPIRegs(RegMap):
    CTRL        = 0x00, R_CTRL
    CONFIG      = 0x04, R_CONFIG
    STATUS      = 0x08, R_STATUS
    PIN         = 0x0C, R_PIN
    TXDATA      = 0x10, Register32
    RXDATA      = 0x20, Register32
    CLKDIV      = 0x30, R_CLKDIV
    RXCNT       = 0x34, Register32
    INTER_DLY   = 0x38, R_INTER_DLY
    TXCNT       = 0x4C, Register32
    FIFO_STAT   = 0x10C, R_FIFO_STAT
    
    IMASK1      = 0x130, R_ISTATUS1
    ISTATUS1    = 0x134, R_ISTATUS1
    IMASK2      = 0x138, R_ISTATUS2
    ISTATUS2    = 0x13c, R_ISTATUS2
    
    SHIFTCONFIG = 0x150, R_SHIFTCONFIG
    PINCONFIG   = 0x154, R_PINCONFIG
    
    PRE_DLY     = 0x160, R_DELAY
    SCK_CONFIG  = 0x164, R_SCK_CONFIG
    POST_DLY    = 0x168, R_DELAY
    
    SCK_PHASES  = 0x180, R_SCK_PHASES
    
    UNK_PHASE   = 0x18c, Register32 # probably MISO sample point
    
    XFSTATUS    = 0x1c0, R_XFSTATUS
    DIVSTATUS   = 0x1e0, R_DIVSTATUS

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
                      div=1, on_pin_change=False)

#p.write32(spi + 0x100, 0xffffffff)

regs.CTRL.val = 0xc
regs.PIN.val = 0x2
regs.CONFIG.val = 0x20 | (1<<15) | 6
regs.CONFIG.val = 0x20 | (1<<15) | 4
regs.CONFIG.val = 0x20 | (1<<15) | 2
regs.CONFIG.val = 0x20 | (3<<15) | 0 | (0<<17)

def try_all_bits():
    for i in range(0, 0x200, 4):
        v = p.read32(spi + i)
        for j in range(32):
            p.write32(spi + i, v ^ (1<<j))
            print(f"{i:4x}:{v:8x}:{j:2d} FIFO level:", regs.FIFO_LEVEL.reg.LEVEL_TX)
            mon.poll()
        p.write32(spi + i, v)


regs.STATUS.val = 0xffffffff
regs.ISTATUS1.val = 0xffffffff
regs.ISTATUS2.val = 0xfffffff#f

regs.CLKDIV.val = 0xfff
regs.INTER_DLY.val = 0x1000

regs.PINCONFIG.val = 0x101

#p.write32(spi + 0x150, 0x80c07)
p.write32(spi + 0x150, 0x88c07)
print(hex(p.read32(spi + 0x150)))

#p.write32(spi + 0x160, 0)
p.write32(spi + 0x160, 0xfff0001)
p.write32(spi + 0x168, 0)
#p.write32(spi + 0x164, 0x06000210)
#p.write32(spi + 0x180, 0x02000000)
#p.write32(spi + 0x18c, 0x500)
#regs.INTER_DLY2 = 0x20000001

#p.write32(spi + 0x200, 0x11)

m.regs = {
    "CTRL": (spi + 0x00, R_CTRL),
    "STATUS": (spi + 0x08, R_STATUS),
    "RXCNT": (spi + 0x34),
    "TXCNT": (spi + 0x4c),
    "FIFO_STAT": (spi + 0x10c, R_FIFO_STAT),
    "ISTATUS1": (spi + 0x134, R_ISTATUS1),
    "ISTATUS2": (spi + 0x13c, R_ISTATUS2),
    "XFSTATUS": (spi + 0x1c0),
    "DIVSTATUS": (spi + 0x1e0, R_DIVSTATUS)
}
m.start(300000, bufsize=0x80000)

p.write32(0x28e0380c4, 0x80100000)

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
        #regs.ISTATUS1.val = 0xffffffff
        #regs.ISTATUS2.val = 0xffffffff
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
    regs.PIN.val = 0x2
    #regs.PINCONFIG.val = 0x001
    #regs.PINCONFIG.val = 0x101
    #regs.PINCONFIG.val = 0x201
    #regs.PINCONFIG.val = 0x301
    print(f"{regs.RXCNT.val:#x} {regs.FIFO_STAT.reg} {regs.STATUS.val:#x} {regs.ISTATUS2.val:#x}")
    regs.STATUS.val = 0xffffffff
    regs.ISTATUS1.val = 0xffffffff
    regs.ISTATUS2.val = 0xffffffff

    
    while regs.FIFO_STAT.reg.LEVEL_RX:
        regs.RXDATA.val

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



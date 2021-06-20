# SPDX-License-Identifier: MIT

from ..hv import TraceMode
from ..utils import *
from . import ADTDevTracer

class R_PIN(Register32):
    GROUP       = 18, 16
    CFG_DONE    = 9
    PERIPH      = 5
    CONFIG      = 3, 1
    VALUE       = 0

class GPIORegs(RegMap):
    PIN = irange(0x000, 212, 4), R_PIN

    IRQ_GROUP  = (irange(0x800, 7, 0x40), irange(0, (212 + 31) // 32, 4)), Register32

def bits32(val, start):
    return [start + i for i in range(0, 32) if int(val) & (1 << i)]

class GPIOTracer(ADTDevTracer):
    DEFAULT_MODE = TraceMode.UNBUF

    REGMAPS = [GPIORegs]
    NAMES = ["gpio"]

    PIN_NAMES = {
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
            0x2D: "spi_nor:CS"
        }

    def pn(self, pin):
        return self.PIN_NAMES.get(pin, f"Pin-{pin}")

    def r_PIN(self, val, index):
        if index == 0x2D and self.verbose < 2:
            return # ignore noisy SPI NOR CS
        self.log(f"{self.pn(index):14} R {val!s} ")

    def w_PIN(self, val, index):
        if index == 0x2D and self.verbose < 2:
            return # ignore noisy SPI NOR CS
        self.log(f"{self.pn(index):14} W {val!s} ")

    def r_IRQ_GROUP(self, val, index):
        (grp, index) = index
        if int(val) != 0:
            self.log(f"IRQ[{grp}] ACT {[self.pn(x) for x in bits32(val, index * 32)]}")

    def w_IRQ_GROUP(self, val, index):
        (grp, index) = index
        if int(val) == (1 << 32) - 1:
            self.log(f"IRQ[{grp}] ACK {index * 32} - {index * 32 + 31}")
        elif int(val) != 0:
            self.log(f"IRQ[{grp}] ACK {[self.pn(x) for x in bits32(val, index * 32)]}")


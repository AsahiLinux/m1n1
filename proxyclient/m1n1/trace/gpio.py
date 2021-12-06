# SPDX-License-Identifier: MIT

from ..hv import TraceMode
from ..utils import *
from . import ADTDevTracer

class R_PIN(Register32):
    DRIVE_STRENGTH1 = 23, 22
    LOCK            = 21
    GROUP           = 18, 16
    SCHMITT         = 15
    DRIVE_STRENGTH0 = 11, 10
    INPUT_ENABLE    = 9
    PULL            = 8, 7
    PERIPH          = 6, 5
    MODE            = 3, 1
    DATA            = 0

class GPIORegs(RegMap):
    PIN = irange(0x000, 212, 4), R_PIN

    IRQ_GROUP  = (irange(0x800, 7, 0x40), irange(0, (212 + 31) // 32, 4)), Register32

def bits32(val, start):
    return [start + i for i in range(0, 32) if int(val) & (1 << i)]

class GPIOTracer(ADTDevTracer):
    DEFAULT_MODE = TraceMode.UNBUF

    REGMAPS = [GPIORegs]
    NAMES = ["gpio"]

    PIN_NAMES = {}

    def __init__(self, hv, devpath, pin_names={}, verbose=False):
        super().__init__(hv, devpath, verbose)
        self.PIN_NAMES = pin_names

    def pn(self, pin):
        return self.PIN_NAMES.get(pin, f"Pin-{pin}")

    def r_PIN(self, val, index):
        if index not in self.PIN_NAMES and self.verbose < 2:
            return
        self.log(f"{self.pn(index):14} R {val!s} ")

    def w_PIN(self, val, index):
        if index not in self.PIN_NAMES and self.verbose < 2:
            return
        self.log(f"{self.pn(index):14} W {val!s} ")

    def r_IRQ_GROUP(self, val, index):
        (grp, index) = index
        if int(val) == 0:
            return
        pins = [self.pn(x) for x in bits32(val, index * 32) if self.verbose >= 2 or x in self.PIN_NAMES]
        if len(pins):
            self.log(f"IRQ[{grp}] ACT {pins}")

    def w_IRQ_GROUP(self, val, index):
        (grp, index) = index
        if int(val) == 0:
            return
        pins = [self.pn(x) for x in bits32(val, index * 32) if self.verbose >= 2 or x in self.PIN_NAMES]
        if len(pins):
            self.log(f"IRQ[{grp}] ACK {pins}")


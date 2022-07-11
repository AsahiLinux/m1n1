# SPDX-License-Identifier: MIT
import struct

from ..hw.dockchannel import DockChannelIRQRegs, DockChannelConfigRegs, DockChannelDataRegs
from ..hv import TraceMode
from ..utils import *
from . import ADTDevTracer

class DockChannelTracer(ADTDevTracer):
    DEFAULT_MODE = TraceMode.SYNC

    REGMAPS = [None, DockChannelIRQRegs, DockChannelConfigRegs, DockChannelDataRegs]
    NAMES = [None, "irq", "config", "data"]

    def w_TX_8(self, d):
        self.tx(struct.pack("<I", d.value)[0:1])
    def w_TX_16(self, d):
        self.tx(struct.pack("<I", d.value)[0:2])
    def w_TX_24(self, d):
        self.tx(struct.pack("<I", d.value)[0:3])
    def w_TX_32(self, d):
        self.tx(struct.pack("<I", d.value))

    def r_RX_8(self, d):
        self.rx(struct.pack("<I", d.value)[1:2])
    def r_RX_16(self, d):
        self.rx(struct.pack("<I", d.value)[1:3])
    def r_RX_24(self, d):
        self.rx(struct.pack("<I", d.value)[1:4])
    def r_RX_32(self, d):
        self.rx(struct.pack("<I", d.value))

    def tx(self, d):
        pass

    def rx(self, d):
        pass

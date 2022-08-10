# SPDX-License-Identifier: MIT

from m1n1.hv import TraceMode
from m1n1.hw.dwc3 import XhciRegs, Dwc3CoreRegs
from m1n1.hw.atc import PhyRegs
from m1n1.trace import ADTDevTracer
from m1n1.utils import *

class PhyTracer(ADTDevTracer):
    DEFAULT_MODE = TraceMode.SYNC

    REGMAPS = [PhyRegs]
    NAMES = ["usb-phy"]

    ENDPOINTS = {}

    def init_state(self):
        self.state.ep = {}

    def start(self):
        self.cmd_cache = {}
        super().start()

class Dwc3Tracer(ADTDevTracer):
    DEFAULT_MODE = TraceMode.SYNC

    REGMAPS = [XhciRegs, None, Dwc3CoreRegs]
    NAMES = ["xhci", None, "dwc-core"]


PhyTracer = PhyTracer._reloadcls()
phy_tracer = PhyTracer(hv, "/arm-io/atc-phy1", verbose=2)
phy_tracer.start()


Dwc3Tracer = Dwc3Tracer._reloadcls()
dwc3_tracer = Dwc3Tracer(hv, "/arm-io/usb-drd1", verbose=2)
dwc3_tracer.start()

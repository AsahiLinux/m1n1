# SPDX-License-Identifier: MIT

from m1n1.hv import TraceMode
from m1n1.hw.dwc3 import XhciRegs, Dwc3CoreRegs, PipehandlerRegs
from m1n1.hw.atc import Usb2PhyRegs, AtcPhyRegs
from m1n1.trace import ADTDevTracer
from m1n1.utils import *


class PhyTracer(ADTDevTracer):
    REGMAPS = [
        Usb2PhyRegs,
        None,
        (AtcPhyRegs, 0x20000),
        (AtcPhyRegs, 0x0),
        (AtcPhyRegs, 0x2000),
        (AtcPhyRegs, 0x2200),
        (AtcPhyRegs, 0x2800),
        (AtcPhyRegs, 0x2A00),
        (AtcPhyRegs, 0x7000),
        (AtcPhyRegs, 0xA00),
        (AtcPhyRegs, 0x800),
        (AtcPhyRegs, 0xD000),
        (AtcPhyRegs, 0x14000),
        (AtcPhyRegs, 0xC000),
        (AtcPhyRegs, 0x13000),
        (AtcPhyRegs, 0xB000),
        (AtcPhyRegs, 0x12000),
        (AtcPhyRegs, 0x9000),
        (AtcPhyRegs, 0x10000),
        (AtcPhyRegs, 0x1000),
        (AtcPhyRegs, 0x50000),
        (AtcPhyRegs, 0x50200),
        (AtcPhyRegs, 0x54000),
        None,
        None,
        None,
        (AtcPhyRegs, 0xA000),
        (AtcPhyRegs, 0x11000),
    ]


class Dwc3VerboseTracer(ADTDevTracer):
    REGMAPS = [XhciRegs, None, Dwc3CoreRegs, PipehandlerRegs]
    NAMES = ["xhci", None, "dwc-core", "pipehandler"]


class Dwc3Tracer(ADTDevTracer):
    REGMAPS = [None, None, Dwc3CoreRegs, PipehandlerRegs]
    NAMES = [None, None, "dwc-core", "pipehandler"]


PhyTracer = PhyTracer._reloadcls()
Dwc3Tracer = Dwc3Tracer._reloadcls()
Dwc3VerboseTracer = Dwc3VerboseTracer._reloadcls()

phy_tracer = PhyTracer(hv, "/arm-io/atc-phy1", verbose=2)
dwc3_tracer = Dwc3Tracer(hv, "/arm-io/usb-drd1", verbose=2)

phy_tracer.start()
dwc3_tracer.start()

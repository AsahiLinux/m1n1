# SPDX-License-Identifier: MIT
from ...utils import *

from .crash import ASCCrashLogEndpoint
from .syslog import ASCSysLogEndpoint
from .mgmt import ASCManagementEndpoint
from .kdebug import ASCKDebugEndpoint
from .ioreporting import ASCIOReportingEndpoint
from .oslog import ASCOSLogEndpoint
from .base import ASCBaseEndpoint, ASCTimeout
from ...hw.asc import ASC

__all__ = []

class ASCDummyEndpoint(ASCBaseEndpoint):
    SHORT = "dummy"

class StandardASC(ASC):
    ENDPOINTS = {
        0: ASCManagementEndpoint,
        1: ASCCrashLogEndpoint,
        2: ASCSysLogEndpoint,
        3: ASCKDebugEndpoint,
        4: ASCIOReportingEndpoint,
        8: ASCOSLogEndpoint,
        0xa: ASCDummyEndpoint, # tracekit
    }

    def __init__(self, u, asc_base, dart=None, stream=0):
        super().__init__(u, asc_base)
        self.remote_eps = set()
        self.add_ep(0, ASCManagementEndpoint(self, 0))
        self.dart = dart
        self.stream = stream
        self.eps = []
        self.epcls = {}
        self.dva_offset = 0
        self.dva_size = 1 << 32
        self.allow_phys = False

        for cls in type(self).mro():
            eps = getattr(cls, "ENDPOINTS", None)
            if eps is None:
                break
            for k, v in eps.items():
                if k not in self.epcls:
                    self.epcls[k] = v

    def addr(self, addr):
        return f"{addr:#x}"

    def iomap(self, addr, size):
        if self.dart is None:
            return addr
        dva = self.dva_offset | self.dart.iomap(self.stream, addr, size)

        self.dart.invalidate_streams(1)
        return dva

    def ioalloc(self, size):
        paddr = self.u.memalign(0x4000, size)
        dva = self.iomap(paddr, size)
        return paddr, dva

    def ioread(self, dva, size):
        if self.allow_phys and dva < self.dva_offset or dva >= (self.dva_offset + self.dva_size):
            return self.iface.readmem(dva, size)

        if self.dart:
            return self.dart.ioread(self.stream, dva & 0xFFFFFFFF, size)
        else:
            return self.iface.readmem(dva, size)

    def iowrite(self, dva, data):
        if self.allow_phys and dva < self.dva_offset or dva >= (self.dva_offset + self.dva_size):
            return self.iface.writemem(dva, data)

        if self.dart:
            return self.dart.iowrite(self.stream, dva & 0xFFFFFFFF, data)
        else:
            return self.iface.writemem(dva, data)

    def iotranslate(self, dva, size):
        if self.allow_phys and dva < self.dva_offset or dva >= (self.dva_offset + self.dva_size):
            return [(dva, size)]

        if self.dart:
            return self.dart.iotranslate(self.stream, dva & 0xFFFFFFFF, size)
        else:
            return [(dva, size)]

    def start_ep(self, epno):
        if epno not in self.epcls:
            raise Exception(f"Unknown endpoint {epno:#x}")

        epcls = self.epcls[epno]
        ep = epcls(self, epno)
        self.add_ep(epno, ep)
        print(f"Starting endpoint #{epno:#x} ({ep.name})")
        self.mgmt.start_ep(epno)
        ep.start()

    def start(self):
        super().boot()
        self.mgmt.start()
        self.mgmt.wait_boot(3)

    def stop(self, state=0x10):
        for ep in list(self.epmap.values())[::-1]:
            if ep.epnum < 0x10:
                continue
            ep.stop()
        self.mgmt.stop(state=state)
        self.epmap = {}
        self.add_ep(0, ASCManagementEndpoint(self, 0))
        if state < 0x10:
            self.shutdown()

    def boot(self):
        print("Booting ASC...")
        super().boot()
        self.mgmt.wait_boot(1)

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)

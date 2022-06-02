# SPDX-License-Identifier: MIT
import bisect

from .object import GPUObject, GPUAllocator
from .initdata import build_initdata
from .channels import *
from ..malloc import Heap
from ..hw.uat import UAT, MemoryAttr
from ..fw.agx import AGXASC

class AGX:
    PAGE_SIZE = 0x4000

    def __init__(self, u):
        self.u = u
        self.iface = u.iface

        self.asc_dev = u.adt["/arm-io/gfx-asc"]
        self.sgx_dev = u.adt["/arm-io/sgx"]

        self.log("Initializing allocations")

        self.all_objects = []

        # Memory areas
        self.fw_va_base = self.sgx_dev.rtkit_private_vm_region_base
        self.fw_va_size = self.sgx_dev.rtkit_private_vm_region_size
        self.kern_va_base = self.fw_va_base + self.fw_va_size

        # Set up UAT
        self.uat = UAT(self.u.iface, self.u)
        self.uat.early_init()

        # Allocator for RTKit/ASC objects
        self.uat.allocator = Heap(self.kern_va_base + 0x80000000,
                                  self.kern_va_base + 0x81000000,
                                  self.PAGE_SIZE)

        self.asc = AGXASC(self.u, self.asc_dev.get_reg(0)[0], self, self.uat)
        self.asc.verbose = 0
        self.asc.mgmt.verbose = 0

        self.kobj = GPUAllocator(self, "kernel",
                                 self.kern_va_base, 0x10000000,
                                 AttrIndex=MemoryAttr.Normal, AP=1)
        self.cmdbuf = GPUAllocator(self, "cmdbuf",
                                   self.kern_va_base + 0x10000000, 0x10000000,
                                   AttrIndex=MemoryAttr.Normal, AP=0)
        self.kshared = GPUAllocator(self, "kshared",
                                    self.kern_va_base + 0x20000000, 0x10000000,
                                    AttrIndex=MemoryAttr.Shared, AP=1)
        self.kshared2 = GPUAllocator(self, "kshared2",
                                     self.kern_va_base + 0x30000000, 0x10000,
                                     AttrIndex=MemoryAttr.Shared, AP=0, PXN=1)

        self.io_allocator = Heap(self.kern_va_base + 0x38000000,
                                 self.kern_va_base + 0x40000000,
                                 block=self.PAGE_SIZE)

        self.mon = None

    def find_object(self, addr):
        self.all_objects.sort()

        idx = bisect.bisect_left(self.all_objects, (addr + 1, "")) - 1
        if idx < 0 or idx >= len(self.all_objects):
            return None, None

        return self.all_objects[idx]

    def reg_object(self, obj):
        self.all_objects.append((obj._addr, obj))
        if self.mon is not None:
            obj.add_to_mon(self.mon)

    def boot(self):
        # boot asc
        super().boot()

        initdata_addr = self.build_initdata()
        self.agx.send_initdata(self.initdata_addr)

    def start(self):
        self.asc.start()

        self.initdata = build_initdata(self)

    def stop(self):
        self.asc.stop()

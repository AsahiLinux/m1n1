# SPDX-License-Identifier: MIT

from .object import GPUObject, GPUAllocator
from .initdata import build_initdata
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

        # Memory areas
        self.fw_va_base = self.sgx_dev.rtkit_private_vm_region_base
        self.fw_va_size = self.sgx_dev.rtkit_private_vm_region_size
        self.kern_va_base = self.fw_va_base + self.fw_va_size
        self.ttbr_base = self.sgx_dev.gpu_region_base
        self.ttbr0_base = u.memalign(self.PAGE_SIZE, self.PAGE_SIZE)
        self.ttbr1_base = self.sgx_dev.gfx_shared_region_base

        # Set up UAT
        self.uat = UAT(self.u.iface, self.u)
        # Allocator for RTKit/ASC objects
        self.uat.allocator = Heap(self.kern_va_base + 0x80000000,
                                  self.kern_va_base + 0x81000000,
                                  self.PAGE_SIZE)
        self.uat.set_ttbr(self.ttbr_base)
        self.uat.set_l0(0, 0, self.ttbr0_base)
        self.uat.set_l0(0, 1, self.ttbr1_base)
        self.uat.flush_dirty()

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
                                     AttrIndex=MemoryAttr.Shared, AP=0)

        self.io_allocator = Heap(self.kern_va_base + 0x38000000,
                                 self.kern_va_base + 0x40000000,
                                 block=self.PAGE_SIZE)

    def boot(self):
        # boot asc
        super().boot()

        initdata_addr = self.build_initdata()
        self.agx.send_initdata(self.initdata_addr)

    def start(self):
        self.asc.boot_or_start()

        self.initdata = build_initdata(self)

    def stop(self):
        self.asc.stop()

# SPDX-License-Identifier: MIT
from ...utils import *
from ...malloc import Heap

from ..asc import StandardASC
from ..asc.base import ASCBaseEndpoint, msg_handler

from ...hw.uat import UAT

from .initdata import InitData, IOMapping


class PongMsg(Register64):
    TYPE    = 59, 52
    UNK     = 47, 0

class GpuMsg(Register64):
    TYPE    = 55, 48

class KickMsg(GpuMsg):
    TYPE    = 55, 48, Constant(0x83)
    KICK    = 15, 0


class AgxEP(ASCBaseEndpoint):
    BASE_MESSAGE = PongMsg
    SHORT = "agx"

    def send_initdata(initdata):
        pass

    @msg_handler(0x1)
    def pong(self, msg):
        print("received pong")


class KickEP(ASCBaseEndpoint):
    BASE_MESSAGE = KickMsg
    SHORT = "kick"

    def kick(self, kick_type):
        msg = KickMsg(KICK = kick_type)
        print(msg)
        self.send(msg)

class Agx(StandardASC):
    ENDPOINTS = {
        0x20: AgxEP,
        0x21: KickEP
    }

    def __init__(self, u):
        self.asc_dev = u.adt["/arm-io/gfx-asc"]
        self.sgx_dev = u.adt["/arm-io/sgx"]
        super().__init__(u, self.asc_dev.get_reg(0)[0])

        # Setup UAT
        self.uat = UAT(self.u.iface, self.u)
        kernel_base_va = getattr(self.sgx_dev, 'rtkit-private-vm-region-base')
        kernel_base_va += getattr(self.sgx_dev, 'rtkit-private-vm-region-size')
        ttbr_base = getattr(self.sgx_dev, 'gpu-region-base')
        ttbr1_addr = getattr(self.sgx_dev, 'gfx-shared-region-base')
        self.uat.initilize(ttbr_base, ttbr1_addr, kernel_base_va)

        # create some heaps
        shared_size = 2 * 1024 * 1024
        shared_paddr, shared_dva = self.ioalloc(shared_size, ctx=0)
        self.sharedHeap = Heap(shared_dva, shared_dva + shared_size)

        print("shared heap:", hex(shared_dva), hex(shared_size))

        normal_size = 2 * 1024 * 1024
        normal_paddr, normal_dva = self.ioalloc(shared_size, ctx=0)
        self.normalHeap = Heap(normal_dva, normal_dva + normal_size)

        print("normal heap:", hex(normal_dva), hex(normal_size))

        self.initdata = None


    def iomap(self, addr, size, ctx=0):
        dva = self.uat.iomap(ctx, addr, size)
        self.uat.iomap_at(ctx, dva, addr, size)

        return dva

    def ioalloc(self, size, ctx=0):
        paddr = self.u.memalign(0x4000, size)
        dva = self.iomap(paddr, size, ctx)
        return paddr, dva

    def ioread(self, dva, size, ctx=0):
        return self.uat.ioread(ctx, dva & 0xFFFFFFFFFF, size)

    def iowrite(self, dva, data, ctx=0):
        return self.uat.iowrite(ctx, dva & 0xFFFFFFFFFF, data)

    def build_initdata(self):
        if self.initdata is None:
            self.initdata_addr = self.normalHeap.malloc(InitData.sizeof())

            io_mappings = [IOMapping() for _ in range(0x14)]

            self.initdata = InitData(self.normalHeap, self.sharedHeap, {"io_mappings": io_mappings})
            self.initdata.build_stream(stream = self.uat.iostream(0, self.initdata_addr))

        return self.initdata_addr

    def boot(self):
        # boot asc
        super().boot()

        initdata_addr = self.build_initdata()
        self.agx.send_initdata(self.initdata_addr)

# SPDX-License-Identifier: MIT
from ...utils import *

from ..asc import StandardASC
from ..asc.base import ASCBaseEndpoint, msg_handler

from ...hw.uat import UAT


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

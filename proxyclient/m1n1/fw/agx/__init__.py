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
    SHORT = "pong"

    @msg_handler(0x1)
    def pong(self, msg):
        print("received pong")

    def send_initdata(self, addr):
        msg = PongMsg(TYPE=0x81, UNK=addr)
        print(msg)
        self.send(msg)

class KickEP(ASCBaseEndpoint):
    BASE_MESSAGE = KickMsg
    SHORT = "kick"

    def kick(self, kick_type):
        msg = KickMsg(KICK = kick_type)
        print(msg)
        self.send(msg)

class AGXASC(StandardASC):
    ENDPOINTS = {
        0x20: AgxEP,
        0x21: KickEP
    }

    def __init__(self, u, base, agx, uat):
        super().__init__(u, base)
        self.agx = agx
        self.uat = uat

    def iomap(self, addr, size):
        return self.uat.iomap(0, addr, size)

    def ioalloc(self, size):
        paddr = self.u.memalign(0x4000, size)
        dva = self.iomap(paddr, size)
        return paddr, dva

    def ioread(self, dva, size, ctx=0):
        return self.uat.ioread(ctx, dva & 0xFFFFFFFFFF, size)

    def iowrite(self, dva, data, ctx=0):
        return self.uat.iowrite(ctx, dva & 0xFFFFFFFFFF, data)

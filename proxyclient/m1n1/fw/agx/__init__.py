# SPDX-License-Identifier: MIT
from ...utils import *
from ...malloc import Heap

from ..asc import StandardASC
from ..asc.base import ASCBaseEndpoint, msg_handler

from .initdata import InitData, IOMapping

__all__ = []

class GpuMsg(Register64):
    TYPE    = 63, 48

class InitMsg(GpuMsg):
    TYPE        = 63, 48, Constant(0x81)
    UNK         = 47, 44, Constant(0)
    INITDATA    = 43, 0

class EventMsg(GpuMsg):
    TYPE        = 63, 48, Constant(0x42)
    UNK         = 47, 0, Constant(0)

class DoorbellMsg(GpuMsg):
    TYPE        = 63, 48, Constant(0x83)
    CHANNEL     = 15, 0

class FWCtlMsg(GpuMsg):
    TYPE        = 63, 48, Constant(0x84)

class HaltMsg(GpuMsg):
    TYPE        = 63, 48, Constant(0x85)

class FirmwareEP(ASCBaseEndpoint):
    BASE_MESSAGE = GpuMsg
    SHORT = "fw"

    @msg_handler(0x42)
    def event(self, msg):
        #self.log("Received event")
        self.asc.agx.poll_channels()
        return True

    def send_initdata(self, addr):
        self.log(f"Sending initdata @ {addr:#x}")
        msg = InitMsg(INITDATA=addr)
        self.send(msg)

class DoorbellEP(ASCBaseEndpoint):
    BASE_MESSAGE = DoorbellMsg
    SHORT = "db"

    def doorbell(self, channel):
        #self.log(f"Sending doorbell ch={channel}")
        msg = DoorbellMsg(CHANNEL = channel)
        self.send(msg)

    def fwctl_doorbell(self):
        msg = FWCtlMsg()
        self.send(msg)

class AGXASC(StandardASC):
    ENDPOINTS = {
        0x20: FirmwareEP,
        0x21: DoorbellEP,
    }

    def __init__(self, u, base, agx, uat):
        super().__init__(u, base)
        self.agx = agx
        self.uat = uat

    def addr(self, addr):
        base, obj = self.agx.find_object(addr)
        if base is None:
            return super().addr(addr)

        return f"{addr:#x} ({obj._name} [{obj._size:#x}] @ {base:#x} + {addr - base:#x})"

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

    def iotranslate(self, dva, size, ctx=0):
        return self.uat.iotranslate(ctx, dva & 0xFFFFFFFFFF, size)

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)

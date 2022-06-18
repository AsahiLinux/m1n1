# SPDX-License-Identifier: MIT
import bisect

from .object import GPUObject, GPUAllocator
from .initdata import build_initdata
from .channels import *
from ..malloc import Heap
from ..hw.uat import UAT, MemoryAttr
from ..fw.agx import AGXASC
from ..fw.agx.channels import ChannelInfoSet, ChannelInfo

class AGXChannels:
    pass

class AGXQueue:
    pass

class AGX:
    PAGE_SIZE = 0x4000

    def __init__(self, u):
        self.u = u
        self.p = u.proxy

        self.iface = u.iface

        self.asc_dev = u.adt["/arm-io/gfx-asc"]
        self.sgx_dev = u.adt["/arm-io/sgx"]

        self.log("Initializing allocations")

        self.all_objects = {}

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
        all_objects = list(self.all_objects.items())
        all_objects.sort()

        idx = bisect.bisect_left(all_objects, (addr + 1, "")) - 1
        if idx < 0 or idx >= len(all_objects):
            return None, None

        return all_objects[idx]

    def reg_object(self, obj, track=True):
        self.all_objects[obj._addr] = obj
        if track and self.mon is not None:
            obj.add_to_mon(self.mon)

    def unreg_object(self, obj):
        del self.all_objects[obj._addr]

    def alloc_channels(self, cls, name, channel_id, count=1, rx=False):

        # All channels have 0x100 items
        item_count = 0x100
        item_size = cls.item_size
        ring_size = item_count * item_size

        self.log(f"Allocating {count} channel(s) for {name} ({item_count} * {item_size:#x} bytes each)")

        state_obj = self.kshared.new_buf(0x30 * count, f"Channel.{name}.state")
        if rx:
            ring_buf = self.kshared.new_buf(ring_size * count, f"Channel.{name}.ring")
        else:
            ring_buf = self.kobj.new_buf(ring_size * count, f"Channel.{name}.ring")

        info = ChannelInfo()
        info.state_addr = state_obj._addr
        info.ringbuffer_addr = ring_buf._addr
        setattr(self.ch_info, name, info)

        return [cls(self, name + ("" if count == 1 else f"[{i}]"), channel_id,
                    state_obj._paddr + 0x30 * i,
                    ring_buf._paddr + ring_size * i, item_count)
                for i in range(count)]

    def init_channels(self):
        self.log("Initializing channels...")
        self.ch_info = ChannelInfoSet()
        self.ch = AGXChannels()
        self.ch.queue = []

        # Command queue submission channels
        for index in range(4):
            queue = AGXQueue()
            self.ch.queue.append(queue)
            for typeid, chtype in enumerate(("TA", "3D", "CL")):
                name = f"{chtype}_{index}"
                chan = self.alloc_channels(GPUCmdQueueChannel, name,
                                           (index << 2) | typeid)[0]
                setattr(queue, "q_" + chtype, chan)

        # Device control channel
        self.ch.devctrl = self.alloc_channels(GPUDeviceControlChannel, "DevCtrl", 0x11)[0]

        # GPU -> CPU channels
        self.ch.event = self.alloc_channels(GPUEventChannel, "Event", None)[0]
        self.ch.log = self.alloc_channels(GPULogChannel, "FWLog", None, 6)
        self.ch.ktrace = self.alloc_channels(GPUKTraceChannel, "KTrace", None)[0]
        self.ch.stats = self.alloc_channels(GPUStatsChannel, "Stats", None)[0]

        # For some reason, the FWLog channels have their rings in a different place...
        self.fwlog_ring = self.ch_info.FWLog.ringbuffer_addr
        self.ch_info.FWLog.ringbuffer_addr = self.kshared.buf(0x150000, "FWLog_Dummy")

    def poll_channels(self):
        self.ch.event.poll()
        for chan in self.ch.log:
            chan.poll()
        self.ch.ktrace.poll()
        self.ch.stats.poll()

    def kick_firmware(self):
        self.asc.db.doorbell(0x10)

    def start(self):
        self.log("Starting ASC")
        self.asc.start()

        self.log("Starting endpoints")
        self.asc.start_ep(0x20)
        self.asc.start_ep(0x21)

        self.init_channels()

        self.log("Building initdata")
        self.initdata = build_initdata(self)
        self.uat.flush_dirty()

        self.log("Sending initdata")
        self.asc.fw.send_initdata(self.initdata._addr & 0xfff_ffffffff)
        self.asc.work()

        self.log("Sending DC19")
        self.ch.devctrl.send_dc19()
        self.asc.work()

        for i in range(4):
            self.log("Sending DC23")
            self.ch.devctrl.send_dc23()
            self.asc.work()

    def stop(self):
        self.asc.stop()

    def work(self):
        self.asc.work()

    def log(self, msg):
       print("[AGX] " + msg)

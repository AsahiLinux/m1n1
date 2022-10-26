# SPDX-License-Identifier: MIT
import bisect, time

from .object import GPUObject, GPUAllocator
from .initdata import build_initdata
from .channels import *
from .event import GPUEventManager
from ..proxy import IODEV
from ..malloc import Heap
from ..hw.uat import UAT, MemoryAttr
from ..hw.agx import *
from ..fw.agx import AGXASC
from ..fw.agx.channels import ChannelInfoSet, ChannelInfo

class AGXChannels:
    pass

class AGXQueue:
    pass

class AGX:
    PAGE_SIZE = 0x4000
    MAX_EVENTS = 128

    def __init__(self, u):
        self.start_time = time.time()
        self.u = u
        self.p = u.proxy

        self.iface = u.iface
        self.show_stats = False

        self.asc_dev = u.adt["/arm-io/gfx-asc"]
        self.sgx_dev = u.adt["/arm-io/sgx"]
        self.sgx = SGXRegs(u, self.sgx_dev.get_reg(0)[0])

        self.log("Initializing allocations")

        self.aic_base = u.adt["/arm-io/aic"].get_reg(0)[0]

        self.all_objects = {}
        self.tracked_objects = {}

        # Memory areas
        self.fw_va_base = self.sgx_dev.rtkit_private_vm_region_base
        self.fw_va_size = self.sgx_dev.rtkit_private_vm_region_size
        self.kern_va_base = self.fw_va_base + self.fw_va_size

        # Set up UAT
        self.uat = UAT(self.u.iface, self.u)

        # Allocator for RTKit/ASC objects
        self.uat.allocator = Heap(self.kern_va_base + 0x80000000,
                                  self.kern_va_base + 0x81000000,
                                  self.PAGE_SIZE)

        self.asc = AGXASC(self.u, self.asc_dev.get_reg(0)[0], self, self.uat)
        self.asc.verbose = 0
        self.asc.mgmt.verbose = 0

        self.kobj = GPUAllocator(self, "kernel",
                                 self.kern_va_base, 0x10000000,
                                 AttrIndex=MemoryAttr.Shared, AP=1, guard_pages=4)
        self.cmdbuf = GPUAllocator(self, "cmdbuf",
                                   self.kern_va_base + 0x10000000, 0x10000000,
                                   AttrIndex=MemoryAttr.Shared, AP=0, guard_pages=4)
        self.kshared = GPUAllocator(self, "kshared",
                                    self.kern_va_base + 0x20000000, 0x10000000,
                                    AttrIndex=MemoryAttr.Shared, AP=1, guard_pages=4)
        self.kshared2 = GPUAllocator(self, "kshared2",
                                     self.kern_va_base + 0x30000000, 0x100000,
                                     AttrIndex=MemoryAttr.Shared, AP=0, PXN=1, guard_pages=4)

        self.io_allocator = Heap(self.kern_va_base + 0x38000000,
                                 self.kern_va_base + 0x40000000,
                                 block=self.PAGE_SIZE)

        self.mon = None
        self.event_mgr = GPUEventManager(self)

        self.p.iodev_set_usage(IODEV.FB, 0)

        self.initdata_hook = None

        # Early init, needed?
        self.poke_sgx()

    def poke_sgx(self):
        self.sgx_base = self.sgx_dev.get_reg(0)[0]
        self.p.read32(self.sgx_base + 0xd14000)
        self.p.write32(self.sgx_base + 0xd14000, 0x70001)

    def find_object(self, addr, ctx=0):
        all_objects = list(self.all_objects.items())
        all_objects.sort()

        idx = bisect.bisect_left(all_objects, ((ctx, addr + 1), "")) - 1
        if idx < 0 or idx >= len(all_objects):
            return None, None

        (ctx, base), obj = all_objects[idx]
        return base, obj

    def reg_object(self, obj, track=True):
        self.all_objects[(obj._ctx, obj._addr)] = obj
        if track:
            if self.mon is not None:
                obj.add_to_mon(self.mon)
            self.tracked_objects[(obj._ctx, obj._addr)] = obj

    def unreg_object(self, obj):
        del self.all_objects[(obj._ctx, obj._addr)]
        if obj._addr in self.tracked_objects:
            del self.tracked_objects[(obj._ctx, obj._addr)]

    def poll_objects(self):
        for obj in self.tracked_objects.values():
            diff = obj.poll()
            if diff is not None:
                self.log(diff)

    def alloc_channels(self, cls, name, channel_id, count=1, ring_size=0x100, rx=False):

        # All channels have 0x100 items
        item_count = ring_size
        item_size = cls.item_size
        ring_size = item_count * item_size

        self.log(f"Allocating {count} channel(s) for {name} ({item_count} * {item_size:#x} bytes each)")

        state_obj = self.kshared.new_buf(0x30 * count, f"Channel.{name}.state", track=False)
        if rx:
            ring_buf = self.kshared.new_buf(ring_size * count, f"Channel.{name}.ring", track=False)
        else:
            ring_buf = self.kobj.new_buf(ring_size * count, f"Channel.{name}.ring", track=False)

        info = ChannelInfo()
        info.state_addr = state_obj._addr
        info.ringbuffer_addr = ring_buf._addr
        if name == "FWCtl":
            self.fwctl_chinfo = info
        else:
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
        self.ch.event = self.alloc_channels(GPUEventChannel, "Event", None, rx=True)[0]
        self.ch.log = self.alloc_channels(GPULogChannel, "FWLog", None, 6, rx=True)
        self.ch.ktrace = self.alloc_channels(GPUKTraceChannel, "KTrace", None, ring_size=0x200, rx=True)[0]
        self.ch.stats = self.alloc_channels(GPUStatsChannel, "Stats", None, rx=True)[0]

        self.ch.fwctl = self.alloc_channels(GPUFWCtlChannel, "FWCtl", None, rx=False)[0]

        # For some reason, the FWLog channels have their rings in a different place...
        self.fwlog_ring = self.ch_info.FWLog.ringbuffer_addr
        self.ch_info.FWLog.ringbuffer_addr = self.kshared.buf(0x150000, "FWLog_Dummy")

    def poll_channels(self):
        for chan in self.ch.log:
            chan.poll()
        self.ch.ktrace.poll()
        if self.show_stats:
            self.ch.stats.poll()
        self.ch.event.poll()

    def kick_firmware(self):
        self.asc.db.doorbell(0x10)

    def show_irqs(self):
        hw_state = self.aic_base + 0x4200
        irqs = []
        for irq in self.sgx_dev.interrupts:
            v = int(bool((self.p.read32(hw_state + (irq // 32) * 4) & (1 << (irq % 32)))))
            irqs.append(v)
        self.log(f' SGX IRQ state: {irqs}')

    def timeout(self, msg):
        if self.mon:
            self.mon.poll()
        self.poll_objects()
        self.log(msg)
        self.log(r' (\________/) ')
        self.log(r'  |        |  ')
        self.log(r"'.| \  , / |.'")
        self.log(r'--| / (( \ |--')
        self.log(r".'|  _-_-  |'.")
        self.log(r'  |________|  ')
        self.log(r'')
        self.log(r' Timeout nya~!!!!!')
        self.log(r'')
        self.log(f' Stamp index: {int(msg.stamp_index)}')
        self.show_pending_stamps()
        self.log(f' Fault info:')
        self.log(self.initdata.regionC.fault_info)

        self.show_irqs()
        self.check_fault()
        self.recover()

    def faulted(self, msg):
        if self.mon:
            self.mon.poll()
        self.poll_objects()
        self.log(msg)
        self.log(r' (\________/) ')
        self.log(r'  |        |  ')
        self.log(r"'.| \  , / |.'")
        self.log(r'--| / (( \ |--')
        self.log(r".'|  _-_-  |'.")
        self.log(r'  |________|  ')
        self.log(r'')
        self.log(r' Fault nya~!!!!!')
        self.log(r'')
        self.show_pending_stamps()
        self.log(f' Fault info:')
        self.log(self.initdata.regionC.fault_info)

        self.show_irqs()
        self.check_fault()
        self.recover()

    def show_pending_stamps(self):
        self.initdata.regionC.pull()
        self.log(f' Pending stamps:')
        for i in self.initdata.regionC.pending_stamps:
            if i.info or i.wait_value:
                self.log(f"  - #{i.info >> 3:3d}: {i.info & 0x7}/{i.wait_value:#x}")
            i.info = 0
            i.wait_value = 0
            tmp = i.regmap()
            tmp.info.val = 0
            tmp.wait_value.val = 0

        #self.initdata.regionC.push()

    def check_fault(self):
        fault_info = self.sgx.FAULT_INFO.reg
        if fault_info.value == 0xacce5515abad1dea:
            raise Exception("Got fault notification, but fault address is unreadable")

        self.log(f" Fault info: {fault_info}")

        if not fault_info.FAULTED:
            return

        fault_addr = fault_info.ADDR
        if fault_addr & 0x8000000000:
            fault_addr |= 0xffffff8000000000
        base, obj = self.find_object(fault_addr)
        info = ""
        if obj is not None:
            info = f" ({obj!s} + {fault_addr - base:#x})"
        self.log(f" GPU fault at {fault_addr:#x}{info}")
        self.log(f" Faulting unit: {agx_decode_unit(fault_info.UNIT)}")

    def recover(self):
        status = self.fw_status
        self.log(f" Halt count: {status.halt_count.val}")
        halted = bool(status.halted.val)
        self.log(f" Halted: {halted}")
        if halted:
            self.log(f" Attempting recovery...")
            status.halted.val = 0
            status.resume.val = 1
        else:
            raise Exception("Cannot recover")
        self.show_irqs()

    def resume(self):
        self.log("Starting ASC")
        self.asc.start()

        self.log("Starting endpoints")
        self.asc.start_ep(0x20)
        self.asc.start_ep(0x21)

    def start(self):
        self.resume()

        self.init_channels()

        self.log("Building initdata")
        self.initdata = build_initdata(self)
        if self.initdata_hook:
            self.initdata_hook(self)

        self.fw_status = self.initdata.fw_status.regmap()
        self.uat.flush_dirty()

        self.log("Sending initdata")
        self.asc.fw.send_initdata(self.initdata._addr & 0xfff_ffffffff)
        self.asc.work()

        self.log("Sending DC_Init")
        self.ch.devctrl.send_init()
        self.asc.work()

        self.log("Sending DC_UpdateIdleTS")
        self.ch.devctrl.update_idle_ts()
        self.asc.work()

    def stop(self):
        self.asc.stop()

    def work(self):
        self.asc.work()

    def wait_for_events(self, timeout=1.0):
        now = time.time()
        deadline = now + timeout
        cnt = self.event_mgr.event_count
        while now < deadline and self.event_mgr.event_count == cnt:
            self.asc.work()
            now = time.time()
        if self.event_mgr.event_count == cnt:
            raise Exception("Timed out waiting for events")

    def log(self, msg):
        t = time.time() - self.start_time
        print(f"[AGX][{t:10.03f}] " + str(msg))

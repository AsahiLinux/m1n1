# SPDX-License-Identifier: MIT

import textwrap
from .asc import *
from ..hw.uat import UAT, MemoryAttr, PTE, Page_PTE

from ..fw.agx.initdata import InitData as NewInitData
from ..fw.agx.channels import *

from m1n1.proxyutils import RegMonitor
from m1n1.constructutils import *

from construct import *

class ChannelTraceState(object):
    pass

class GpuMsg(Register64):
    TYPE    = 55, 48

class PongMsg(GpuMsg):
    TYPE    = 59, 52
    UNK     = 47, 0

class PongEp(EP):
    # This endpoint recives pongs. The cpu code reads some status registers after receiving one
    # Might be a "work done" message.
    BASE_MESSAGE = GpuMsg

    @msg(0x42, DIR.RX, PongMsg)
    def pong_rx(self, msg):
        self.log(f"  Pong {msg!s}")
        if msg.UNK != 0:
            self.log(f"  Pong had unexpected value{msg.UNK:x}")
            self.hv.run_shell()

        self.tracer.pong()
        return True

    @msg(0x81, DIR.TX, PongMsg)
    def init_ep(self, msg):
        self.log(f"  Init {msg.UNK:x}")

        self.tracer.pong_init(msg.UNK)
        return True

class KickMsg(GpuMsg):
    TYPE    = 59, 52
    KICK    = 7, 0 # Seen: 17, 16 (common), 9, 8, 1 (common), 0 (common)

class KickEp(EP):
    BASE_MESSAGE = GpuMsg

    @msg(0x83, DIR.TX, KickMsg)
    def kick(self, msg):
        self.log(f"  Kick {msg.KICK:x}")
        self.tracer.kick(msg.KICK)

        return True

class ChannelTracer(Reloadable):
    def __init__(self, tracer, info, index):
        self.tracer = tracer
        self.uat = tracer.uat
        self.hv = tracer.hv
        self.u = self.hv.u
        self.ring_count = len(channelRings[index])

        if index not in tracer.state.channels:
            self.state = ChannelTraceState()
            self.state.tail = [0] * self.ring_count
            tracer.state.channels[index] = self.state
        else:
            self.state = tracer.state.channels[index]

        self.index = index
        self.name = channelNames[index]
        self.info = info
        base = None

        if self.name == "FWLog":
            base = self.tracer.state.fwlog_ring2

        self.channel = Channel(self.u, self.uat, self.info, channelRings[index], base=base)
        for addr, size in self.channel.st_maps:
            self.log(f"st_map {addr:#x} ({size:#x})")
        for i in range(self.ring_count):
            for addr, size in self.channel.rb_maps[i]:
                self.log(f"rb_map[{i}] {addr:#x} ({size:#x})")

        self.hv.add_tracer(irange(self.channel.state_phys, 0x30 * self.ring_count),
                           f"ChannelTracer/{self.name}",
                           mode=TraceMode.SYNC,
                           write=self.state_write,
                           read=self.state_read)

    def state_read(self, evt, regmap=None, prefix=None):
        off = evt.addr - self.channel.state_phys
        ring = off // 0x30
        off = off % 0x30

        msgcls, size, count = self.channel.ring_defs[ring]

        if off == 0x20:
            self.log(f"RD [{evt.addr:#x}] WPTR[{ring}] = {evt.data:#x}")
        elif off == 0x00:
            self.log(f"RD [{evt.addr:#x}] RPTR[{ring}] = {evt.data:#x}")
            self.poll_ring(ring)
        else:
            self.log(f"RD [{evt.addr:#x}] UNK[{ring}] {off:#x} = {evt.data:#x}")

    def state_write(self, evt, regmap=None, prefix=None):
        off = evt.addr - self.channel.state_phys
        ring = off // 0x30
        off = off % 0x30

        msgcls, size, count = self.channel.ring_defs[ring]

        if off == 0x20:
            self.log(f"WR [{evt.addr:#x}] WPTR[{ring}] = {evt.data:#x}")
        elif off == 0x00:
            self.log(f"WR [{evt.addr:#x}] RPTR[{ring}] = {evt.data:#x}")
            self.poll_ring(ring)
            # Clear message with test pattern
            idx = (evt.data - 1) % count
            self.channel.clear_message(ring, idx)
        else:
            self.log(f"WR [{evt.addr:#x}] UNK[{ring}] {off:#x} = {evt.data:#x}")

    def log(self, msg):
        self.tracer.log(f"[{self.index}:{self.name}] {msg}")

    def poll(self):
        for i in range(self.ring_count):
            self.poll_ring(i)

    def poll_ring(self, ring):
        msgcls, size, count = self.channel.ring_defs[ring]

        cur = self.state.tail[ring]
        tail = self.channel.state[ring].WRITE_PTR.val
        if cur != tail:
            #self.log(f"{cur:#x} -> {tail:#x}")
            while cur != tail:
                msg = self.channel.get_message(ring, cur)
                self.log(f"Message @{ring}.{cur}:\n{msg!s}")
                #if self.index < 12:
                    #self.hv.run_shell()
                cur = (cur + 1) % count
            self.state.tail[ring] = cur

ChannelTracer = ChannelTracer._reloadcls()

class AGXTracer(ASCTracer):
    ENDPOINTS = {
        0x20: PongEp,
        0x21: KickEp
    }

    PAGESIZE = 0x4000

    def __init__(self, hv, devpath, verbose=False):
        super().__init__(hv, devpath, verbose)
        self.channels = []
        self.uat = UAT(hv.iface, hv.u, hv)
        self.mon = RegMonitor(hv.u, ascii=True, log=hv.log)
        self.dev_sgx = hv.u.adt["/arm-io/sgx"]
        self.gpu_region = getattr(self.dev_sgx, "gpu-region-base")
        self.gpu_region_size = getattr(self.dev_sgx, "gpu-region-size")
        self.gfx_shared_region = getattr(self.dev_sgx, "gfx-shared-region-base")
        self.gfx_shared_region_size = getattr(self.dev_sgx, "gfx-shared-region-size")
        self.gfx_handoff = getattr(self.dev_sgx, "gfx-handoff-base")
        self.gfx_handoff_size = getattr(self.dev_sgx, "gfx-handoff-size")

        self.ignorelist = []
        self.last_msg = None

        # self.mon.add(self.gpu_region, self.gpu_region_size, "contexts")
        # self.mon.add(self.gfx_shared_region, self.gfx_shared_region_size, "gfx-shared")
        # self.mon.add(self.gfx_handoff, self.gfx_handoff_size, "gfx-handoff")

        self.uat.set_ttbr(self.gpu_region)

        self.hv.add_tracer(irange(self.gfx_shared_region, 0x4000),
                           f"UATMapTracer",
                           mode=TraceMode.WSYNC,
                           write=self.uat_write,
                           iova=0xf8000000000,
                           base=self.gfx_shared_region,
                           level=2)

    def uat_write(self, evt, level=3, base=0, iova=0):
        off = evt.addr - base
        iova += (off // 8) << (level * 11 + 14)
        #self.log(f"UAT write L{level} at {iova:#x} (#{off:#x}) -> {evt.data}")

        if level == 0:
            pte = Page_PTE(evt.data)
            self.uat_page_mapped(iova, pte)
            return

        level -= 1

        pte = PTE(evt.data)
        self.hv.add_tracer(irange(pte.offset(), 0x4000),
                           f"UATMapTracer",
                           mode=TraceMode.WSYNC,
                           write=self.uat_write,
                           iova=iova,
                           base=pte.offset(),
                           level=level)

    def uat_page_mapped(self, iova, pte):
        paddr = pte.offset()
        self.log(f"UAT map {iova:#x} -> {paddr:#x}")
        return

        self.hv.add_tracer(irange(paddr, 0x4000),
                           f"GPUVM",
                           mode=TraceMode.ASYNC,
                           read=self.event_gpuvm,
                           write=self.event_gpuvm,
                           iova=iova,
                           paddr=paddr)

    def event_gpuvm(self, evt, iova, paddr):
        off = evt.addr - paddr
        iova += off

        t = "W" if evt.flags.WRITE else "R"
        m = "+" if evt.flags.MULTI else " "
        logline = (f"GPUVM: {t}.{1<<evt.flags.WIDTH:<2}{m} " +
                   f"{iova:#x}({evt.addr:#x}) = {evt.data:#x}")
        self.log(logline)

    def start(self):
        super().start()
        self.init_channels()

    def mon_addva(self, ctx, va, size, name=""):
        self.mon.add(va, size, name, readfn= lambda a, s: self.uat.ioread(ctx, a, s))

    def print_ringmsg(self, channel):
        addr = self.initdata.regionB.channels[channel].ringbuffer_addr
        addr += self.channels_read_ptr[channel] * 0x30
        self.channels_read_ptr[channel] = (self.channels_read_ptr[channel] + 1) % 256
        msg = ChannelMessage.parse_stream(self.uat.iostream(0, addr))

        if isinstance(msg, NotifyCmdQueueWork) and (msg.cmdqueue_addr & 0xfff_ffffffff) in self.ignorelist:
            return

        self.log(f"Channel[{channelNames[channel]}]: {msg}")
        self.last_msg = msg

    def ignore(self, addr=None):
        if addr is None:
            addr = self.last_msg.cmdqueue_addr
        self.ignorelist += [addr & 0xfff_ffffffff]

    def kick(self, val):
        self.log(f"kick~! {val:#x}")
        self.mon.poll()

        if val == 0x10: # Kick Firmware
            self.log("KickFirmware")
            self.uat.invalidate_cache()
            for chan in self.channels[13:]:
                chan.poll()
            return

        if val == 0x11: # Device Control
            channel = 12
            self.uat.invalidate_cache()

        elif val < 0x10:
            type = val & 3
            assert type != 3
            priority = (val >> 2) & 3
            channel = type + priority * 3

        else:
            raise(Exception("Unknown kick type"))

        self.channels[channel].poll()

        ## if val not in [0x0, 0x1, 0x10, 0x11]:
        #if self.last_msg and isinstance(self.last_msg, (NotifyCmdQueueWork, DeviceControl_17)):
            #self.hv.run_shell()

            #self.last_msg = None

        # check the gfx -> cpu channels
        for chan in self.channels[13:]:
            chan.poll()

    def pong(self):
        self.log("pong~!");
        self.mon.poll()

        # check the gfx -> cpu channels
        for chan in self.channels[13:]:
            chan.poll()

    def trace_uatrange(self, ctx, start, size):
        ranges = self.uat.iotranslate(ctx, start, size)
        for range in ranges:
            start, size = range
            if start:
                self.hv.trace_range(irange(start, size), mode=TraceMode.SYNC)

    def dump_va(self, ctx):
        data = b''
        dataStart = 0

        def dump_page(start, end, i, pte, level, sparse):
            if i == 0 or sparse:
                if len(data):
                    chexdump32(data, dataStart)
                data = b''
                dataStart = 0
            if MemoryAttr(pte.AttrIndex) != MemoryAttr.Device and pte.OS:
                if dataStart == 0:
                    dataStart = start
                data += self.uat.ioread(0, start, 0x4000)

        self.uat.foreach_page(0, dump_page)
        if len(data):
            chexdump32(data, dataStart)

    def init_state(self):
        super().init_state()
        self.state.channel_info = []
        self.state.channels = {}

    def init_channels(self):
        if self.channels:
            return
        #self.channels = []
        for i, chan_info in enumerate(self.state.channel_info):
            if i == 16:
                continue
            channel_chan = ChannelTracer(self, chan_info, i)
            self.channels.append(channel_chan)
            for i, (msg, size, count) in enumerate(channel_chan.channel.ring_defs):
                self.mon_addva(0, chan_info.state_addr + i * 0x30, 0x30, f"chan[{channel_chan.name}]->state[{i}]")
                self.mon_addva(0, channel_chan.channel.rb_base[i], size * count, f"chan[{channel_chan.name}]->ringbuffer[{i}]")

    def pong_init(self, addr):
        self.log("UAT at init time:")
        self.uat.dump(0, log=self.log)

        self.initdata_addr = addr
        self.initdata = NewInitData.parse_stream(self.uat.iostream(0, addr))

        self.log("Initdata:")
        self.log(self.initdata)

        #self.mon_addva(0, self.initdata.regionB_addr, 0x34000, "initdata.RegionB")
        #self.mon_addva(0, self.initdata.regionC_addr, 0x88000, "initdata.RegionC")

        self.trace_uatrange(0, self.initdata.regionB_addr, 0x34000)
        self.trace_uatrange(0, self.initdata.regionC_addr, 0x8000)
        self.trace_uatrange(0, self.initdata.regionC_addr + 0xc000, 0x4000)

        self.initdata.regionB.mon(lambda addr, size, name: self.mon_addva(0, addr, size, name))

        self.state.initdata = self.initdata
        self.state.channel_info = []
        self.state.fwlog_ring2 = self.initdata.regionB.fwlog_ring2
        channels = self.initdata.regionB.channels
        for i in range(len(channels)):
            chan_info = channels[i]
            self.state.channel_info.append(chan_info)

        self.init_channels()
        self.mon.poll()

        self.log("Initial commands::")
        for chan in self.channels:
            chan.poll()
        self.log("Init done")

        self.log("Mon regions")
        self.mon.show_regions(log=self.log)

        #self.hv.run_shell()

ChannelTracer = ChannelTracer._reloadcls()

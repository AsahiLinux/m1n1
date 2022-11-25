# SPDX-License-Identifier: MIT

import textwrap
from .asc import *
from ..hw.uat import UAT, MemoryAttr, PTE, Page_PTE, TTBR
from ..hw.agx import *

from ..fw.agx.initdata import InitData
from ..fw.agx.channels import *
from ..fw.agx.cmdqueue import *
from ..fw.agx.microsequence import *
from ..fw.agx.handoff import *

from m1n1.proxyutils import RegMonitor
from m1n1.constructutils import *
from m1n1.trace import Tracer

from construct import *

class ChannelTraceState(object):
    pass

class CommandQueueState(object):
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
        if self.tracer.state.active:
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
        if self.tracer.state.active:
            self.log(f"  Kick {msg}")
        self.tracer.kick(msg.KICK)

        return True

    @msg(0x84, DIR.TX, KickMsg)
    def fwkick(self, msg):
        if self.tracer.state.active:
            self.log(f"  FWRing Kick {msg}")
        self.tracer.fwkick(msg.KICK)
        return True

class ChannelTracer(Reloadable):
    STATE_FIELDS = ChannelStateFields
    WPTR = 0x20
    RPTR = 0x00

    def __init__(self, tracer, info, index):
        self.tracer = tracer
        self.uat = tracer.uat
        self.hv = tracer.hv
        self.u = self.hv.u
        self.ring_count = len(channelRings[index])
        self.verbose = False

        if index not in tracer.state.channels:
            self.state = ChannelTraceState()
            self.state.active = True
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

        self.channel = Channel(self.u, self.uat, self.info, channelRings[index], base=base,
                               state_fields=self.STATE_FIELDS)
        for addr, size in self.channel.st_maps:
            self.log(f"st_map {addr:#x} ({size:#x})")
        for i in range(self.ring_count):
            for addr, size in self.channel.rb_maps[i]:
                self.log(f"rb_map[{i}] {addr:#x} ({size:#x})")

        self.set_active(self.state.active)

    def state_read(self, evt, regmap=None, prefix=None):
        off = evt.addr - self.channel.state_phys
        ring = off // 0x30
        off = off % 0x30

        msgcls, size, count = self.channel.ring_defs[ring]

        if off == self.WPTR:
            if self.verbose:
                self.log(f"RD [{evt.addr:#x}] WPTR[{ring}] = {evt.data:#x}")
            self.poll_ring(ring)
        elif off == self.RPTR:
            if self.verbose:
                self.log(f"RD [{evt.addr:#x}] RPTR[{ring}] = {evt.data:#x}")
            self.poll_ring(ring)
        else:
            if self.verbose:
                self.log(f"RD [{evt.addr:#x}] UNK[{ring}] {off:#x} = {evt.data:#x}")

    def state_write(self, evt, regmap=None, prefix=None):
        off = evt.addr - self.channel.state_phys
        ring = off // 0x30
        off = off % 0x30

        msgcls, size, count = self.channel.ring_defs[ring]

        if off == self.WPTR:
            if self.verbose:
                self.log(f"WR [{evt.addr:#x}] WPTR[{ring}] = {evt.data:#x}")
            self.poll_ring(ring)
        elif off == self.RPTR:
            if self.verbose:
                self.log(f"WR [{evt.addr:#x}] RPTR[{ring}] = {evt.data:#x}")
            self.poll_ring(ring)
            # Clear message with test pattern
            idx = (evt.data - 1) % count
            self.channel.clear_message(ring, idx)
        else:
            if self.verbose:
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
        if tail >= count:
            raise Exception(f"Message index {tail:#x} >= {count:#x}")
        if cur != tail:
            #self.log(f"{cur:#x} -> {tail:#x}")
            while cur != tail:
                msg = self.channel.get_message(ring, cur, self.tracer.meta_gpuvm)
                self.log(f"Message @{ring}.{cur}:\n{msg!s}")
                self.tracer.handle_ringmsg(msg)
                #if self.index < 12:
                    #self.hv.run_shell()
                cur = (cur + 1) % count
            self.state.tail[ring] = cur

    def set_active(self, active=True):
        if active:
            if not self.state.active:
                for ring in range(self.ring_count):
                    self.state.tail[ring] = self.channel.state[ring].WRITE_PTR.val

            for base in range(0, 0x30 * self.ring_count, 0x30):
                self.hv.add_tracer(irange(self.channel.state_phys + base + self.RPTR, 4),
                                   f"ChannelTracer/{self.name}",
                                   mode=TraceMode.SYNC,
                                   read=self.state_read,
                                   write=self.state_write)
                self.hv.add_tracer(irange(self.channel.state_phys + base + self.WPTR, 4),
                                   f"ChannelTracer/{self.name}",
                                   mode=TraceMode.SYNC,
                                   read=self.state_read,
                                   write=self.state_write)
        else:
            self.hv.clear_tracers(f"ChannelTracer/{self.name}")
        self.state.active = active

ChannelTracer = ChannelTracer._reloadcls()
CommandQueueInfo = CommandQueueInfo._reloadcls()

class FWCtlChannelTracer(ChannelTracer):
    STATE_FIELDS = FWControlStateFields
    WPTR = 0x10
    RPTR = 0x00

class CommandQueueTracer(Reloadable):
    def __init__(self, tracer, info_addr, new_queue):
        self.tracer = tracer
        self.uat = tracer.uat
        self.hv = tracer.hv
        self.u = self.hv.u
        self.verbose = False
        self.info_addr = info_addr

        if info_addr not in tracer.state.queues:
            self.state = CommandQueueState()
            self.state.rptr = None
            self.state.active = True
            tracer.state.queues[info_addr] = self.state
        else:
            self.state = tracer.state.queues[info_addr]

        if new_queue:
            self.state.rptr = 0

        self.update_info()

    def update_info(self):
        self.info = CommandQueueInfo.parse_stream(self.tracer.get_stream(0, self.info_addr))

    def log(self, msg):
        self.tracer.log(f"[CQ@{self.info_addr:#x}] {msg}")

    @property
    def rb_size(self):
        return self.info.pointers.rb_size

    def get_workitems(self, workmsg):
        self.tracer.uat.invalidate_cache()
        self.update_info()

        if self.state.rptr is None:
            self.state.rptr = int(self.info.pointers.gpu_doneptr)
            self.log(f"Initializing rptr to {self.info.gpu_rptr1:#x}")

        self.log(f"Got workmsg: wptr={workmsg.head:#x} rptr={self.state.rptr:#x}")
        self.log(f"Queue info: {self.info}")


        assert self.state.rptr < self.rb_size
        assert workmsg.head < self.rb_size

        stream = self.tracer.get_stream(0, self.info.rb_addr)

        count = 0
        orig_rptr = rptr = self.state.rptr
        while rptr != workmsg.head:
            count += 1
            stream.seek(self.info.rb_addr + rptr * 8, 0)
            pointer = Int64ul.parse_stream(stream)
            self.log(f"WI item @{rptr:#x}: {pointer:#x}")
            if pointer:
                stream.seek(pointer, 0)
                yield CmdBufWork.parse_stream(stream)
            rptr = (rptr + 1) % self.rb_size

        self.state.rptr = rptr

        self.log(f"Parsed {count} items from {orig_rptr:#x} to {workmsg.head:#x}")

    def set_active(self, active=True):
        if not active:
            self.state.rptr = None
        self.state.active = active

CmdBufWork = CmdBufWork._reloadcls()
CommandQueueTracer = CommandQueueTracer._reloadcls()
InitData = InitData._reloadcls(True)

class HandoffTracer(Tracer):
    DEFAULT_MODE = TraceMode.SYNC

    def __init__(self, hv, agx_tracer, base, verbose=False):
        super().__init__(hv, verbose=verbose)
        self.agx_tracer = agx_tracer
        self.base = base

    def start(self):
        self.trace_regmap(self.base, 0x4000, GFXHandoffStruct, name="regs")

class SGXTracer(ADTDevTracer):
    DEFAULT_MODE = TraceMode.HOOK

    REGMAPS = [SGXRegs, SGXInfoRegs]
    NAMES = ["sgx", "sgx-id"]

    def __init__(self, hv, devpath, verbose=False):
        super().__init__(hv, devpath, verbose=verbose)
        self.hooks = {}

    def hook_r(self, addr, width, **kwargs):
        self.log(f"HOOK: {addr:#x}:{width}")

        if addr in self.hooks:
            val = self.hooks[addr]
            self.log(f"  Returning: {val:#x}")
        else:
            xval = val = super().hook_r(addr, width, **kwargs)
            if isinstance(val, (list, tuple)):
                xval = list(map(hex, val))
            else:
                xval = hex(val)
            self.log(f"  Read: {xval}")

        return val

class AGXTracer(ASCTracer):
    ENDPOINTS = {
        0x20: PongEp,
        0x21: KickEp
    }

    REGMAPS = [ASCRegs]
    NAMES = ["asc"]

    PAGESIZE = 0x4000

    def __init__(self, hv, devpath, verbose=False):
        super().__init__(hv, devpath, verbose)
        self.channels = []
        self.uat = UAT(hv.iface, hv.u, hv)
        self.mon = RegMonitor(hv.u, ascii=True, log=hv.log)
        self.dev_sgx = hv.u.adt["/arm-io/sgx"]
        self.sgx = SGXRegs(hv.u, self.dev_sgx.get_reg(0)[0])
        self.gpu_region = getattr(self.dev_sgx, "gpu-region-base")
        self.gpu_region_size = getattr(self.dev_sgx, "gpu-region-size")
        self.gfx_shared_region = getattr(self.dev_sgx, "gfx-shared-region-base")
        self.gfx_shared_region_size = getattr(self.dev_sgx, "gfx-shared-region-size")
        self.gfx_handoff = getattr(self.dev_sgx, "gfx-handoff-base")
        self.gfx_handoff_size = getattr(self.dev_sgx, "gfx-handoff-size")

        self.handoff_tracer = HandoffTracer(hv, self, self.gfx_handoff, verbose=2)

        self.ignorelist = []
        self.last_msg = None

        # self.mon.add(self.gpu_region, self.gpu_region_size, "contexts")
        # self.mon.add(self.gfx_shared_region, self.gfx_shared_region_size, "gfx-shared")
        # self.mon.add(self.gfx_handoff, self.gfx_handoff_size, "gfx-handoff")

        self.trace_kernva = False
        self.trace_userva = False
        self.trace_kernmap = True
        self.trace_usermap = True
        self.pause_after_init = False
        self.shell_after_init = False
        self.after_init_hook = None
        self.encoder_id_filter = None
        self.redump = False

        self.vmcnt = 0
        self.readlog = {}
        self.writelog = {}
        self.cmdqueues = {}
        self.va_to_pa = {}

        self.last_ta = None
        self.last_3d = None


    def get_cmdqueue(self, info_addr, new_queue):
        if info_addr in self.cmdqueues and not new_queue:
            return self.cmdqueues[info_addr]

        cmdqueue = CommandQueueTracer(self, info_addr, new_queue)
        self.cmdqueues[info_addr] = cmdqueue

        return cmdqueue

    def clear_ttbr_tracers(self):
        self.hv.clear_tracers(f"UATTTBRTracer")

    def add_ttbr_tracers(self):
        self.hv.add_tracer(irange(self.gpu_region, UAT.NUM_CONTEXTS * 16),
                        f"UATTTBRTracer",
                        mode=TraceMode.WSYNC,
                        write=self.uat_write,
                        iova=0,
                        base=self.gpu_region,
                        level=3)

    def clear_uatmap_tracers(self, ctx=None):
        if ctx is None:
            for i in range(UAT.NUM_CONTEXTS):
                self.clear_uatmap_tracers(i)
        else:
            self.hv.clear_tracers(f"UATMapTracer/{ctx}")

    def add_uatmap_tracers(self, ctx=None):
        self.log(f"add_uatmap_tracers({ctx})")
        if ctx is None:
            if self.trace_kernmap:
                self.add_uatmap_tracers(0)
            if self.trace_usermap:
                for i in range(1, UAT.NUM_CONTEXTS):
                    self.add_uatmap_tracers(i)
            return

        if ctx != 0 and not self.trace_usermap:
            return
        if ctx == 0 and not self.trace_kernmap:
            return

        def trace_pt(start, end, idx, pte, level, sparse):
            if start >= 0xf8000000000 and (ctx != 0 or not self.trace_kernmap):
                return
            if start < 0xf8000000000 and not self.trace_usermap:
                return
            self.log(f"Add UATMapTracer/{ctx} {start:#x}")
            self.hv.add_tracer(irange(pte.offset(), 0x4000),
                            f"UATMapTracer/{ctx}",
                            mode=TraceMode.WSYNC,
                            write=self.uat_write,
                            iova=start,
                            base=pte.offset(),
                            level=2 - level,
                            ctx=ctx)

        self.uat.foreach_table(ctx, trace_pt)

    def clear_gpuvm_tracers(self, ctx=None):
        if ctx is None:
            for i in range(UAT.NUM_CONTEXTS):
                self.clear_gpuvm_tracers(i)
        else:
            self.hv.clear_tracers(f"GPUVM/{ctx}")

    def add_gpuvm_tracers(self, ctx=None):
        self.log(f"add_gpuvm_tracers({ctx})")
        if ctx is None:
            self.add_gpuvm_tracers(0)
            if self.trace_userva:
                for i in range(1, UAT.NUM_CONTEXTS):
                    self.add_gpuvm_tracers(i)
            return

        def trace_page(start, end, idx, pte, level, sparse):
            self.uat_page_mapped(start, pte, ctx)

        self.uat.foreach_page(ctx, trace_page)

    def uat_write(self, evt, level=3, base=0, iova=0, ctx=None):
        off = (evt.addr - base) // 8
        sh = ["NS", "??", "OS", "IS"]
        a = f"{evt.flags.ATTR:02x}:{sh[evt.flags.SH]}"
        self.log(f"UAT <{a}> write L{level} at {ctx}:{iova:#x} (#{off:#x}) -> {evt.data}")

        if level == 3:
            ctx = off // 2
            is_kernel = off & 1
            if ctx != 0 and is_kernel:
                return

            if is_kernel:
                iova += 0xf8000000000
            pte = TTBR(evt.data)
            if not pte.valid():
                self.log(f"Context {ctx} invalidated")
                self.uat.invalidate_cache()
                self.clear_uatmap_tracers(ctx)
                self.clear_gpuvm_tracers(ctx)
                return
            self.log(f"Dumping UAT for context {ctx}")
            self.uat.invalidate_cache()
            _, pt = self.uat.get_pt(self.uat.gpu_region + ctx * 16, 2)
            pt[off & 1] = evt.data
            self.uat.dump(ctx, log=self.log)
            self.add_uatmap_tracers(ctx)
            self.add_gpuvm_tracers(ctx)
        else:
            is_kernel = iova >= 0xf8000000000
            iova += off << (level * 11 + 14)
            if level == 0:
                pte = Page_PTE(evt.data)
                self.uat_page_mapped(iova, pte, ctx)
                return
            else:
                pte = PTE(evt.data)

        if not pte.valid():
            try:
                paddr = self.va_to_pa[(ctx, level, iova)]
            except KeyError:
                return
            self.hv.del_tracer(irange(paddr, 0x4000),
                               f"UATMapTracer/{ctx}")
            del self.va_to_pa[(ctx, level, iova)]
            return

        if ctx != 0 and not self.trace_usermap:
            return
        if ctx == 0 and not self.trace_kernmap:
            return

        self.va_to_pa[(ctx, level, iova)] = pte.offset()
        level -= 1
        self.hv.add_tracer(irange(pte.offset(), 0x4000),
                           f"UATMapTracer/{ctx}",
                           mode=TraceMode.WSYNC,
                           write=self.uat_write,
                           iova=iova,
                           base=pte.offset(),
                           level=level,
                           ctx=ctx)

    def uat_page_mapped(self, iova, pte, ctx=0):
        if iova >= 0xf8000000000 and ctx != 0:
            return
        if not pte.valid():
            self.log(f"UAT unmap {ctx}:{iova:#x} ({pte})")
            try:
                paddr = self.va_to_pa[(ctx, iova)]
            except KeyError:
                return
            self.hv.del_tracer(irange(paddr, 0x4000), f"GPUVM/{ctx}")
            del self.va_to_pa[(ctx, iova)]
            return

        paddr = pte.offset()
        self.log(f"UAT map {ctx}:{iova:#x} -> {paddr:#x} ({pte})")
        if paddr < 0x800000000:
            return # MMIO, ignore

        if not self.trace_userva and ctx != 0 and iova < 0x80_00000000:
            return
        if not self.trace_kernva and ctx == 0:
            return

        self.va_to_pa[(ctx, iova)] = paddr
        self.hv.add_tracer(irange(paddr, 0x4000),
                           f"GPUVM/{ctx}",
                           mode=TraceMode.ASYNC,
                           read=self.event_gpuvm,
                           write=self.event_gpuvm,
                           iova=iova,
                           paddr=paddr,
                           ctx=ctx)

    def event_gpuvm(self, evt, iova, paddr, name=None, base=None, ctx=None):
        off = evt.addr - paddr
        iova += off

        if evt.flags.WRITE:
            self.writelog[iova] = (self.vmcnt, evt)
        else:
            self.readlog[iova] = (self.vmcnt, evt)
        t = "W" if evt.flags.WRITE else "R"
        m = "+" if evt.flags.MULTI else " "
        sh = ["NS", "??", "OS", "IS"]
        a = f"{evt.flags.ATTR:02x}:{sh[evt.flags.SH]}"
        dinfo = ""
        if name is not None and base is not None:
            dinfo = f"[{name} + {iova - base:#x}]"
        logline = (f"[cpu{evt.flags.CPU}] GPUVM[{ctx}/{self.vmcnt:5}]: <{a}>{t}.{1<<evt.flags.WIDTH:<2}{m} " +
                   f"{iova:#x}({evt.addr:#x}){dinfo} = {evt.data:#x}")
        self.log(logline, show_cpu=False)
        self.vmcnt += 1
        #self.mon.poll()

    def meta_gpuvm(self, iova, size):
        meta = ""
        iova &= 0xfffffffffff
        for off in range(size):
            offva = iova + off
            if offva in self.readlog:
                ctr, evt = self.readlog[offva]
                m = "+" if evt.flags.MULTI else " "
                meta += f"[R.{1<<evt.flags.WIDTH:<2}{m} @{ctr} +{off:#x}]"

            if offva in self.writelog:
                ctr, evt = self.writelog[offva]
                m = "+" if evt.flags.MULTI else " "
                meta += f"[W.{1<<evt.flags.WIDTH:<2}{m} @{ctr} +{off:#x}]"

        return meta or None

    def get_stream(self, context, off):
        stream = self.uat.iostream(context, off)
        stream.meta_fn = self.meta_gpuvm
        return stream

    def start(self):
        super().start()

        self.clear_ttbr_tracers()
        self.clear_uatmap_tracers()
        self.add_ttbr_tracers()
        self.add_uatmap_tracers()
        self.clear_gpuvm_tracers()
        self.add_mon_regions()

        #self.handoff_tracer.start()
        self.init_channels()
        if self.state.active:
            self.resume()
        else:
            self.pause()

    def stop(self):
        self.pause()
        self.handoff_tracer.stop()
        self.clear_ttbr_tracers()
        self.clear_uatmap_tracers()
        self.clear_gpuvm_tracers()
        super().stop()

    def mon_addva(self, ctx, va, size, name=""):
        self.mon.add(va, size, name, readfn= lambda a, s: self.uat.ioread(ctx, a, s))

    def handle_ringmsg(self, msg):
        if isinstance(msg, FlagMsg):
            self.log(f"== Event flag notification ==")
            self.handle_event(msg)
            return
        elif isinstance(msg, RunCmdQueueMsg):
            self.log(f"== Work notification (type {msg.queue_type})==")
            queue = self.get_cmdqueue(msg.cmdqueue_addr, msg.new_queue)
            work_items = list(queue.get_workitems(msg))
            if self.encoder_id_filter is not None:
                for wi in work_items:
                    if wi.cmd.magic == 0:
                        # TA
                        if not self.encoder_id_filter(wi.cmd.struct_3.encoder_id):
                            return True
                    if wi.cmd.magic == 1:
                        # 3D
                        if not self.encoder_id_filter(wi.cmd.struct_6.encoder_id):
                            return True
            for wi in work_items:
                self.log(str(wi))
                if msg.queue_type == 2:
                    pass
                    #return self.handle_compute(wi)
                elif msg.queue_type == 1:
                    self.handle_3d(wi)
                    self.queue_3d = queue
                elif msg.queue_type == 0:
                    self.handle_ta(wi)
                    self.queue_ta = queue
        return True

    def handle_event(self, msg):
        if self.last_ta and self.redump:
            self.log("Redumping TA...")
            stream = self.get_stream(0, self.last_ta._addr)
            last_ta = CmdBufWork.parse_stream(stream)
            self.log(str(last_ta))
            self.handle_ta(last_ta)
            self.queue_ta.update_info()
            self.log(f"Queue info: {self.queue_ta.info}")
            self.last_ta = None
        if self.last_3d and self.redump:
            self.log("Redumping 3D...")
            stream = self.get_stream(0, self.last_3d._addr)
            last_3d = CmdBufWork.parse_stream(stream)
            self.log(str(last_3d))
            self.handle_3d(last_3d)
            self.queue_3d.update_info()
            self.log(f"Queue info: {self.queue_3d.info}")
            self.last_3d = None

    def dump_buffer_manager(self, buffer_mgr, kread, read):
        return

        self.log(f"  buffer_mgr @ {buffer_mgr._addr:#x}: {buffer_mgr!s}")
        self.log(f"    page_list @ {buffer_mgr.page_list_addr:#x}:")
        chexdump(read(buffer_mgr.page_list_addr,
                        buffer_mgr.page_list_size), print_fn=self.log)
        self.log(f"    block_list @ {buffer_mgr.block_list_addr:#x}:")
        chexdump(read(buffer_mgr.block_list_addr,
                        0x8000), print_fn=self.log)
        #self.log(f"    unkptr_d8 @ {buffer_mgr.unkptr_d8:#x}:")
        #chexdump(read(buffer_mgr.unkptr_d8, 0x4000), print_fn=self.log)


    def handle_ta(self, wi):
        self.log(f"Got TA WI{wi.cmd.magic:d}")
        self.last_ta = wi

        def kread(off, size):
            return self.uat.ioread(0, off, size)

        if wi.cmd.magic == 6:
            wi6 = wi.cmd
            #self.log(f"  unkptr_14 @ {wi6.unkptr_14:#x}:")
            #chexdump(kread(wi6.unkptr_14, 0x100), print_fn=self.log)

        elif wi.cmd.magic == 0:
            wi0 = wi.cmd
            context = wi0.context_id

            def read(off, size):
                return self.uat.ioread(context, off & 0x7fff_ffff_ffff_ffff, size)

            #chexdump(kread(wi0.addr, 0x600), print_fn=self.log)
            self.log(f"  context_id = {context:#x}")
            self.dump_buffer_manager(wi0.buffer_mgr, kread, read)
            #self.log(f"  unk_emptybuf @ {wi0.unk_emptybuf_addr:#x}:")
            #chexdump(kread(wi0.unk_emptybuf_addr, 0x1000), print_fn=self.log)

            #self.log(f"  unkptr_48 @ {wi0.unkptr_48:#x}:")
            #chexdump(read(wi0.unkptr_48, 0x1000), print_fn=self.log)
            #self.log(f"  unkptr_58 @ {wi0.unkptr_58:#x}:")
            #chexdump(read(wi0.unkptr_58, 0x4000), print_fn=self.log)
            #self.log(f"  unkptr_60 @ {wi0.unkptr_60:#x}:")
            #chexdump(read(wi0.unkptr_60, 0x4000), print_fn=self.log)

            #self.log(f"  unkptr_45c @ {wi0.unkptr_45c:#x}:")
            #chexdump(read(wi0.unkptr_45c, 0x1800), print_fn=self.log)

            for i in wi0.microsequence.value:
                i = i.cmd
                if isinstance(i, StartTACmd):
                    self.log(f"  # StartTACmd")
                    self.log(f"    buf_thing @ {i.buf_thing_addr:#x}: {i.buf_thing!s}")
                    self.log(f"      unkptr_18 @ {i.buf_thing.unkptr_18:#x}:")
                    chexdump(read(i.buf_thing.unkptr_18, 0x100), print_fn=self.log)
                    self.log(f"    unkptr_24 @ {i.unkptr_24:#x}:")
                    chexdump(read(i.unkptr_24, 0x100), print_fn=self.log)
                    self.log(f"    unk_5c @ {i.unkptr_5c:#x}:")
                    chexdump(read(i.unkptr_5c, 0x100), print_fn=self.log)

                elif isinstance(i, FinalizeTACmd):
                    self.log(f"  # FinalizeTACmd")


            #self.uat.dump(context, self.log)

    def handle_3d(self, wi):
        self.log(f"Got 3D WI{wi.cmdid:d}")
        if wi.cmdid != 1:
            return

        self.last_3d = wi

        def kread(off, size):
            return self.uat.ioread(0, off, size)

        if wi.cmd.magic == 4:
            wi4 = wi.cmd
            #self.log(f" completion_buf @ {wi4.completion_buf_addr:#x}: {wi4.completion_buf!s} ")
            #chexdump(kread(wi4.completion_buf_addr, 0x1000), print_fn=self.log)
        elif wi.cmd.magic == 1:
            wi1 = wi.cmd
            context = wi1.context_id
            def read(off, size):
                return self.uat.ioread(context, off, size)

            self.log(f" context_id = {context:#x}")
            cmd3d = wi1.microsequence.value[0].cmd

            self.log(f" 3D:")
            self.log(f"  struct1 @ {cmd3d.struct1_addr:#x}: {cmd3d.struct1!s}")
            self.log(f"  struct2 @ {cmd3d.struct2_addr:#x}: {cmd3d.struct2!s}")
            #self.log(f"    tvb_start_addr @ {cmd3d.struct2.tvb_start_addr:#x}:")
            #if cmd3d.struct2.tvb_start_addr:
                #chexdump(read(cmd3d.struct2.tvb_start_addr, 0x1000), print_fn=self.log)
            #self.log(f"    tvb_tilemap_addr @ {cmd3d.struct2.tvb_tilemap_addr:#x}:")
            #if cmd3d.struct2.tvb_tilemap_addr:
                #chexdump(read(cmd3d.struct2.tvb_tilemap_addr, 0x1000), print_fn=self.log)
            #self.log(f"    aux_fb_ptr @ {cmd3d.struct2.aux_fb_ptr:#x}:")
            #chexdump(read(cmd3d.struct2.aux_fb_ptr, 0x100), print_fn=self.log)
            #self.log(f"    pipeline_base @ {cmd3d.struct2.pipeline_base:#x}:")
            #chexdump(read(cmd3d.struct2.pipeline_base, 0x100), print_fn=self.log)

            self.log(f"  buf_thing @ {cmd3d.buf_thing_addr:#x}: {cmd3d.buf_thing!s}")
            #self.log(f"    unkptr_18 @ {cmd3d.buf_thing.unkptr_18:#x}:")
            #chexdump(read(cmd3d.buf_thing.unkptr_18, 0x1000), print_fn=self.log)

            #self.log(f"  unk_24 @ {cmd3d.unkptr_24:#x}: {cmd3d.unk_24!s}")
            self.log(f"  struct6 @ {cmd3d.struct6_addr:#x}: {cmd3d.struct6!s}")
            #self.log(f"    unknown_buffer @ {cmd3d.struct6.unknown_buffer:#x}:")
            #chexdump(read(cmd3d.struct6.unknown_buffer, 0x1000), print_fn=self.log)
            self.log(f"  struct7 @ {cmd3d.struct7_addr:#x}: {cmd3d.struct7!s}")
            self.log(f"  unk_buf_ptr @ {cmd3d.unk_buf_ptr:#x}:")
            chexdump(kread(cmd3d.unk_buf_ptr, 0x11c), print_fn=self.log)
            self.log(f"  unk_buf2_ptr @ {cmd3d.unk_buf2_ptr:#x}:")
            chexdump(kread(cmd3d.unk_buf2_ptr, 0x18), print_fn=self.log)

            for i in wi1.microsequence.value:
                i = i.cmd
                if not isinstance(i, Finalize3DCmd):
                    continue
                self.log(f" Finalize:")
                cmdfin = i
                #self.log(f"  completion:")
                #chexdump(kread(cmdfin.completion, 0x4), print_fn=self.log)
                self.log(f"  unkptr_1c @ {cmdfin.unkptr_1c:#x}:")
                chexdump(kread(cmdfin.unkptr_1c, 0x1000), print_fn=self.log)
                #self.log(f"  unkptr_24 @ {cmdfin.unkptr_24:#x}:")
                #chexdump(kread(cmdfin.unkptr_24, 0x100), print_fn=self.log)
                self.log(f"  unkptr_34 @ {cmdfin.unkptr_34:#x}:")
                chexdump(kread(cmdfin.unkptr_34, 0x1000), print_fn=self.log)
                self.log(f"  unkptr_3c @ {cmdfin.unkptr_3c:#x}:")
                chexdump(kread(cmdfin.unkptr_3c, 0x1c0), print_fn=self.log)
                self.log(f"  unkptr_44 @ {cmdfin.unkptr_44:#x}:")
                chexdump(kread(cmdfin.unkptr_44, 0x40), print_fn=self.log)
                self.log(f"  unkptr_64 @ {cmdfin.unkptr_64:#x}:")
                chexdump(kread(cmdfin.unkptr_64, 0x118), print_fn=self.log)

            self.log(f"  buf_thing @ {wi1.buf_thing_addr:#x}: {wi1.buf_thing!s}")
            self.log(f"    unkptr_18 @ {wi1.buf_thing.unkptr_18:#x}:")
            chexdump(read(wi1.buf_thing.unkptr_18, 0x1000), print_fn=self.log)
            self.dump_buffer_manager(wi1.buffer_mgr, kread, read)
            #self.log(f"  unk_emptybuf @ {wi1.unk_emptybuf_addr:#x}:")
            #chexdump(kread(wi1.unk_emptybuf_addr, 0x1000), print_fn=self.log)
            #self.log(f"  tvb_addr @ {wi1.tvb_addr:#x}:")
            #chexdump(read(wi1.tvb_addr, 0x1000), print_fn=self.log)

    def handle_compute(self, msg):
        self.log("Got Compute Work Item")

        try:
            wi =  msg.workItems[0].cmd
        except:
            return

        def kread(off, size):
            return self.uat.ioread(0, off, size)

        context = wi.context_id

        def read(off, size):
            return self.uat.ioread(context, off, size)

        self.log(f" context_id = {context:#x}")
        self.log(f" unk_c @ {wi.unkptr_c:#x}: {wi.unk_c!s} ")
        #chexdump(kread(wi.unkptr_c, 0x100), print_fn=self.log)
        self.log(f"   unkptr_0:")
        chexdump(kread(wi.unk_c.unkptr_0, 0x1000), print_fn=self.log)

        self.log("StartComputeCmd:")
        try:
            ccmd = wi.microsequence.value[0].cmd
        except:
            self.log(" MISSING!")
            return
        self.log(f" unkptr_4: {ccmd.unkptr_4:#x}")
        chexdump(kread(ccmd.unkptr_4, 0x54), print_fn=self.log)
        self.log(f" unkptr_14: {ccmd.unkptr_14:#x}")
        chexdump(kread(ccmd.unkptr_14, 0x1000), print_fn=self.log)
        #self.log(f" unkptr_3c: {ccmd.unkptr_3c:#x}")
        #chexdump(kread(ccmd.unkptr_3c, 0xb4), print_fn=self.log)

        ci = ccmd.computeinfo
        self.log(f" Compute Info: {ci!s}")
        self.log(f"  args:")
        u0data = read(ci.args, 0x8000)
        chexdump(u0data, print_fn=self.log)
        args = struct.unpack("<8Q", u0data[0x7fa0:0x7fe0])
        for i, p in enumerate(args):
            if p:
                self.log(f"    args[{i}] @ {p:#x}")
                chexdump(read(p, 0x1000), print_fn=self.log)
        p0, p1 = struct.unpack("<QQ", u0data[0x7fe0:0x7ff0])
        self.log(f"    p0 @ {p0:#x}")
        chexdump(read(p0, 0x100), print_fn=self.log)
        self.log(f"    p1 @ {p1:#x}")
        chexdump(read(p1, 0x100), print_fn=self.log)
        self.log(f"  cmdlist:")
        chexdump(read(ci.cmdlist, 0x8000), print_fn=self.log)
        self.log(f"  unkptr_10:")
        chexdump(read(ci.unkptr_10, 8), print_fn=self.log)
        self.log(f"  unkptr_18:")
        chexdump(read(ci.unkptr_18, 8), print_fn=self.log)
        self.log(f"  unkptr_20:")
        chexdump(read(ci.unkptr_20, 8), print_fn=self.log)
        self.log(f"  unkptr_28:")
        chexdump(read(ci.unkptr_28, 8), print_fn=self.log)
        self.log(f"  pipeline:")
        chexdump(read(ci.pipeline_base, 0x1000), print_fn=self.log)
        self.log(f"  unkptr_48:")
        chexdump(read(ci.unkptr_48, 0x8000), print_fn=self.log)

        ci2 = ccmd.computeinfo2
        self.log(f" Compute Info 2: {ci2!s}")
        self.log(f"  unknown_buffer:")
        chexdump(read(ci2.unknown_buffer, 0x8000), print_fn=self.log)

    def ignore(self, addr=None):
        if addr is None:
            addr = self.last_msg.cmdqueue_addr
        self.ignorelist += [addr & 0xfff_ffffffff]

    def kick(self, val):
        if not self.state.active:
            return

        self.log(f"kick~! {val:#x}")
        self.mon.poll()

        if val == 0x10: # Kick Firmware
            self.log("KickFirmware, polling")
            self.uat.invalidate_cache()
            for chan in self.channels:
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
            self.uat.invalidate_cache()

        else:
            raise(Exception("Unknown kick type"))

        self.channels[channel].poll()

        ## if val not in [0x0, 0x1, 0x10, 0x11]:
        #if self.last_msg and isinstance(self.last_msg, (RunCmdQueue, DeviceControl_17)):
            #self.hv.run_shell()

            #self.last_msg = None

        # check the gfx -> cpu channels
        for chan in self.channels[13:]:
            chan.poll()

    def fwkick(self, val):
        if not self.state.active:
            return

        self.log(f"FW Kick~! {val:#x}")
        self.mon.poll()

        if val == 0x00: # Kick FW control
            channel = len(self.channels) - 1
        else:
            raise(Exception("Unknown kick type"))

        self.channels[channel].poll()

        # check the gfx -> cpu channels
        for chan in self.channels[13:]:
            chan.poll()

    def pong(self):
        if not self.state.active:
            return

        self.log("pong~!");
        self.mon.poll()

        # check the gfx -> cpu channels
        for chan in self.channels[13:]:
            chan.poll()

    def trace_uatrange(self, ctx, start, size, name=None, off=0):
        start &= 0xfff_ffffffff
        ranges = self.uat.iotranslate(ctx, start, size)
        iova = start
        for range in ranges:
            pstart, psize = range
            if pstart:
                self.log(f"trace {name} {start:#x}/{iova:#x} [{pstart:#x}:{psize:#x}] +{off:#x}")
                self.hv.add_tracer(irange(pstart, psize), f"GPUVM",
                           mode=TraceMode.ASYNC,
                           read=self.event_gpuvm,
                           write=self.event_gpuvm,
                           iova=iova,
                           paddr=pstart,
                           name=name,
                           base=start - off)
            iova += psize

    def untrace_uatrange(self, ctx, start, size):
        ranges = self.uat.iotranslate(ctx, start, size)
        for range in ranges:
            start, size = range
            if start:
                self.hv.del_tracer(irange(start, size), f"GPUVM")

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
        self.state.active = True
        self.state.initdata = None
        self.state.channel_info = []
        self.state.channels = {}
        self.state.queues = {}

    def init_channels(self):
        if self.channels:
            return
        #self.channels = []
        for i, chan_info in enumerate(self.state.channel_info):
            print(channelNames[i], chan_info)
            if channelNames[i] == "Stats": # ignore stats
                continue
            elif channelNames[i] == "KTrace": # ignore KTrace
                continue
            elif channelNames[i] == "FWCtl":
                channel_chan = FWCtlChannelTracer(self, chan_info, i)
            else:
                channel_chan = ChannelTracer(self, chan_info, i)
            self.channels.append(channel_chan)

    def pause(self):
        self.clear_gpuvm_tracers()
        if self.state.initdata is None:
            return
        self.clear_uatmap_tracers()
        self.clear_ttbr_tracers()
        self.log("Pausing tracing")
        self.state.active = False
        for chan in self.channels:
            chan.set_active(False)
        for queue in self.cmdqueues.values():
            queue.set_active(False)
        for info_addr in self.state.queues:
            self.state.queues[info_addr].rptr = None
        self.untrace_uatrange(0, self.state.initdata.regionA_addr, 0x4000)
        self.untrace_uatrange(0, self.state.initdata.regionB_addr, 0x6bc0)
        self.untrace_uatrange(0, self.state.initdata.regionC_addr, 0x11d40)

    def resume(self):
        self.add_gpuvm_tracers()
        self.add_uatmap_tracers()
        self.add_ttbr_tracers()
        if self.state.initdata is None:
            return
        self.log("Resuming tracing")
        self.state.active = True
        for chan in self.channels:
            if chan.name == "Stats":
                continue
            chan.set_active(True)
        for queue in self.cmdqueues.values():
            queue.set_active(True)
        self.trace_uatrange(0, self.state.initdata.regionA_addr, 0x4000, name="regionA")
        self.trace_uatrange(0, self.state.initdata.regionB_addr, 0x6bc0, name="regionB")
        self.trace_uatrange(0, self.state.initdata.regionC_addr, 0x11d40, name="regionC")
        self.trace_uatrange(0, self.state.initdata.regionB.buffer_mgr_ctl_addr, 0x4000, name="Buffer manager ctl")

    def add_mon_regions(self):
        return
        initdata = self.state.initdata
        if initdata is not None:
            self.mon_addva(0, initdata.regionA_addr, 0x4000, "RegionA")
            self.mon_addva(0, initdata.regionB_addr, 0x6bc0, "RegionB")
            self.mon_addva(0, initdata.regionC_addr, 0x11d40, "RegionC")
            #self.mon_addva(0, initdata.regionB.unkptr_170, 0xc0, "unkptr_170")
            #self.mon_addva(0, initdata.regionB.unkptr_178, 0x1c0, "unkptr_178")
            #self.mon_addva(0, initdata.regionB.unkptr_180, 0x140, "unkptr_180")
            self.mon_addva(0, initdata.regionB.unkptr_190, 0x80, "unkptr_190")
            self.mon_addva(0, initdata.regionB.unkptr_198, 0xc0, "unkptr_198")
            self.mon_addva(0, initdata.regionB.buffer_mgr_ctl_addr, 0x4000, "Buffer manager ctl")
            self.mon_addva(0, initdata.unkptr_20.unkptr_0, 0x40, "unkptr_20.unkptr_0")
            self.mon_addva(0, initdata.unkptr_20.unkptr_8, 0x40, "unkptr_20.unkptr_8")

    def pong_init(self, addr):
        self.log("UAT at init time:")
        self.uat.invalidate_cache()
        self.uat.dump(0, log=self.log)
        addr |= 0xfffff000_00000000
        initdata = InitData.parse_stream(self.get_stream(0, addr))

        self.log("Initdata:")
        self.log(initdata)

        self.add_mon_regions()

        #self.initdata.regionB.mon(lambda addr, size, name: self.mon_addva(0, addr, size, name))

        self.state.initdata_addr = addr
        self.state.initdata = initdata
        self.state.channel_info = []
        self.state.fwlog_ring2 = initdata.regionB.fwlog_ring2
        channels = initdata.regionB.channels
        for i in channelNames:
            if i == "FWCtl":
                chan_info = initdata.fw_status.fwctl_channel
            else:
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


        if self.pause_after_init:
            self.log("Pausing tracing")
            self.pause()
            self.stop()
        if self.shell_after_init:
            self.hv.run_shell()
        if self.after_init_hook:
            self.after_init_hook()

ChannelTracer = ChannelTracer._reloadcls()

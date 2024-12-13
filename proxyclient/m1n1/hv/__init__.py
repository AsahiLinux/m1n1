# SPDX-License-Identifier: MIT
import io, sys, traceback, struct, array, bisect, os, plistlib, signal, runpy
from construct import *

from ..asm import ARMAsm
from ..tgtypes import *
from ..proxy import IODEV, START, EVENT, EXC, EXC_RET, ExcInfo
from ..utils import *
from ..sysreg import *
from ..macho import MachO
from ..adt import load_adt
from .. import xnutools, shell

from .gdbserver import *
from .types import *
from .virtutils import *
from .virtio import *

__all__ = ["HV"]

class HV(Reloadable):
    PAC_MASK = 0xfffff00000000000

    PTE_VALID               = 1 << 0

    PTE_MEMATTR_UNCHANGED   = 0b1111 << 2
    PTE_S2AP_RW             = 0b11 << 6
    PTE_SH_NS               = 0b11 << 8
    PTE_ACCESS              = 1 << 10
    PTE_ATTRIBUTES          = PTE_ACCESS | PTE_SH_NS | PTE_S2AP_RW | PTE_MEMATTR_UNCHANGED

    SPTE_TRACE_READ         = 1 << 63
    SPTE_TRACE_WRITE        = 1 << 62
    SPTE_TRACE_UNBUF        = 1 << 61
    SPTE_MAP                = 0 << 50
    SPTE_HOOK               = 1 << 50
    SPTE_PROXY_HOOK_R       = 2 << 50
    SPTE_PROXY_HOOK_W       = 3 << 50
    SPTE_PROXY_HOOK_RW      = 4 << 50

    MSR_REDIRECTS = {
        SCTLR_EL1: SCTLR_EL12,
        TTBR0_EL1: TTBR0_EL12,
        TTBR1_EL1: TTBR1_EL12,
        TCR_EL1: TCR_EL12,
        ESR_EL1: ESR_EL12,
        FAR_EL1: FAR_EL12,
        AFSR0_EL1: AFSR0_EL12,
        AFSR1_EL1: AFSR1_EL12,
        MAIR_EL1: MAIR_EL12,
        AMAIR_EL1: AMAIR_EL12,
        CONTEXTIDR_EL1: CONTEXTIDR_EL12,
        # ACTLR_EL1: ACTLR_EL12, # Handled in hv_exc.c, depends on CPU version
        AMX_CONFIG_EL1: AMX_CONFIG_EL12,
        SPRR_CONFIG_EL1: SPRR_CONFIG_EL12,
        SPRR_PPERM_EL1: SPRR_PPERM_EL12,
        SPRR_UPERM_EL0: SPRR_UPERM_EL02,
        SPRR_AMRANGE_EL1: SPRR_AMRANGE_EL12,
        SPRR_UMPRR_EL1: SPRR_UMPRR_EL12,
        APCTL_EL1: APCTL_EL12,
        APSTS_EL1: APSTS_EL12,
        KERNKEYLO_EL1: KERNKEYLO_EL12,
        KERNKEYHI_EL1: KERNKEYHI_EL12,
        GXF_CONFIG_EL1: GXF_CONFIG_EL12,
        GXF_PABENTRY_EL1: GXF_PABENTRY_EL12,
        GXF_ENTRY_EL1: GXF_ENTRY_EL12,
        VBAR_GL1: VBAR_GL12,
        SPSR_GL1: SPSR_GL12,
        ASPSR_GL1: ASPSR_GL12,
        ESR_GL1: ESR_GL12,
        ELR_GL1: ELR_GL12,
    }

    AIC_EVT_TYPE_HW = 1
    IRQTRACE_IRQ = 1

    def __init__(self, iface, proxy, utils):
        self.iface = iface
        self.p = proxy
        self.u = utils
        self.pac_mask = self.PAC_MASK
        self.user_pac_mask = self.PAC_MASK
        self.vbar_el1 = None
        self.want_vbar = None
        self.vectors = [None]
        self._bps = [None, None, None, None, None]
        self._bp_hooks = dict()
        self._wps = [None, None, None, None]
        self._wpcs = [0, 0, 0, 0]
        self.sym_offset = 0
        self.symbols = []
        self.symbol_dict = {}
        self.sysreg = {}
        self.novm = False
        self._in_handler = False
        self._sigint_pending = False
        self._in_shell = False
        self._gdbserver = None
        self.vm_hooks = [None]
        self.interrupt_map = {}
        self.mmio_maps = DictRangeMap()
        self.dirty_maps = BoolRangeMap()
        self.tracer_caches = {}
        self.shell_locals = {}
        self.xnu_mode = False
        self._update_shell_locals()
        self.wdt_cpu = None
        self.smp = True
        self.hook_exceptions = False
        self.started_cpus = {}
        self.started = False
        self.ctx = None
        self.hvcall_handlers = {}
        self.switching_context = False
        self.show_timestamps = False
        self.virtio_devs = {}

    def _reloadme(self):
        super()._reloadme()
        self._update_shell_locals()

    def _update_shell_locals(self):
        self.shell_locals.update({
            "hv": self,
            "iface": self.iface,
            "p": self.p,
            "u": self.u,
            "trace": trace,
            "TraceMode": TraceMode,
        })

        for attr in dir(self):
            a = getattr(self, attr)
            if callable(a):
                self.shell_locals[attr] = getattr(self, attr)

        self.shell_locals["ctx"] = self.context

    def log(self, s, *args, show_cpu=True, **kwargs):
        if self.ctx is not None and show_cpu:
            ts=""
            if self.show_timestamps:
                ts = f"[{self.u.mrs(CNTPCT_EL0):#x}]"
            print(ts+f"[cpu{self.ctx.cpu_id}] " + s, *args, **kwargs)
            if self.print_tracer.log_file:
                print(f"# {ts}[cpu{self.ctx.cpu_id}] " + s, *args, file=self.print_tracer.log_file, **kwargs)
        else:
            print(s, *args, **kwargs)
            if self.print_tracer.log_file:
                print("# " + s, *args, file=self.print_tracer.log_file, **kwargs)

    def unmap(self, ipa, size):
        assert self.p.hv_map(ipa, 0, size, 0) >= 0

    def map_hw(self, ipa, pa, size):
        '''map IPA (Intermediate Physical Address) to actual PA'''
        #print(f"map_hw {ipa:#x} -> {pa:#x} [{size:#x}]")
        if (ipa & 0x3fff) != (pa & 0x3fff):
            self.map_sw(ipa, pa, size)
            return

        ipa_p = align_up(ipa)
        if ipa_p != ipa:
            self.map_sw(ipa, pa, min(ipa_p - ipa, size))
            pa += ipa_p - ipa
            size -= ipa_p - ipa

        if size <= 0:
            return

        size_p = align_down(size)
        if size_p > 0:
            #print(f"map_hw real {ipa_p:#x} -> {pa:#x} [{size_p:#x}]")
            assert self.p.hv_map(ipa_p, pa | self.PTE_ATTRIBUTES | self.PTE_VALID, size_p, 1) >= 0

        if size_p != size:
            self.map_sw(ipa_p + size_p, pa + size_p, size - size_p)

    def map_sw(self, ipa, pa, size):
        #print(f"map_sw {ipa:#x} -> {pa:#x} [{size:#x}]")
        assert self.p.hv_map(ipa, pa | self.SPTE_MAP, size, 1) >= 0

    def map_hook(self, ipa, size, read=None, write=None, **kwargs):
        index = len(self.vm_hooks)
        self.vm_hooks.append((read, write, ipa, kwargs))
        self.map_hook_idx(ipa, size, index, read is not None, write is not None)

    def map_hook_idx(self, ipa, size, index, read=False, write=False, flags=0):
        if read:
            if write:
                t = self.SPTE_PROXY_HOOK_RW
            else:
                t = self.SPTE_PROXY_HOOK_R
        elif write:
            t = self.SPTE_PROXY_HOOK_W
        else:
            assert False

        assert self.p.hv_map(ipa, (index << 2) | flags | t, size, 0) >= 0

    def readmem(self, va, size):
        '''read from virtual memory'''
        with io.BytesIO() as buffer:
            while size > 0:
                pa = self.p.hv_translate(va, False, False)
                if pa == 0:
                    break

                size_in_page = 4096 - (va % 4096)
                if size < size_in_page:
                    buffer.write(self.iface.readmem(pa, size))
                    break

                buffer.write(self.iface.readmem(pa, size_in_page))
                va += size_in_page
                size -= size_in_page

            return buffer.getvalue()

    def writemem(self, va, data):
        '''write to virtual memory'''
        written = 0
        while written < len(data):
            pa = self.p.hv_translate(va, False, True)
            if pa == 0:
                break

            size_in_page = 4096 - (va % 4096)
            if len(data) - written < size_in_page:
                self.iface.writemem(pa, data[written:])
                written = len(data)
                break

            self.iface.writemem(pa, data[written:written + size_in_page])
            va += size_in_page
            written += size_in_page

        return written

    def trace_irq(self, device, num, count, flags):
        for n in range(num, num + count):
            if flags & self.IRQTRACE_IRQ:
                self.interrupt_map[n] = device
            else:
                self.interrupt_map.pop(n, None)

        start, size = self.adt["/arm-io/aic"].get_reg(0)
        zone = irange(start, size)
        if len(self.interrupt_map):
            self.add_tracer(zone, "AIC_IRQ", TraceMode.RESERVED)
        else:
            self.del_tracer(zone, "AIC_IRQ")

        assert self.p.hv_trace_irq(self.AIC_EVT_TYPE_HW, num, count, flags) > 0

    def add_tracer(self, zone, ident, mode=TraceMode.ASYNC, read=None, write=None, **kwargs):
        assert mode in (TraceMode.RESERVED, TraceMode.OFF, TraceMode.BYPASS) or read or write
        self.mmio_maps[zone, ident] = (mode, ident, read, write, kwargs)
        self.dirty_maps.set(zone)

    def del_tracer(self, zone, ident):
        del self.mmio_maps[zone, ident]
        self.dirty_maps.set(zone)

    def clear_tracers(self, ident):
        for r, v in self.mmio_maps.items():
            if ident in v:
                v.pop(ident)
                self.dirty_maps.set(r)

    def trace_device(self, path, mode=TraceMode.ASYNC, ranges=None):
        node = self.adt[path]
        for index in range(len(node.reg)):
            if ranges is not None and index not in ranges:
                continue
            addr, size = node.get_reg(index)
            self.trace_range(irange(addr, size), mode)

    def trace_range(self, zone, mode=TraceMode.ASYNC, read=True, write=True, name=None):
        if mode is True:
            mode = TraceMode.ASYNC
        if mode and mode != TraceMode.OFF:
            self.add_tracer(zone, "PrintTracer", mode,
                            self.print_tracer.event_mmio if read else None,
                            self.print_tracer.event_mmio if write else None,
                            start=zone.start,
                            name=name)
        else:
            self.del_tracer(zone, "PrintTracer")

    def pt_update(self):
        if not self.dirty_maps:
            return

        self.dirty_maps.compact()
        self.mmio_maps.compact()

        top = 0

        for zone in self.dirty_maps:
            if zone.stop <= top:
                continue
            top = max(top, zone.start)

            for mzone, maps in self.mmio_maps.overlaps(zone):
                if mzone.stop <= top:
                    continue
                if top < mzone.start:
                    self.unmap(top, mzone.start - top)
                    self.log(f"PT[{top:09x}:{mzone.start:09x}] -> *UNMAPPED*")

                top = mzone.stop
                if not maps:
                    continue
                maps = sorted(maps.values(), reverse=True)
                mode, ident, read, write, kwargs = maps[0]

                need_read = any(m[2] for m in maps)
                need_write = any(m[3] for m in maps)

                if mode == TraceMode.RESERVED:
                    self.log(f"PT[{mzone.start:09x}:{mzone.stop:09x}] -> RESERVED {ident}")
                    continue
                elif mode in (TraceMode.HOOK, TraceMode.SYNC):
                    self.map_hook_idx(mzone.start, mzone.stop - mzone.start, 0,
                                      need_read, need_write)
                    if mode == TraceMode.HOOK:
                        for m2, i2, r2, w2, k2 in maps[1:]:
                            if m2 == TraceMode.HOOK:
                                self.log(f"!! Conflict: HOOK {i2}")
                elif mode == TraceMode.WSYNC:
                    flags = self.SPTE_TRACE_READ if need_read else 0
                    self.map_hook_idx(mzone.start, mzone.stop - mzone.start, 0,
                                      False, need_write, flags=flags)
                elif mode in (TraceMode.UNBUF, TraceMode.ASYNC, TraceMode.BYPASS):
                    pa = mzone.start
                    if mode == TraceMode.UNBUF:
                        pa |= self.SPTE_TRACE_UNBUF
                    if need_read:
                        pa |= self.SPTE_TRACE_READ
                    if need_write:
                        pa |= self.SPTE_TRACE_WRITE
                    self.map_sw(mzone.start, pa, mzone.stop - mzone.start)
                elif mode == TraceMode.OFF:
                    self.map_hw(mzone.start, mzone.start, mzone.stop - mzone.start)
                    self.log(f"PT[{mzone.start:09x}:{mzone.stop:09x}] -> HW:{ident}")
                    continue

                rest = [m[1] for m in maps[1:] if m[0] != TraceMode.OFF]
                if rest:
                    rest = " (+ " + ", ".join(rest) + ")"
                else:
                    rest = ""

                self.log(f"PT[{mzone.start:09x}:{mzone.stop:09x}] -> {mode.name}.{'R' if read else ''}{'W' if read else ''} {ident}{rest}")

            if top < zone.stop:
                self.unmap(top, zone.stop - top)
                self.log(f"PT[{top:09x}:{zone.stop:09x}] -> *UNMAPPED*")

        self.u.inst(0xd50c83df) # tlbi vmalls12e1is
        self.dirty_maps.clear()

    def shellwrap(self, func, description, update=None, needs_ret=False):

        while True:
            try:
                return func()
            except Exception:
                print(f"Exception in {description}")
                traceback.print_exc()

            if not self.ctx:
                print("Running in asynchronous context. Target operations are not available.")

            def do_exit(i):
                raise shell.ExitConsole(i)

            self.shell_locals["skip"] = lambda: do_exit(1)
            self.shell_locals["cont"] = lambda: do_exit(0)
            ret = self.run_shell("Entering debug shell", "Returning to tracer")
            self.shell_locals["skip"] = self.skip
            self.shell_locals["cont"] = self.cont

            if self.ctx:
                self.cpu() # Return to the original CPU to avoid confusing things

            if ret == 1:
                if needs_ret:
                    print("Cannot skip, return value required.")
                else:
                    return

            if update:
                update()

    def run_shell(self, entry_msg="Entering shell", exit_msg="Continuing"):
        def handle_sigusr1(signal, stack):
            raise shell.ExitConsole(EXC_RET.HANDLED)

        def handle_sigusr2(signal, stack):
            raise shell.ExitConsole(EXC_RET.EXIT_GUEST)

        default_sigusr1 = signal.signal(signal.SIGUSR1, handle_sigusr1)
        try:
            default_sigusr2 = signal.signal(signal.SIGUSR2, handle_sigusr2)
            try:
                self._in_shell = True
                try:
                    if not self._gdbserver is None:
                        self._gdbserver.notify_in_shell()
                    return shell.run_shell(self.shell_locals, entry_msg, exit_msg)
                finally:
                    self._in_shell = False
            finally:
                signal.signal(signal.SIGUSR2, default_sigusr2)
        finally:
            signal.signal(signal.SIGUSR1, default_sigusr1)

    @property
    def in_shell(self):
        return self._in_shell

    def gdbserver(self, address="/tmp/.m1n1-unix", log=None):
        '''activate gdbserver'''
        if not self._gdbserver is None:
            raise Exception("gdbserver is already running")

        self._gdbserver = GDBServer(self, address, log)
        self._gdbserver.activate()

    def shutdown_gdbserver(self):
        '''shutdown gdbserver'''
        self._gdbserver.shutdown()
        self._gdbserver = None

    def handle_mmiotrace(self, data):
        evt = EvtMMIOTrace.parse(data)

        def do_update():
            nonlocal mode, ident, read, write, kwargs
            read = lambda *args, **kwargs: None
            write = lambda *args, **kwargs: None

            m = self.mmio_maps[evt.addr].get(ident, None)
            if not m:
                return

            mode, ident, read_, write_, kwargs = m
            read = read_ or read
            write = write_ or write

        maps = sorted(self.mmio_maps[evt.addr].values(), reverse=True)
        for mode, ident, read, write, kwargs in maps:
            if mode > TraceMode.WSYNC or (evt.flags.WRITE and mode > TraceMode.UNBUF):
                print(f"ERROR: mmiotrace event but expected {mode.name} mapping")
                continue
            if mode == TraceMode.OFF:
                continue
            if evt.flags.WRITE:
                if write:
                    self.shellwrap(lambda: write(evt, **kwargs),
                                   f"Tracer {ident}:write ({mode.name})", update=do_update)
            else:
                if read:
                    self.shellwrap(lambda: read(evt, **kwargs),
                                   f"Tracer {ident}:read ({mode.name})", update=do_update)

    def handle_vm_hook_mapped(self, ctx, data):
        maps = sorted(self.mmio_maps[data.addr].values(), reverse=True)

        if not maps:
            raise Exception(f"VM hook without a mapping at {data.addr:#x}")

        def do_update():
            nonlocal mode, ident, read, write, kwargs
            read = lambda *args, **kwargs: None
            write = lambda *args, **kwargs: None

            m = self.mmio_maps[data.addr].get(ident, None)
            if not m:
                return

            mode, ident, read_, write_, kwargs = m
            read = read_ or read
            write = write_ or write

        mode, ident, read, write, kwargs = maps[0]

        first = 0

        val = data.data

        if mode not in (TraceMode.HOOK, TraceMode.SYNC, TraceMode.WSYNC):
            raise Exception(f"VM hook with unexpected mapping at {data.addr:#x}: {maps[0][0].name}")

        if not data.flags.WRITE:
            if mode == TraceMode.HOOK and not read:
                mode = TraceMode.SYNC
                first += 1

            if mode == TraceMode.HOOK:
                val = self.shellwrap(lambda: read(data.addr, 8 << data.flags.WIDTH, **kwargs),
                                     f"Tracer {ident}:read (HOOK)", update=do_update, needs_ret=True)

                if not isinstance(val, list) and not isinstance(val, tuple):
                    val = [val]
                first += 1
            elif mode == TraceMode.SYNC:
                try:
                    val = self.u.read(data.addr, 8 << data.flags.WIDTH)
                except:
                    self.log(f"MMIO read failed: {data.addr:#x} (w={data.flags.WIDTH})")
                    raise
                if not isinstance(val, list) and not isinstance(val, tuple):
                    val = [val]
            elif mode == TraceMode.WSYNC:
                raise Exception(f"VM hook with unexpected mapping at {data.addr:#x}: {maps[0][0].name}")

            for i in range(1 << max(0, data.flags.WIDTH - 3)):
                self.p.write64(ctx.data + 16 + 8 * i, val[i])

        elif mode == TraceMode.HOOK:
            first += 1

        flags = data.flags.copy()
        flags.CPU = self.ctx.cpu_id
        width = data.flags.WIDTH

        if width > 3:
            flags.WIDTH = 3
            flags.MULTI = 1

        for i in range(1 << max(0, width - 3)):
            evt = Container(
                flags = flags,
                reserved = 0,
                pc = ctx.elr,
                addr = data.addr + 8 * i,
                data = val[i]
            )

            for mode, ident, read, write, kwargs in maps[first:]:
                if flags.WRITE:
                    if write:
                        self.shellwrap(lambda: write(evt, **kwargs),
                                       f"Tracer {ident}:write ({mode.name})", update=do_update)
                else:
                    if read:
                        self.shellwrap(lambda: read(evt, **kwargs),
                                       f"Tracer {ident}:read ({mode.name})", update=do_update)

        if data.flags.WRITE:
            mode, ident, read, write, kwargs = maps[0]

            if data.flags.WIDTH <= 3:
                wval = val[0]
            else:
                wval = val

            if mode == TraceMode.HOOK and not write:
                mode = TraceMode.SYNC

            if mode == TraceMode.HOOK:
                self.shellwrap(lambda: write(data.addr, wval, 8 << data.flags.WIDTH, **kwargs),
                            f"Tracer {ident}:write (HOOK)", update=do_update)
            elif mode in (TraceMode.SYNC, TraceMode.WSYNC):
                try:
                    self.u.write(data.addr, wval, 8 << data.flags.WIDTH)
                except:
                    if data.flags.WIDTH > 3:
                        wval = wval[0]
                    self.log(f"MMIO write failed: {data.addr:#x} = {wval} (w={data.flags.WIDTH})")
                    raise

        return True

    def handle_vm_hook(self, ctx):
        data = self.iface.readstruct(ctx.data, VMProxyHookData)

        if data.id == 0:
            return self.handle_vm_hook_mapped(ctx, data)

        rfunc, wfunc, base, kwargs = self.vm_hooks[data.id]

        d = data.data
        if data.flags.WIDTH < 3:
            d = d[0]

        if data.flags.WRITE:
            wfunc(base, data.addr - base, d, 8 << data.flags.WIDTH, **kwargs)
        else:
            val = rfunc(base, data.addr - base, 8 << data.flags.WIDTH, **kwargs)
            if not isinstance(val, list) and not isinstance(val, tuple):
                val = [val]
            for i in range(1 << max(0, data.flags.WIDTH - 3)):
                self.p.write64(ctx.data + 16 + 8 * i, val[i])

        return True

    def handle_irqtrace(self, data):
        evt = EvtIRQTrace.parse(data)

        if evt.type == self.AIC_EVT_TYPE_HW and evt.flags & self.IRQTRACE_IRQ:
            dev = self.interrupt_map[int(evt.num)]
            print(f"IRQ: {dev}: {evt.num}")

    def addr(self, addr):
        unslid_addr = addr + self.sym_offset
        if self.xnu_mode and (addr < self.tba.virt_base or unslid_addr < self.macho.vmin):
            return f"0x{addr:x}"

        saddr, name = self.sym(addr)

        if name is None:
            return f"0x{addr:x} (0x{unslid_addr:x})"

        return f"0x{addr:x} ({name}+0x{unslid_addr - saddr:x})"

    def resolve_symbol(self, name):
        return self.symbol_dict[name] - self.sym_offset

    def sym(self, addr):
        unslid_addr = addr + self.sym_offset

        if self.xnu_mode and (addr < self.tba.virt_base or unslid_addr < self.macho.vmin):
            return None, None

        idx = bisect.bisect_left(self.symbols, (unslid_addr + 1, "")) - 1
        if idx < 0 or idx >= len(self.symbols):
            return None, None

        return self.symbols[idx]

    def get_sym(self, addr):
        a, name = self.sym(addr)
        if addr == a:
            return name
        else:
            return None

    def handle_msr(self, ctx, iss=None):
        if iss is None:
            iss = ctx.esr.ISS
        iss = ESR_ISS_MSR(iss)
        enc = iss.Op0, iss.Op1, iss.CRn, iss.CRm, iss.Op2

        name = sysreg_name(enc)

        skip = set()
        shadow = {
            #SPRR_CONFIG_EL1,
            #SPRR_PERM_EL0,
            #SPRR_PERM_EL1,
            VMSA_LOCK_EL1,
            #SPRR_UNK1_EL1,
            #SPRR_UNK2_EL1,
            MDSCR_EL1,
        }
        ro = {
            ACC_CFG_EL1,
            ACC_OVRD_EL1,
        }
        xlate = {
            DC_CIVAC,
        }
        for i in range(len(self._bps)):
            shadow.add(DBGBCRn_EL1(i))
            shadow.add(DBGBVRn_EL1(i))
        for i in range(len(self._wps)):
            shadow.add(DBGWCRn_EL1(i))
            shadow.add(DBGWVRn_EL1(i))

        value = 0
        if enc == CYC_OVRD_EL1 and iss.DIR == MSR_DIR.WRITE:
            if iss.Rt != 31:
                value = ctx.regs[iss.Rt]
            self.log(f"Skip: msr {name}, x{iss.Rt} = {value:x}")
            if value & 1:
                self.log("Guest is shutting down CPU")
                self.p.hv_exit_cpu()
                del self.started_cpus[self.ctx.cpu_id]
        elif enc in shadow:
            if iss.DIR == MSR_DIR.READ:
                value = self.sysreg[self.ctx.cpu_id].setdefault(enc, 0)
                self.log(f"Shadow: mrs x{iss.Rt}, {name} = {value:x}")
                if iss.Rt != 31:
                    ctx.regs[iss.Rt] = value
            else:
                if iss.Rt != 31:
                    value = ctx.regs[iss.Rt]
                self.log(f"Shadow: msr {name}, x{iss.Rt} = {value:x}")
                self.sysreg[self.ctx.cpu_id][enc] = value
        elif enc in skip or (enc in ro and iss.DIR == MSR_DIR.WRITE):
            if iss.DIR == MSR_DIR.READ:
                self.log(f"Skip: mrs x{iss.Rt}, {name} = 0")
                if iss.Rt != 31:
                    ctx.regs[iss.Rt] = 0
            else:
                if iss.Rt != 31:
                    value = ctx.regs[iss.Rt]
                self.log(f"Skip: msr {name}, x{iss.Rt} = {value:x}")
        else:
            if iss.DIR == MSR_DIR.READ:
                enc2 = self.MSR_REDIRECTS.get(enc, enc)
                value = self.u.mrs(enc2)
                self.log(f"Pass: mrs x{iss.Rt}, {name} = {value:x} ({sysreg_name(enc2)})")
                if iss.Rt != 31:
                    ctx.regs[iss.Rt] = value
            else:
                if iss.Rt != 31:
                    value = ctx.regs[iss.Rt]
                enc2 = self.MSR_REDIRECTS.get(enc, enc)
                sys.stdout.flush()
                if enc in xlate:
                    value = self.p.hv_translate(value, True, False)
                self.u.msr(enc2, value, call=self.p.gl2_call)
                self.log(f"Pass: msr {name}, x{iss.Rt} = {value:x} (OK) ({sysreg_name(enc2)})")

        ctx.elr += 4

        if self.hook_exceptions:
            self.patch_exception_handling()

        return True

    def handle_impdef(self, ctx):
        if ctx.esr.ISS == 0x20:
            return self.handle_msr(ctx, ctx.afsr1)

        code = struct.unpack("<I", self.iface.readmem(ctx.elr_phys, 4))
        c = ARMAsm(".inst " + ",".join(str(i) for i in code), ctx.elr_phys)
        insn = "; ".join(c.disassemble())

        self.log(f"IMPDEF exception on: {insn}")

        return False

    def handle_hvc(self, ctx):
        idx = ctx.esr.ISS
        if idx == 0:
            return False

        vector, target = self.vectors[idx]
        if target is None:
            self.log(f"EL1: Exception #{vector} with no target")
            target = 0
            ok = False
        else:
            ctx.elr = target
            ctx.elr_phys = self.p.hv_translate(target, False, False)
            ok = True

        if (vector & 3) == EXC.SYNC:
            spsr = SPSR(self.u.mrs(SPSR_EL12))
            esr = ESR(self.u.mrs(ESR_EL12))
            elr = self.u.mrs(ELR_EL12)
            elr_phys = self.p.hv_translate(elr, False, False)
            sp_el1 = self.u.mrs(SP_EL1)
            sp_el0 = self.u.mrs(SP_EL0)
            far = None
            if esr.EC == ESR_EC.DABORT or esr.EC == ESR_EC.IABORT:
                far = self.u.mrs(FAR_EL12)
                if self.sym(elr)[1] != "com.apple.kernel:_panic_trap_to_debugger":
                    self.log("Page fault")
                    return ok

            self.log(f"EL1: Exception #{vector} ({esr.EC!s}) to {self.addr(target)} from {spsr.M.name}")
            self.log(f"     ELR={self.addr(elr)} (0x{elr_phys:x})")
            self.log(f"     SP_EL1=0x{sp_el1:x} SP_EL0=0x{sp_el0:x}")
            if far is not None:
                self.log(f"     FAR={self.addr(far)}")
            if elr_phys:
                self.u.disassemble_at(elr_phys - 4 * 4, 9 * 4, elr - 4 * 4, elr, sym=self.get_sym)
            if self.sym(elr)[1] == "com.apple.kernel:_panic_trap_to_debugger":
                self.log("Panic! Trying to decode panic...")
                try:
                    self.decode_panic_call()
                except:
                    self.log("Error decoding panic.")
                try:
                    self.bt()
                except:
                    pass
                return False
            if esr.EC == ESR_EC.UNKNOWN:
                instr = self.p.read32(elr_phys)
                if instr == 0xe7ffdeff:
                    self.log("Debugger break! Trying to decode panic...")
                    try:
                        self.decode_dbg_panic()
                    except:
                        self.log("Error decoding panic.")
                    try:
                        self.bt()
                    except:
                        pass
                    return False
                return False
        else:
            elr = self.u.mrs(ELR_EL12)
            self.log(f"Guest: {str(EXC(vector & 3))} at {self.addr(elr)}")

        return ok

    def handle_step(self, ctx):
        # not sure why MDSCR_EL1.SS needs to be disabled here but otherwise
        # if also SPSR.SS=0 no instruction will be executed after eret
        # and instead a debug exception is generated again
        self.u.msr(MDSCR_EL1, MDSCR(MDE=1).value)

        # enable all breakpoints again
        for i, vaddr in enumerate(self._bps):
            if vaddr is None:
                continue
            self.u.msr(DBGBCRn_EL1(i), DBGBCR(E=1, PMC=0b11, BAS=0xf).value)

        # enable all watchpoints again
        for i, wpc in enumerate(self._wpcs):
            self.u.msr(DBGWCRn_EL1(i), wpc)

        return True

    def handle_break(self, ctx):
        # disable all breakpoints so that we don't get stuck
        for i in range(5):
            self.u.msr(DBGBCRn_EL1(i), 0)

        # we'll need to single step to enable these breakpoints again
        self.u.msr(MDSCR_EL1, MDSCR(SS=1, MDE=1).value)
        self.ctx.spsr.SS = 1

        if ctx.elr in self._bp_hooks:
            if self._bp_hooks[ctx.elr](ctx):
                return True

    def handle_watch(self, ctx):
        # disable all watchpoints so that we don't get stuck
        for i in range(len(self._wps)):
            self.u.msr(DBGWCRn_EL1(i), 0)

        # we'll need to single step to enable these watchpoints again
        self.u.msr(MDSCR_EL1, MDSCR(SS=1, MDE=1).value)
        self.ctx.spsr.SS = 1

    def add_hvcall(self, callid, handler):
        self.hvcall_handlers[callid] = handler

    def handle_brk(self, ctx):
        iss = ctx.esr.ISS
        if iss != 0x4242:
            return self._lower()

        # HV call from EL0/1
        callid = ctx.regs[0]
        handler = self.hvcall_handlers.get(callid, None)
        if handler is None:
            self.log(f"Undefined HV call #{callid}")
            return False

        ok = handler(ctx)
        if ok:
            ctx.elr += 4
        return ok

    def handle_dabort(self, ctx):
        insn = self.p.read32(ctx.elr_phys)
        far_phys = self.p.hv_translate(ctx.far, True, False)

        if insn & 0x3b200c00 == 0x38200000:
            page = far_phys & ~0x3fff

            before = self.p.read32(far_phys)
            self.map_hw(page, page, 0x4000)
            r0b = self.ctx.regs[0]
            self.log(f"-ELR={self.ctx.elr:#x} LR={self.ctx.regs[30]:#x}")
            self.step()
            self.log(f"+ELR={self.ctx.elr:#x}")
            r0a = self.ctx.regs[0]
            self.dirty_maps.set(irange(page, 0x4000))
            self.pt_update()
            after = self.p.read32(far_phys)
            self.log(f"Unhandled atomic: @{far_phys:#x} {before:#x} -> {after:#x} | r0={r0b:#x} -> {r0a:#x}")
            return True

        if insn & 0x3f000000 == 0x08000000:
            page = far_phys & ~0x3fff
            before = self.p.read32(far_phys)
            self.map_hw(page, page, 0x4000)
            r0b = self.ctx.regs[0]
            self.log(f"-ELR={self.ctx.elr:#x} LR={self.ctx.regs[30]:#x}")
            self.step()
            self.log(f"+ELR={self.ctx.elr:#x}")
            r0a = self.ctx.regs[0]
            self.dirty_maps.set(irange(page, 0x4000))
            self.pt_update()
            after = self.p.read32(far_phys)
            self.log(f"Unhandled exclusive: @{far_phys:#x} {before:#x} -> {after:#x} | r0={r0b:#x} -> {r0a:#x}")
            return True

    def handle_sync(self, ctx):
        if ctx.esr.EC == ESR_EC.MSR:
            return self.handle_msr(ctx)

        if ctx.esr.EC == ESR_EC.IMPDEF:
            return self.handle_impdef(ctx)

        if ctx.esr.EC == ESR_EC.HVC:
            return self.handle_hvc(ctx)

        if ctx.esr.EC == ESR_EC.SSTEP_LOWER:
            return self.handle_step(ctx)

        if ctx.esr.EC == ESR_EC.BKPT_LOWER:
            return self.handle_break(ctx)

        if ctx.esr.EC == ESR_EC.WATCH_LOWER:
            return self.handle_watch(ctx)

        if ctx.esr.EC == ESR_EC.BRK:
            return self.handle_brk(ctx)

        if ctx.esr.EC == ESR_EC.DABORT_LOWER:
            return self.handle_dabort(ctx)

    def _load_context(self):
        self._info_data = self.iface.readmem(self.exc_info, ExcInfo.sizeof())
        self.ctx = ExcInfo.parse(self._info_data)
        return self.ctx

    def _commit_context(self):
        new_info = ExcInfo.build(self.ctx)
        if new_info != self._info_data:
            self.iface.writemem(self.exc_info, new_info)
            self._info_data = new_info

    def handle_exception(self, reason, code, info):
        self.exc_info = info
        self.exc_reason = reason
        if reason in (START.EXCEPTION_LOWER, START.EXCEPTION):
            code = EXC(code)
        elif reason == START.HV:
            code = HV_EVENT(code)
        self.exc_code = code
        self.is_fault = reason == START.EXCEPTION_LOWER and code in (EXC.SYNC, EXC.SERROR)

        # Nested context switch is handled by the caller
        if self.switching_context:
            self.switching_context = False
            return

        self._in_handler = True

        ctx = self._load_context()
        self.exc_orig_cpu = self.ctx.cpu_id

        handled = False
        user_interrupt = False

        try:
            if reason == START.EXCEPTION_LOWER:
                if code == EXC.SYNC:
                    handled = self.handle_sync(ctx)
                elif code == EXC.FIQ:
                    self.u.msr(CNTV_CTL_EL0, 0)
                    self.u.print_context(ctx, False, sym=self.get_sym)
                    handled = True
            elif reason == START.HV:
                code = HV_EVENT(code)
                if code == HV_EVENT.HOOK_VM:
                    handled = self.handle_vm_hook(ctx)
                elif code == HV_EVENT.USER_INTERRUPT:
                    handled = True
                    user_interrupt = True
        except Exception as e:
            self.log(f"Python exception while handling guest exception:")
            traceback.print_exc()

        if handled:
            ret = EXC_RET.HANDLED
            if self._sigint_pending:
                self.update_pac_mask()
                self.log("User interrupt")
        else:
            self.log(f"Guest exception: {reason.name}/{code.name}")
            self.update_pac_mask()
            self.u.print_context(ctx, self.is_fault, sym=self.get_sym)

        if self._sigint_pending or not handled or user_interrupt:
            self._sigint_pending = False

            signal.signal(signal.SIGINT, self.default_sigint)
            ret = self.run_shell("Entering hypervisor shell", "Returning from exception")
            signal.signal(signal.SIGINT, self._handle_sigint)

            if ret is None:
                ret = EXC_RET.HANDLED

        self.pt_update()

        self._commit_context()
        self.ctx = None
        self.exc_orig_cpu = None
        self.p.exit(ret)

        self._in_handler = False
        if self._sigint_pending:
            self._handle_sigint()

    def handle_bark(self, reason, code, info):
        self._in_handler = True
        self._sigint_pending = False

        signal.signal(signal.SIGINT, self.default_sigint)
        ret = self.run_shell("Entering panic shell", "Exiting")
        signal.signal(signal.SIGINT, self._handle_sigint)

        self.p.exit(0)

    def attach_virtio(self, dev, base=None, irq=None, verbose=False):
        if base is None:
            base = alloc_mmio_base(self.adt, 0x1000)
        if irq is None:
            irq = alloc_aic_irq(self.adt)

        data = dev.config_data
        data_base = self.u.heap.malloc(len(data))
        self.iface.writemem(data_base, data)

        config = VirtioConfig.build({
            "irq": irq,
            "devid": dev.devid,
            "feats": dev.feats,
            "num_qus": dev.num_qus,
            "data": data_base,
            "data_len": len(data),
            "verbose": verbose,
        })

        config_base = self.u.heap.malloc(len(config))
        self.iface.writemem(config_base, config)

        name = None
        for i in range(16):
            n = "/arm-io/virtio%d" % i
            if n not in self.adt:
                name = n
                break
        if name is None:
            raise ValueError("Too many virtios in ADT")

        print(f"Adding {n} @ 0x{base:x}, irq {irq}")

        node = self.adt.create_node(name)
        node.reg = [Container(addr=node.to_bus_addr(base), size=0x1000)]
        node.interrupt_parent = getattr(self.adt["/arm-io/aic"], "AAPL,phandle")
        node.interrupts = (irq,)
        node.compatible = ["virtio,mmio"]

        self.p.hv_map_virtio(base, config_base)
        self.add_tracer(irange(base, 0x1000), "VIRTIO", TraceMode.RESERVED)

        dev.base = base
        dev.hv = self
        self.virtio_devs[base] = dev

    def handle_virtio(self, reason, code, info):
        ctx = self.iface.readstruct(info, ExcInfo)
        self.virtio_ctx = info = self.iface.readstruct(ctx.data, VirtioExcInfo)

        try:
            handled = self.virtio_devs[info.devbase].handle_exc(info)
        except:
            self.log(f"Python exception from within virtio handler")
            traceback.print_exc()
            handled = False

        if not handled:
            signal.signal(signal.SIGINT, self.default_sigint)
            self.run_shell("Entering hypervisor shell", "Returning")
            signal.signal(signal.SIGINT, self._handle_sigint)

        self.p.exit(EXC_RET.HANDLED)

    def skip(self):
        self.ctx.elr += 4
        self.cont()

    def cont(self):
        os.kill(os.getpid(), signal.SIGUSR1)

    def _lower(self):
        if not self.is_fault:
            print("Cannot lower non-fault exception")
            return False

        self.u.msr(ELR_EL12, self.ctx.elr)
        self.u.msr(SPSR_EL12, self.ctx.spsr.value)
        self.u.msr(ESR_EL12, self.ctx.esr.value)
        self.u.msr(FAR_EL12, self.ctx.far)

        exc_off = 0x80 * self.exc_code

        if self.ctx.spsr.M == SPSR_M.EL0t:
            exc_off += 0x400
        elif self.ctx.spsr.M == SPSR_M.EL1t:
            pass
        elif self.ctx.spsr.M == SPSR_M.EL1h:
            exc_off += 0x200
        else:
            print(f"Unknown exception level {self.ctx.spsr.M}")
            return False

        self.ctx.spsr.M = SPSR_M.EL1h
        self.ctx.spsr.D = 1
        self.ctx.spsr.A = 1
        self.ctx.spsr.I = 1
        self.ctx.spsr.F = 1
        self.ctx.elr = self.u.mrs(VBAR_EL12) + exc_off

        return True

    def lower(self, step=False):
        self.cpu() # Return to exception CPU

        if not self._lower():
            return
        elif step:
            self.step()
        else:
            self.cont()

    def step(self):
        self.u.msr(MDSCR_EL1, MDSCR(SS=1, MDE=1).value)
        self.ctx.spsr.SS = 1
        self.p.hv_pin_cpu(self.ctx.cpu_id)
        self._switch_context()
        self.p.hv_pin_cpu(0xffffffffffffffff)

    def _switch_context(self, exit=EXC_RET.HANDLED):
        # Flush current CPU context out to HV
        self._commit_context()
        self.exc_info = None
        self.ctx = None

        self.switching_context = True
        # Exit out of the proxy
        self.p.exit(exit)
        # Wait for next proxy entry
        self.iface.wait_and_handle_boot()
        if self.switching_context:
            raise Exception(f"Failed to switch context")

        # Fetch new context
        self._load_context()

    def cpu(self, cpu=None):
        if cpu is None:
            cpu = self.exc_orig_cpu
        if cpu == self.ctx.cpu_id:
            return

        if not self.p.hv_switch_cpu(cpu):
            raise ValueError(f"Invalid or inactive CPU #{cpu}")

        self._switch_context()
        if self.ctx.cpu_id != cpu:
            raise Exception(f"Switching to CPU #{cpu} but ended on #{self.ctx.cpu_id}")

    def add_hw_bp(self, vaddr, hook=None):
        if None not in self._bps:
            raise ValueError("Cannot add more HW breakpoints")

        i = self._bps.index(None)
        cpu_id = self.ctx.cpu_id
        try:
            for cpu in self.cpus():
                self.u.msr(DBGBCRn_EL1(i), DBGBCR(E=1, PMC=0b11, BAS=0xf).value)
                self.u.msr(DBGBVRn_EL1(i), vaddr)
        finally:
            self.cpu(cpu_id)
        self._bps[i] = vaddr
        if hook is not None:
            self._bp_hooks[vaddr] = hook

    def remove_hw_bp(self, vaddr):
        idx = self._bps.index(vaddr)
        self._bps[idx] = None
        cpu_id = self.ctx.cpu_id
        try:
            for cpu in self.cpus():
                self.u.msr(DBGBCRn_EL1(idx), 0)
                self.u.msr(DBGBVRn_EL1(idx), 0)
        finally:
            self.cpu(cpu_id)
        if vaddr in self._bp_hooks:
            del self._bp_hooks[vaddr]

    def add_sym_bp(self, name, hook=None):
        return self.add_hw_bp(self.resolve_symbol(name), hook=hook)

    def remove_sym_bp(self, name):
        return self.remove_hw_bp(self.resolve_symbol(name))

    def clear_hw_bps(self):
        for vaddr in self._bps:
            self.remove_hw_bp(vaddr)

    def add_hw_wp(self, vaddr, bas, lsc):
        for i, i_vaddr in enumerate(self._wps):
            if i_vaddr is None:
                self._wps[i] = vaddr
                self._wpcs[i] = DBGWCR(E=1, PAC=0b11, BAS=bas, LSC=lsc).value
                cpu_id = self.ctx.cpu_id
                try:
                    for cpu in self.cpus():
                        self.u.msr(DBGWCRn_EL1(i), self._wpcs[i])
                        self.u.msr(DBGWVRn_EL1(i), vaddr)
                finally:
                    self.cpu(cpu_id)
                return
        raise ValueError("Cannot add more HW watchpoints")

    def get_wp_bas(self, vaddr):
        for i, i_vaddr in enumerate(self._wps):
            if i_vaddr == vaddr:
                return self._wpcs[i].BAS

    def remove_hw_wp(self, vaddr):
        idx = self._wps.index(vaddr)
        self._wps[idx] = None
        self._wpcs[idx] = 0
        cpu_id = self.ctx.cpu_id
        try:
            for cpu in self.cpus():
                self.u.msr(DBGWCRn_EL1(idx), 0)
                self.u.msr(DBGWVRn_EL1(idx), 0)
        finally:
            self.cpu(cpu_id)

    def exit(self):
        os.kill(os.getpid(), signal.SIGUSR2)

    def reboot(self):
        print("Hard rebooting the system")
        self.p.reboot()
        sys.exit(0)

    def hvc(self, arg):
        assert 0 <= arg <= 0xffff
        return 0xd4000002 | (arg << 5)

    def decode_dbg_panic(self):
        xnutools.decode_debugger_state(self.u, self.ctx)

    def decode_panic_call(self):
        xnutools.decode_panic_call(self.u, self.ctx)

    def context(self):
        f = f" (orig: #{self.exc_orig_cpu})" if self.ctx.cpu_id != self.exc_orig_cpu else ""
        print(f"  == On CPU #{self.ctx.cpu_id}{f} ==")
        print(f"  Reason: {self.exc_reason.name}/{self.exc_code.name}")
        self.u.print_context(self.ctx, self.is_fault, sym=self.get_sym)

    def bt(self, frame=None, lr=None):
        if frame is None:
            frame = self.ctx.regs[29]
        if lr is None:
            lr = self.unpac(self.ctx.elr) + 4

        print("Stack trace:")
        frames = set()
        while frame:
            if frame in frames:
                print("Stack loop detected!")
                break
            frames.add(frame)
            print(f" - {self.addr(lr - 4)}")
            lrp = self.p.hv_translate(frame + 8)
            fpp = self.p.hv_translate(frame)
            if not fpp:
                break
            lr = self.unpac(self.p.read64(lrp))
            frame = self.p.read64(fpp)

    def cpus(self):
        for i in sorted(self.started_cpus):
            self.cpu(i)
            yield i

    def patch_exception_handling(self):
        if self.ctx.cpu_id != 0:
            return

        if self.want_vbar is not None:
            vbar = self.want_vbar
        else:
            vbar = self.u.mrs(VBAR_EL12)

        if vbar == self.vbar_el1:
            return

        if vbar == 0:
            return

        if self.u.mrs(SCTLR_EL12) & 1:
            vbar_phys = self.p.hv_translate(vbar, False, False)
            if vbar_phys == 0:
                self.log(f"VBAR vaddr 0x{vbar:x} translation failed!")
                if self.vbar_el1 is not None:
                    self.want_vbar = vbar
                    self.u.msr(VBAR_EL12, self.vbar_el1)
                return
        else:
            if vbar & (1 << 63):
                self.log(f"VBAR vaddr 0x{vbar:x} without translation enabled")
                if self.vbar_el1 is not None:
                    self.want_vbar = vbar
                    self.u.msr(VBAR_EL12, self.vbar_el1)
                return

            vbar_phys = vbar

        if self.want_vbar is not None:
            self.want_vbar = None
            self.u.msr(VBAR_EL12, vbar)

        self.log(f"New VBAR paddr: 0x{vbar_phys:x}")

        #for i in range(16):
        for i in [0, 3, 4, 7, 8, 11, 12, 15]:
            idx = 0
            addr = vbar_phys + 0x80 * i
            orig = self.p.read32(addr)
            if (orig & 0xfc000000) != 0x14000000:
                self.log(f"Unknown vector #{i}:\n")
                self.u.disassemble_at(addr, 16)
            else:
                idx = len(self.vectors)
                delta = orig & 0x3ffffff
                if delta == 0:
                    target = None
                    self.log(f"Vector #{i}: Loop\n")
                else:
                    target = (delta << 2) + vbar + 0x80 * i
                    self.log(f"Vector #{i}: 0x{target:x}\n")
                self.vectors.append((i, target))
                self.u.disassemble_at(addr, 16)
            self.p.write32(addr, self.hvc(idx))

        self.p.dc_cvau(vbar_phys, 0x800)
        self.p.ic_ivau(vbar_phys, 0x800)

        self.vbar_el1 = vbar

    def set_logfile(self, fd):
        self.print_tracer.log_file = fd

    def init(self):
        self.adt = load_adt(self.u.get_adt())
        self.iodev = self.p.iodev_whoami()
        self.tba = self.u.ba.copy()
        self.device_addr_tbl = self.adt.build_addr_lookup()
        self.print_tracer = trace.PrintTracer(self, self.device_addr_tbl)

        # disable unused USB iodev early so interrupts can be reenabled in hv_init()
        for iodev in IODEV:
            if iodev >= IODEV.USB0 and iodev != self.iodev:
                print(f"Disable iodev {iodev!s}")
                self.p.iodev_set_usage(iodev, 0)

        print("Initializing hypervisor over iodev %s" % self.iodev)
        self.p.hv_init()

        self.iface.set_handler(START.EXCEPTION_LOWER, EXC.SYNC, self.handle_exception)
        self.iface.set_handler(START.EXCEPTION_LOWER, EXC.IRQ, self.handle_exception)
        self.iface.set_handler(START.EXCEPTION_LOWER, EXC.FIQ, self.handle_exception)
        self.iface.set_handler(START.EXCEPTION_LOWER, EXC.SERROR, self.handle_exception)
        self.iface.set_handler(START.EXCEPTION, EXC.FIQ, self.handle_exception)
        self.iface.set_handler(START.HV, HV_EVENT.USER_INTERRUPT, self.handle_exception)
        self.iface.set_handler(START.HV, HV_EVENT.HOOK_VM, self.handle_exception)
        self.iface.set_handler(START.HV, HV_EVENT.VTIMER, self.handle_exception)
        self.iface.set_handler(START.HV, HV_EVENT.WDT_BARK, self.handle_bark)
        self.iface.set_handler(START.HV, HV_EVENT.CPU_SWITCH, self.handle_exception)
        self.iface.set_handler(START.HV, HV_EVENT.VIRTIO, self.handle_virtio)
        self.iface.set_handler(START.HV, HV_EVENT.PANIC, self.handle_bark)
        self.iface.set_event_handler(EVENT.MMIOTRACE, self.handle_mmiotrace)
        self.iface.set_event_handler(EVENT.IRQTRACE, self.handle_irqtrace)

        # Map MMIO ranges as HW by default
        for r in self.adt["/arm-io"].ranges:
            print(f"Mapping MMIO range: {r.parent_addr:#x} .. {r.parent_addr + r.size:#x}")
            self.add_tracer(irange(r.parent_addr, r.size), "HW", TraceMode.OFF)

        hcr = HCR(self.u.mrs(HCR_EL2))
        if self.novm:
            hcr.VM = 0
            hcr.AMO = 0
        else:
            hcr.TACR = 1
        hcr.TIDCP = 0
        hcr.TVM = 0
        hcr.FMO = 1
        hcr.IMO = 0
        hcr.TTLBOS = 1
        self.u.msr(HCR_EL2, hcr.value)

        # Trap dangerous things
        hacr = HACR(0)
        if not self.novm:
            #hacr.TRAP_CPU_EXT = 1
            #hacr.TRAP_SPRR = 1
            #hacr.TRAP_GXF = 1
            hacr.TRAP_CTRR = 1
            hacr.TRAP_EHID = 1
            hacr.TRAP_HID = 1
            hacr.TRAP_ACC = 1
            hacr.TRAP_IPI = 1
            hacr.TRAP_SERROR_INFO = 1 # M1RACLES mitigation
            hacr.TRAP_PM = 1
        self.u.msr(HACR_EL2, hacr.value)

        # enable and route debug exceptions to EL2
        mdcr = MDCR(0)
        mdcr.TDE = 1
        mdcr.TDA = 1
        mdcr.TDOSA = 1
        mdcr.TDRA = 1
        self.u.msr(MDCR_EL2, mdcr.value)
        self.u.msr(MDSCR_EL1, MDSCR(MDE=1).value)

        # Enable AMX
        amx_ctl = AMX_CONFIG(self.u.mrs(AMX_CONFIG_EL1))
        amx_ctl.EN_EL1 = 1
        self.u.msr(AMX_CONFIG_EL1, amx_ctl.value)

        # Set guest AP keys
        self.u.msr(VMKEYLO_EL2, 0x4E7672476F6E6147)
        self.u.msr(VMKEYHI_EL2, 0x697665596F755570)
        self.u.msr(APSTS_EL12, 1)

        self.map_vuart()

        # ACTLR depends on the CPU part
        part = MIDR(self.u.mrs(MIDR_EL1)).PART
        actlr_el12 = ACTLR_EL12 if part >= MIDR_PART.T8110_BLIZZARD else ACTLR_EL12_PRE

        actlr = ACTLR(self.u.mrs(actlr_el12))
        actlr.EnMDSB = 1
        self.u.msr(actlr_el12, actlr.value)

        self.setup_adt()

    def map_vuart(self):
        node = base = self.adt["/arm-io/uart0"]
        base = node.get_reg(0)[0]

        zone = irange(base, 0x4000)
        irq = node.interrupts[0]
        self.p.hv_map_vuart(base, irq, self.iodev)
        self.add_tracer(zone, "VUART", TraceMode.RESERVED)

    def map_essential(self):
        # Things we always map/take over, for the hypervisor to work
        _pmgr = {}

        def wh(base, off, data, width):
            self.log(f"PMGR W {base:x}+{off:x}:{width} = 0x{data:x}: Dangerous write")
            self.p.mask32(base + off, 0x3ff, (data | 0xf) & ~(0x80000400))
            _pmgr[base + off] = (data & 0xfffffc0f) | ((data & 0xf) << 4)

        def rh(base, off, width):
            data = self.p.read32(base + off)
            ret = _pmgr.setdefault(base + off, data)
            self.log(f"PMGR R {base:x}+{off:x}:{width} = 0x{data:x} -> 0x{ret:x}")
            return ret

        atc = f"ATC{self.iodev - IODEV.USB0}_USB"
        atc_aon = f"ATC{self.iodev - IODEV.USB0}_USB_AON"

        hook_devs = ["UART0", atc, atc_aon]

        pmgr = self.adt["/arm-io/pmgr"]
        dev_by_name = {dev.name: dev for dev in pmgr.devices}
        dev_by_id = {dev.id: dev for dev in pmgr.devices}

        pmgr_hooks = []

        def hook_pmgr_dev(dev):
            ps = pmgr.ps_regs[dev.psreg]
            if dev.psidx or dev.psreg:
                addr = pmgr.get_reg(ps.reg)[0] + ps.offset + dev.psidx * 8
                pmgr_hooks.append(addr)
                for idx in dev.parents:
                    if idx in dev_by_id:
                        hook_pmgr_dev(dev_by_id[idx])

        for name in hook_devs:
            dev = dev_by_name[name]
            hook_pmgr_dev(dev)

        pmgr0_start = pmgr.get_reg(0)[0]

        for addr in pmgr_hooks:
            self.map_hook(addr, 4, write=wh, read=rh)
            #TODO : turn into a real tracer
            self.add_tracer(irange(addr, 4), "PMGR HACK", TraceMode.RESERVED)

        pg_overrides = {
            0x23d29c05c: 0xc000000,
            0x23d29c044: 0xc000000,
        }

        for addr in pg_overrides:
            self.map_hook(addr, 4, read=lambda base, off, width: pg_overrides[base + off])
            self.add_tracer(irange(addr, 4), "PMGR HACK", TraceMode.RESERVED)

        cpu_hack = [
            # 0x210e20020,
            # 0x211e20020,
            # 0x212e20020,
        ]

        def wh(base, off, data, width):
            if isinstance(data, list):
                data = data[0]
            self.log(f"CPU W {base:x}+{off:x}:{width} = 0x{data:x}: Dangerous write")

        for addr in cpu_hack:
            self.map_hook(addr, 8, write=wh)
            self.add_tracer(irange(addr, 8), "CPU HACK", TraceMode.RESERVED)

        def cpu_state_rh(base, off, width):
            data = ret = self.p.read64(base + off)
            die = base // 0x20_0000_0000
            cluster = (base >> 24) & 0xf
            cpu = (base >> 20) & 0xf
            for i, j in self.started_cpus.items():
                if j == (die, cluster, cpu):
                    break
            else:
                ret &= ~0xff
            self.log(f"CPU STATE R {base:x}+{off:x}:{width} = 0x{data:x} -> 0x{ret:x}")
            return ret

        def cpustart_wh(base, off, data, width):
            self.log(f"CPUSTART W {base:x}+{off:x}:{width} = 0x{data:x}")
            if off >= 8:
                assert width == 32
                die = base // 0x20_0000_0000
                cluster = (off - 8) // 4
                for i in range(32):
                    if data & (1 << i):
                        self.start_secondary(die, cluster, i)
                        cpu_state = 0x210050100 | (die << 27) | (cluster << 24) | (i << 20)
                        self.map_hook(cpu_state, 8, read=cpu_state_rh)
                        self.add_tracer(irange(addr, 8), "CPU STATE HACK", TraceMode.RESERVED)

        die_count = self.adt["/arm-io"].die_count if hasattr(self.adt["/arm-io"], "die-count") else 1

        for die in range(0, die_count):
            chip_id = self.u.adt["/chosen"].chip_id
            if chip_id in (0x8103, 0x6000, 0x6001, 0x6002):
                cpu_start = 0x54000 + die * 0x20_0000_0000
            elif chip_id in (0x8112, 0x8122, 0x6030):
                cpu_start = 0x34000 + die * 0x20_0000_0000
            elif chip_id in (0x6020, 0x6021, 0x6022):
                cpu_start = 0x28000 + die * 0x20_0000_0000
            elif chip_id in (0x6031,):
                cpu_start = 0x88000 + die * 0x20_0000_0000
            else:
                self.log("CPUSTART unknown for this SoC!")
                break

            zone = irange(pmgr0_start + cpu_start, 0x20)
            self.map_hook(pmgr0_start + cpu_start, 0x20, write=cpustart_wh)
            self.add_tracer(zone, "CPU_START", TraceMode.RESERVED)

    def start_secondary(self, die, cluster, cpu):
        self.log(f"Starting guest secondary {die}:{cluster}:{cpu}")

        for node in list(self.adt["cpus"]):
            if ((die << 11) | (cluster << 8) | cpu) == node.reg:
                break
        else:
            self.log("CPU not found!")
            return

        entry = self.p.read64(node.cpu_impl_reg[0]) & 0xfffffffffff
        index = node.cpu_id
        self.log(f" CPU #{index}: RVBAR = {entry:#x}")

        self.sysreg[index] = {}
        self.started_cpus[index] = (die, cluster, cpu)
        self.p.hv_start_secondary(index, entry)

    def setup_adt(self):
        self.adt["product"].product_name += " on m1n1 hypervisor"
        self.adt["product"].product_description += " on m1n1 hypervisor"
        soc_name = "Virtual " + self.adt["product"].product_soc_name + " on m1n1 hypervisor"
        self.adt["product"].product_soc_name = soc_name

        if self.iodev >= IODEV.USB0:
            idx = self.iodev - IODEV.USB0
            for prefix in ("/arm-io/dart-usb%d",
                           "/arm-io/atc-phy%d",
                           "/arm-io/usb-drd%d",
                           "/arm-io/acio%d",
                           "/arm-io/acio-cpu%d",
                           "/arm-io/dart-acio%d",
                           "/arm-io/apciec%d",
                           "/arm-io/dart-apciec%d",
                           "/arm-io/apciec%d-piodma",
                           "/arm-io/i2c0/hpmBusManager/hpm%d",
                           "/arm-io/nub-spmi-a0/hpm%d",
                           "/arm-io/atc%d-dpxbar",
                           "/arm-io/atc%d-dpphy",
                           "/arm-io/atc%d-dpin0",
                           "/arm-io/atc%d-dpin1",
                           "/arm-io/atc-phy%d",
                          ):
                name = prefix % idx
                print(f"Removing ADT node {name}")
                try:
                    del self.adt[name]
                except KeyError:
                    pass

        if self.wdt_cpu is not None:
            name = f"/cpus/cpu{self.wdt_cpu}"
            print(f"Removing ADT node {name}")
            try:
                del self.adt[name]
            except KeyError:
                pass

        if not self.smp:
            for cpu in list(self.adt["cpus"]):
                if cpu.state != "running":
                    print(f"Removing ADT node {cpu._path}")
                    try:
                        del self.adt["cpus"][cpu.name]
                    except KeyError:
                        pass

    def set_bootargs(self, boot_args):
        if "-v" in boot_args.split():
            self.tba.video.display = 0
        else:
            self.tba.video.display = 1
        print(f"Setting boot arguments to {boot_args!r}")
        self.tba.cmdline = boot_args

    def unmap_carveouts(self):
        print(f"Unmapping TZ carveouts...")
        carveout_p = self.p.mcc_get_carveouts()
        while True:
            base = self.p.read64(carveout_p)
            size = self.p.read64(carveout_p + 8)
            if not base:
                break
            print(f"  Unmap [{base:#x}..{base + size - 1:#x}]")
            self.del_tracer(irange(base, size), "RAM-LOW")
            self.del_tracer(irange(base, size), "RAM-HIGH")
            carveout_p += 16

    def enable_time_stealing(self):
        self.p.hv_set_time_stealing(True)

    def disable_time_stealing(self):
        self.p.hv_set_time_stealing(False)


    def load_raw(self, image, entryoffset=0x800, use_xnu_symbols=False, vmin=0):
        sepfw_start, sepfw_length = self.u.adt["chosen"]["memory-map"].SEPFW
        tc_start, tc_size = self.u.adt["chosen"]["memory-map"].TrustCache
        if hasattr(self.u.adt["chosen"]["memory-map"], "preoslog"):
            preoslog_start, preoslog_size = self.u.adt["chosen"]["memory-map"].preoslog
        else:
            preoslog_size = 0

        image_size = align(len(image))
        sepfw_off = image_size
        image_size += align(sepfw_length)
        preoslog_off = image_size
        image_size += preoslog_size
        self.bootargs_off = image_size
        bootargs_size = 0x4000
        image_size += bootargs_size

        print(f"Total region size: 0x{image_size:x} bytes")

        self.phys_base = phys_base = guest_base = self.u.heap_top
        self.ram_base = self.phys_base & ~0xffffffff
        self.ram_size = self.u.ba.mem_size_actual
        guest_base += 16 << 20 # ensure guest starts within a 16MB aligned region of mapped RAM
        self.adt_base = guest_base
        guest_base += align(self.u.ba.devtree_size)
        tc_base = guest_base
        guest_base += align(tc_size)
        self.guest_base = guest_base
        mem_top = self.u.ba.phys_base + self.u.ba.mem_size
        mem_size = mem_top - phys_base

        print(f"Physical memory: 0x{phys_base:x} .. 0x{mem_top:x}")
        print(f"Guest region start: 0x{guest_base:x}")
        
        self.entry = guest_base + entryoffset

        print(f"Mapping guest physical memory...")
        self.add_tracer(irange(self.ram_base, self.u.ba.phys_base - self.ram_base), "RAM-LOW", TraceMode.OFF)
        self.add_tracer(irange(phys_base, self.u.ba.mem_size_actual - phys_base + self.ram_base), "RAM-HIGH", TraceMode.OFF)
        self.unmap_carveouts()

        print(f"Loading kernel image (0x{len(image):x} bytes)...")
        self.u.compressed_writemem(guest_base, image, True)
        self.p.dc_cvau(guest_base, len(image))
        self.p.ic_ivau(guest_base, len(image))

        print(f"Copying SEPFW (0x{sepfw_length:x} bytes)...")
        self.p.memcpy8(guest_base + sepfw_off, sepfw_start, sepfw_length)

        print(f"Copying TrustCache (0x{tc_size:x} bytes)...")
        self.p.memcpy8(tc_base, tc_start, tc_size)

        if hasattr(self.u.adt["chosen"]["memory-map"], "preoslog"):
            print(f"Copying preoslog (0x{preoslog_size:x} bytes)...")
            self.p.memcpy8(guest_base + preoslog_off, preoslog_start, preoslog_size)

        print(f"Adjusting addresses in ADT...")
        self.adt["chosen"]["memory-map"].SEPFW = (guest_base + sepfw_off, sepfw_length)
        self.adt["chosen"]["memory-map"].TrustCache = (tc_base, tc_size)
        self.adt["chosen"]["memory-map"].DeviceTree = (self.adt_base, align(self.u.ba.devtree_size))
        self.adt["chosen"]["memory-map"].BootArgs = (guest_base + self.bootargs_off, bootargs_size)
        if hasattr(self.u.adt["chosen"]["memory-map"], "preoslog"):
            self.adt["chosen"]["memory-map"].preoslog = (guest_base + preoslog_off, preoslog_size)
        if hasattr(self.u.adt["chosen"]["memory-map"], "Kernel_mach__header"):
            self.adt["chosen"]["memory-map"].Kernel_mach__header = (guest_base, 0)

        def remove_oslog(node):
            names = node.segment_names.split(";")
            try:
                idx = names.index("__OS_LOG")
            except ValueError:
                return
            print(f"Removing __OS_LOG from {node.name}")
            names = names[:idx] + names[idx + 1:]
            node.segment_names = ";".join(names)
            node.segment_ranges = node.segment_ranges[:idx * 32] + node.segment_ranges[32 + idx * 32: ]

        for node in self.adt["/arm-io"]:
            if hasattr(node, "segment_names"):
                remove_oslog(node)
            for nub in node:
                if hasattr(nub, "segment_names"):
                    remove_oslog(nub)

        print(f"Setting up bootargs at 0x{guest_base + self.bootargs_off:x}...")

        self.tba.mem_size = mem_size
        self.tba.phys_base = phys_base
        self.tba.virt_base = 0xfffffe0010000000 + (phys_base & (32 * 1024 * 1024 - 1))
        self.tba.devtree = self.adt_base - phys_base + self.tba.virt_base
        self.tba.top_of_kernel_data = guest_base + image_size

        if use_xnu_symbols == True:
            self.sym_offset = vmin - guest_base + self.tba.phys_base - self.tba.virt_base

        if self.tba.revision <= 1:
            self.iface.writemem(guest_base + self.bootargs_off, BootArgs_r1.build(self.tba))
        elif self.tba.revision == 2:
            self.iface.writemem(guest_base + self.bootargs_off, BootArgs_r2.build(self.tba))
        elif self.tba.revision == 3:
            self.iface.writemem(guest_base + self.bootargs_off, BootArgs_r3.build(self.tba))

        print("Setting secondary CPU RVBARs...")
        rvbar = self.entry & ~0xfff
        for cpu in self.adt["cpus"]:
            if cpu.state == "running":
                continue
            addr, size = cpu.cpu_impl_reg
            print(f"  {cpu.name}: [0x{addr:x}] = 0x{rvbar:x}")
            self.p.write64(addr, rvbar)

    def _load_macho_symbols(self):
        self.symbol_dict = self.macho.symbols
        self.symbols = [(v, k) for k, v in self.macho.symbols.items()]
        self.symbols.sort()

    def load_macho(self, data, symfile=None):
        if isinstance(data, str):
            data = open(data, "rb")

        self.xnu_mode = True

        self.macho = macho = MachO(data)
        if symfile is not None:
            if isinstance(symfile, str):
                symfile = open(symfile, "rb")
            syms = MachO(symfile)
            macho.add_symbols("com.apple.kernel", syms)

        self._load_macho_symbols()

        def load_hook(data, segname, size, fileoff, dest):
            if segname != "__TEXT_EXEC":
                return data

            print(f"Patching segment {segname}...")

            a = array.array("I", data)

            output = []

            p = 0
            while (p := data.find(b"\x20\x00", p)) != -1:
                if (p & 3) != 2:
                    p += 1
                    continue

                opcode = a[p // 4]
                inst = self.hvc((opcode & 0xffff))
                off = fileoff + (p & ~3)
                if off >= 0xbfcfc0:
                    print(f"  0x{off:x}: 0x{opcode:04x} -> hvc 0x{opcode:x} (0x{inst:x})")
                    a[p // 4] = inst
                p += 4

            print("Done.")
            return a.tobytes()

        #image = macho.prepare_image(load_hook)
        image = macho.prepare_image()
        self.load_raw(image, entryoffset=(macho.entry - macho.vmin), use_xnu_symbols=self.xnu_mode and symfile is not None, vmin=macho.vmin)

    def update_pac_mask(self):
        tcr = TCR(self.u.mrs(TCR_EL12))
        valid_bits = (1 << (64 - tcr.T1SZ)) - 1
        self.pac_mask = 0xffffffffffffffff & ~valid_bits
        valid_bits = (1 << (64 - tcr.T0SZ)) - 1
        self.user_pac_mask = 0xffffffffffffffff & ~valid_bits

    def unpac(self, v):
        if v & (1 << 55):
            return v | self.pac_mask
        else:
            return v & ~self.user_pac_mask

    def load_system_map(self, path):
        # Assume Linux
        self.sym_offset = 0
        self.xnu_mode = False
        self.symbols = []
        self.symbol_dict = {}
        with open(path) as fd:
            for line in fd.readlines():
                addr, t, name = line.split()
                addr = int(addr, 16)
                self.symbols.append((addr, name))
                self.symbol_dict[name] = addr
        self.symbols.sort()

    def add_kext_symbols(self, kext, demangle=False):
        info_plist = plistlib.load(open(f"{kext}/Contents/Info.plist", "rb"))
        identifier = info_plist["CFBundleIdentifier"]
        name = info_plist["CFBundleName"]
        macho = MachO(open(f"{kext}/Contents/MacOS/{name}", "rb"))
        self.macho.add_symbols(identifier, macho, demangle=demangle)
        self._load_macho_symbols()

    def _handle_sigint(self, signal=None, stack=None):
        self._sigint_pending = True
        self.interrupt()

    def interrupt(self):
        if self._in_handler:
            return

        # Kick the proxy to break out of the hypervisor
        self.iface.dev.write(b"!")

    def run_script(self, path):
        new_locals = runpy.run_path(path, init_globals=self.shell_locals, run_name="<hv_script>")
        self.shell_locals.clear()
        self.shell_locals.update(new_locals)

    def run_code(self, code):
        exec(code, self.shell_locals)

    def start(self):
        print("Disabling other iodevs...")
        for iodev in IODEV:
            if iodev != self.iodev:
                print(f" - {iodev!s}")
                self.p.iodev_set_usage(iodev, 0)

        print("Doing essential MMIO remaps...")
        self.map_essential()

        print("Updating page tables...")
        self.pt_update()

        adt_blob = self.adt.build()
        print(f"Uploading ADT (0x{len(adt_blob):x} bytes)...")
        self.iface.writemem(self.adt_base, adt_blob)

        print("Improving logo...")
        self.p.fb_improve_logo()

        print("Shutting down framebuffer...")
        self.p.fb_shutdown(True)

        print("Enabling SPRR...")
        self.u.msr(SPRR_CONFIG_EL1, 1)

        print("Enabling GXF...")
        self.u.msr(GXF_CONFIG_EL1, 1)

        print(f"Jumping to entrypoint at 0x{self.entry:x}")

        self.iface.dev.timeout = None
        self.default_sigint = signal.signal(signal.SIGINT, self._handle_sigint)

        set_sigquit_stackdump_handler()

        if self.wdt_cpu is not None:
            self.p.hv_wdt_start(self.wdt_cpu)
        # Does not return

        self.started = True
        for cpu_node in list(self.adt["cpus"]):
            if cpu_node.state == "running":
                break
        self.started_cpus[cpu_node.cpu_id] = (getattr(cpu_node, "die_id", 0), cpu_node.cluster_id, cpu_node.cpu_id)
        self.sysreg[cpu_node.cpu_id] = {}
        self.p.hv_start(self.entry, self.guest_base + self.bootargs_off)

from .. import trace

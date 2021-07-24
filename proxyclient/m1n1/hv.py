# SPDX-License-Identifier: MIT
import sys, traceback, struct, array, bisect, os, signal, runpy
from construct import *
from enum import Enum, IntEnum, IntFlag

from .asm import ARMAsm
from .tgtypes import *
from .proxy import IODEV, START, EVENT, EXC, EXC_RET, ExcInfo
from .utils import *
from .sysreg import *
from .macho import MachO
from .adt import load_adt
from . import xnutools, shell

__all__ = ["HV"]

class MMIOTraceFlags(Register32):
    WIDTH = 4, 0
    WRITE = 5
    MULTI = 6

EvtMMIOTrace = Struct(
    "flags" / RegAdapter(MMIOTraceFlags),
    "reserved" / Int32ul,
    "pc" / Hex(Int64ul),
    "addr" / Hex(Int64ul),
    "data" / Hex(Int64ul),
)

EvtIRQTrace = Struct(
    "flags" / Int32ul,
    "type" / Hex(Int16ul),
    "num" / Int16ul,
)

class HV_EVENT(IntEnum):
    HOOK_VM = 1
    VTIMER = 2
    USER_INTERRUPT = 3
    WDT_BARK = 4

VMProxyHookData = Struct(
    "flags" / RegAdapter(MMIOTraceFlags),
    "id" / Int32ul,
    "addr" / Hex(Int64ul),
    "data" / Array(2, Hex(Int64ul)),
)

class TraceMode(IntEnum):
    OFF = 0
    ASYNC = 1
    UNBUF = 2
    SYNC = 3
    HOOK = 4
    RESERVED = 5

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
        ACTLR_EL1: ACTLR_EL12,
        AMX_CTL_EL1: AMX_CTL_EL12,
        SPRR_CONFIG_EL1: SPRR_CONFIG_EL12,
        SPRR_PERM_EL1: SPRR_PERM_EL12,
        SPRR_PERM_EL0: SPRR_PERM_EL02,
        SPRR_UNK1_EL1: SPRR_UNK1_EL12,
        SPRR_UMASK0_EL1: SPRR_UMASK0_EL12,
        APCTL_EL1: APCTL_EL12,
        APSTS_EL1: APSTS_EL12,
        KERNELKEYLO_EL1: KERNELKEYLO_EL12,
        KERNELKEYHI_EL1: KERNELKEYHI_EL12,
        GXF_CONFIG_EL1: GXF_CONFIG_EL12,
        GXF_ABORT_EL1: GXF_ABORT_EL12,
        GXF_ENTER_EL1: GXF_ENTER_EL12,
    }

    AIC_EVT_TYPE_HW = 1
    IRQTRACE_IRQ = 1

    def __init__(self, iface, proxy, utils):
        self.iface = iface
        self.p = proxy
        self.u = utils
        self.pac_mask = self.PAC_MASK
        self.vbar_el1 = None
        self.want_vbar = None
        self.vectors = [None]
        self._stepping = False
        self._bps = [None, None, None, None, None]
        self.sym_offset = 0
        self.symbols = []
        self.sysreg = {}
        self.novm = False
        self._in_handler = False
        self._sigint_pending = False
        self.vm_hooks = [None]
        self.interrupt_map = {}
        self.mmio_maps = DictRangeMap()
        self.dirty_maps = BoolRangeMap()
        self.tracer_caches = {}
        self.shell_locals = {}
        self.xnu_mode = False
        self._update_shell_locals()

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

    def unmap(self, ipa, size):
        assert self.p.hv_map(ipa, 0, size, 0) >= 0

    def map_hw(self, ipa, pa, size):
        '''map_hw(ipa, pa, size) : map intermediate PA (Physical Address) to actual PA'''
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
        self.map_hook_idx(ipa, size, index, read is not None, write is not None, kwargs)

    def map_hook_idx(self, ipa, size, index, read=False, write=False, kwargs={}):
        if read:
            if write:
                t = self.SPTE_PROXY_HOOK_RW
            else:
                t = self.SPTE_PROXY_HOOK_R
        elif write:
            t = self.SPTE_PROXY_HOOK_W
        else:
            assert False

        assert self.p.hv_map(ipa, (index << 2) | t, size, 0) >= 0

    def trace_irq(self, device, num, count, flags):
        for n in range(num, num + count):
            if flags & self.IRQTRACE_IRQ:
                self.interrupt_map[n] = device
            else:
                self.interrupt_map.pop(n, None)

        start, size = self.adt["/arm-io/aic"].get_reg(0)
        zone = irange(start, 0x4000)
        if len(self.interrupt_map):
            self.add_tracer(zone, "AIC_IRQ", TraceMode.RESERVED)
        else:
            self.del_tracer(zone, "AIC_IRQ", TraceMode.RESERVED)

        assert self.p.hv_trace_irq(self.AIC_EVT_TYPE_HW, num, count, flags) > 0

    def add_tracer(self, zone, ident, mode=TraceMode.ASYNC, read=None, write=None, **kwargs):
        assert mode in (TraceMode.RESERVED, TraceMode.OFF) or read or write
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

    def trace_range(self, zone, mode=TraceMode.ASYNC):
        if mode is True:
            mode = TraceMode.ASYNC
        if mode and mode != TraceMode.OFF:
            self.add_tracer(zone, "PrintTracer", mode, self.print_tracer.event_mmio, self.print_tracer.event_mmio)
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
            for mzone, maps in self.mmio_maps.overlaps(zone):
                if mzone.stop <= top:
                    continue
                top = mzone.stop
                if not maps:
                    continue
                maps = sorted(maps.values(), reverse=True)
                mode, ident, read, write, kwargs = maps[0]

                need_read = any(m[2] for m in maps)
                need_write = any(m[3] for m in maps)

                if mode == TraceMode.RESERVED:
                    print(f"PT[{mzone.start:09x}:{mzone.stop:09x}] -> RESERVED {ident}")
                    continue
                elif mode in (TraceMode.HOOK, TraceMode.SYNC):
                    self.map_hook_idx(mzone.start, mzone.stop - mzone.start, 0, need_read, need_write)
                    if mode == TraceMode.HOOK:
                        for m2, i2, r2, w2, k2 in maps[1:]:
                            if m2 == TraceMode.HOOK:
                                print(f"!! Conflict: HOOK {i2}")
                elif mode in (TraceMode.UNBUF, TraceMode.ASYNC):
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
                    print(f"PT[{mzone.start:09x}:{mzone.stop:09x}] -> HW")
                    continue

                rest = [m[1] for m in maps[1:] if m[0] != TraceMode.OFF]
                if rest:
                    rest = " (+ " + ", ".join(rest) + ")"
                else:
                    rest = ""

                print(f"PT[{mzone.start:09x}:{mzone.stop:09x}] -> {mode.name}.{'R' if read else ''}{'W' if read else ''} {ident}{rest}")

        self.u.inst(0xd50c879f) # tlbi alle1
        self.dirty_maps.clear()

    def shellwrap(self, func, description, update=None, needs_ret=False):

        while True:
            try:
                return func()
            except:
                print(f"Exception in {description}")
                traceback.print_exc()

            if not self.ctx:
                print("Running in asynchronous context. Target operations are not available.")

            def do_exit(i):
                raise shell.ExitConsole(i)

            self.shell_locals["skip"] = lambda: do_exit(1)
            self.shell_locals["cont"] = lambda: do_exit(0)
            ret = shell.run_shell(self.shell_locals, "Entering debug shell", "Returning to tracer")
            self.shell_locals["skip"] = self.skip
            self.shell_locals["cont"] = self.cont

            if ret == 1:
                if needs_ret:
                    print("Cannot skip, return value required.")
                else:
                    return

            if update:
                update()

    def run_shell(self, entry_msg="Entering shell", exit_msg="Continuing"):
        return shell.run_shell(self.shell_locals, entry_msg, exit_msg)

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
            if mode > TraceMode.UNBUF:
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

        if mode not in (TraceMode.HOOK, TraceMode.SYNC):
            raise Exception(f"VM hook with unexpected mapping at {data.addr:#x}: {maps[0][0].name}")

        if not data.flags.WRITE:
            if mode == TraceMode.HOOK:
                val = self.shellwrap(lambda: read(data.addr, 8 << data.flags.WIDTH, **kwargs),
                                     f"Tracer {ident}:read (HOOK)", update=do_update, needs_ret=True)

                if not isinstance(val, list) and not isinstance(val, tuple):
                    val = [val]
                first += 1
            elif mode == TraceMode.SYNC:
                val = self.u.read(data.addr, 8 << data.flags.WIDTH)
                if not isinstance(val, list) and not isinstance(val, tuple):
                    val = [val]

            for i in range(1 << max(0, data.flags.WIDTH - 3)):
                self.p.write64(ctx.data + 16 + 8 * i, val[i])

        elif mode == TraceMode.HOOK:
            first += 1

        flags = data.flags.copy()
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

            if data.flags.WIDTH < 3:
                wval = val[0]
            else:
                wval = val

            if mode == TraceMode.HOOK:
                self.shellwrap(lambda: write(data.addr, wval, 8 << data.flags.WIDTH, **kwargs),
                            f"Tracer {ident}:write (HOOK)", update=do_update)
            elif mode == TraceMode.SYNC:
                self.u.write(data.addr, wval, 8 << data.flags.WIDTH)

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


    def sym(self, addr):
        unslid_addr = addr + self.sym_offset

        if self.xnu_mode and (addr < self.tba.virt_base or unslid_addr < self.macho.vmin):
            return None, None

        idx = bisect.bisect_left(self.symbols, (unslid_addr + 1, "")) - 1
        if idx < 0 or idx >= len(self.symbols):
            return None, None

        return self.symbols[idx]

    def handle_msr(self, ctx, iss=None):
        if iss is None:
            iss = ctx.esr.ISS
        iss = ESR_ISS_MSR(iss)
        enc = iss.Op0, iss.Op1, iss.CRn, iss.CRm, iss.Op2

        name = sysreg_name(enc)

        skip = set((
            (3, 5, 15, 10, 1), # M1RACLES mitigation
        ))
        shadow = {
            #SPRR_CONFIG_EL1,
            #SPRR_PERM_EL0,
            #SPRR_PERM_EL1,
            VMSA_LOCK_EL1,
            #SPRR_UNK1_EL1,
            #SPRR_UNK2_EL1,
        }
        ro = {
            ACC_CFG_EL1,
            CYC_OVRD_EL1,
            ACC_OVRD_EL1,
        }
        value = 0
        if enc in shadow:
            if iss.DIR == MSR_DIR.READ:
                value = self.sysreg.setdefault(enc, 0)
                print(f"Shadow: mrs x{iss.Rt}, {name} = {value:x}")
                if iss.Rt != 31:
                    ctx.regs[iss.Rt] = value
            else:
                if iss.Rt != 31:
                    value = ctx.regs[iss.Rt]
                print(f"Shadow: msr {name}, x{iss.Rt} = {value:x}")
                self.sysreg[enc] = value
        elif enc in skip or (enc in ro and iss.DIR == MSR_DIR.WRITE):
            if iss.DIR == MSR_DIR.READ:
                print(f"Skip: mrs x{iss.Rt}, {name} = 0")
                if iss.Rt != 31:
                    ctx.regs[iss.Rt] = 0
            else:
                value = ctx.regs[iss.Rt]
                print(f"Skip: msr {name}, x{iss.Rt} = {value:x}")
        else:
            if iss.DIR == MSR_DIR.READ:
                print(f"Pass: mrs x{iss.Rt}, {name}", end=" ")
                sys.stdout.flush()
                enc2 = self.MSR_REDIRECTS.get(enc, enc)
                value = self.u.mrs(enc2)
                print(f"= {value:x} ({sysreg_name(enc2)})")
                if iss.Rt != 31:
                    ctx.regs[iss.Rt] = value
            else:
                if iss.Rt != 31:
                    value = ctx.regs[iss.Rt]
                print(f"Pass: msr {name}, x{iss.Rt} = {value:x}", end=" ")
                enc2 = self.MSR_REDIRECTS.get(enc, enc)
                sys.stdout.flush()
                self.u.msr(enc2, value, call=self.p.gl2_call)
                print(f"(OK) ({sysreg_name(enc2)})")

        ctx.elr += 4

        #self.patch_exception_handling()

        return True

    def handle_impdef(self, ctx):
        if ctx.esr.ISS == 0x20:
            return self.handle_msr(ctx, ctx.afsr1)

        start = ctx.elr_phys
        code = struct.unpack("<I", self.iface.readmem(ctx.elr_phys, 4))
        c = ARMAsm(".inst " + ",".join(str(i) for i in code), ctx.elr_phys)
        insn = "; ".join(c.disassemble())

        print(f"IMPDEF exception on: {insn}")

        return False

    def handle_hvc(self, ctx):
        idx = ctx.esr.ISS
        if idx == 0:
            return False

        vector, target = self.vectors[idx]
        if target is None:
            print(f"EL1: Exception #{vector} with no target")
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
                    print("Page fault")
                    return ok

            print(f"EL1: Exception #{vector} ({esr.EC!s}) to {self.addr(target)} from {spsr.M.name}")
            print(f"     ELR={self.addr(elr)} (0x{elr_phys:x})")
            print(f"     SP_EL1=0x{sp_el1:x} SP_EL0=0x{sp_el0:x}")
            if far is not None:
                print(f"     FAR={self.addr(far)}")
            if elr_phys:
                self.u.disassemble_at(elr_phys - 4 * 4, 9 * 4, elr_phys)
            if self.sym(elr)[1] == "com.apple.kernel:_panic_trap_to_debugger":
                print("Panic! Trying to decode panic...")
                try:
                    self.decode_panic_call()
                except:
                    print("Error decoding panic.")
                try:
                    self.bt()
                except:
                    pass
                return False
            if esr.EC == ESR_EC.UNKNOWN:
                instr = self.p.read32(elr_phys)
                if instr == 0xe7ffdeff:
                    print("Debugger break! Trying to decode panic...")
                    try:
                        self.decode_dbg_panic()
                    except:
                        print("Error decoding panic.")
                    try:
                        self.bt()
                    except:
                        pass
                    return False
                return False
        else:
            elr = self.u.mrs(ELR_EL12)
            print(f"Guest: {str(EXC(vector & 3))} at {self.addr(elr)}")

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

        if not self._stepping:
            return True
        self._stepping = False

    def handle_break(self, ctx):
        # disable all breakpoints so that we don't get stuck
        for i in range(5):
            self.u.msr(DBGBCRn_EL1(i), 0)

        # we'll need to single step to enable these breakpoints again
        self.u.msr(MDSCR_EL1, MDSCR(SS=1, MDE=1).value)
        self.ctx.spsr.SS = 1

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

    def handle_exception(self, reason, code, info):
        self._in_handler = True

        info_data = self.iface.readmem(info, ExcInfo.sizeof())
        self.ctx = ctx = ExcInfo.parse(info_data)

        handled = False

        try:
            if reason == START.EXCEPTION_LOWER:
                if code == EXC.SYNC:
                    handled = self.handle_sync(ctx)
                elif code == EXC.FIQ:
                    self.u.msr(CNTV_CTL_EL0, 0)
                    self.u.print_exception(code, ctx)
                    handled = True
            elif reason == START.HV:
                code = HV_EVENT(code)
                if code == HV_EVENT.HOOK_VM:
                    handled = self.handle_vm_hook(ctx)
                elif code == HV_EVENT.USER_INTERRUPT:
                    handled = True
        except Exception as e:
            print(f"Python exception while handling guest exception:")
            traceback.print_exc()

        if handled:
            ret = EXC_RET.HANDLED
            if self._sigint_pending:
                print("User interrupt")
        else:
            print(f"Guest exception: {reason.name}/{code.name}")
            self.u.print_exception(code, ctx)

        if self._sigint_pending or not handled:

            self._sigint_pending = False

            signal.signal(signal.SIGINT, self.default_sigint)
            ret = shell.run_shell(self.shell_locals, "Entering hypervisor shell", "Returning from exception")
            signal.signal(signal.SIGINT, self._handle_sigint)

            if ret is None:
                ret = EXC_RET.HANDLED

        self.pt_update()

        new_info = ExcInfo.build(self.ctx)
        if new_info != info_data:
            self.iface.writemem(info, new_info)

        self.ctx = None
        self.p.exit(ret)

        self._in_handler = False
        if self._sigint_pending:
            self._handle_sigint()

    def handle_bark(self, reason, code, info):
        self._in_handler = True
        self._sigint_pending = False

        signal.signal(signal.SIGINT, self.default_sigint)
        ret = shell.run_shell(self.shell_locals, "Entering panic shell", "Exiting")
        signal.signal(signal.SIGINT, self._handle_sigint)

        self.p.exit(0)

    def skip(self):
        self.ctx.elr += 4
        raise shell.ExitConsole(EXC_RET.HANDLED)

    def cont(self):
        raise shell.ExitConsole(EXC_RET.HANDLED)

    def step(self):
        self.u.msr(MDSCR_EL1, MDSCR(SS=1, MDE=1).value)
        self.ctx.spsr.SS = 1
        self._stepping = True
        raise shell.ExitConsole(EXC_RET.HANDLED)

    def add_hw_bp(self, vaddr):
        for i, i_vaddr in enumerate(self._bps):
            if i_vaddr is None:
                self.u.msr(DBGBCRn_EL1(i), DBGBCR(E=1, PMC=0b11, BAS=0xf).value)
                self.u.msr(DBGBVRn_EL1(i), vaddr)
                self._bps[i] = vaddr
                return
        raise ValueError("Cannot add more HW breakpoints")

    def remove_hw_bp(self, vaddr):
        idx = self._bps.index(vaddr)
        self._bps[idx] = None
        self.u.msr(DBGBCRn_EL1(idx), 0)
        self.u.msr(DBGBVRn_EL1(idx), 0)

    def exit(self):
        raise shell.ExitConsole(EXC_RET.EXIT_GUEST)

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

    def bt(self, frame=None, lr=None):
        if frame is None:
            frame = self.ctx.regs[29]
        if lr is None:
            lr = self.ctx.regs[30] | self.pac_mask

        print("Stack trace:")
        while frame:
            print(f" - {self.addr(lr - 4)}")
            lrp = self.p.hv_translate(frame + 8)
            fpp = self.p.hv_translate(frame)
            if not fpp:
                break
            lr = self.p.read64(lrp) | self.pac_mask
            frame = self.p.read64(fpp)

    def patch_exception_handling(self):
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
                print(f"VBAR vaddr 0x{vbar:x} translation failed!")
                if self.vbar_el1 is not None:
                    self.want_vbar = vbar
                    self.u.msr(VBAR_EL12, self.vbar_el1)
                return
        else:
            if vbar & (1 << 63):
                print(f"VBAR vaddr 0x{vbar:x} without translation enabled")
                if self.vbar_el1 is not None:
                    self.want_vbar = vbar
                    self.u.msr(VBAR_EL12, self.vbar_el1)
                return

            vbar_phys = vbar

        if self.want_vbar is not None:
            self.want_vbar = None
            self.u.msr(VBAR_EL12, vbar)

        print(f"New VBAR paddr: 0x{vbar_phys:x}")

        #for i in range(16):
        for i in [0, 3, 4, 7, 8, 11, 12, 15]:
            idx = 0
            addr = vbar_phys + 0x80 * i
            orig = self.p.read32(addr)
            if (orig & 0xfc000000) != 0x14000000:
                print(f"Unknown vector #{i}:\n")
                self.u.disassemble_at(addr, 16)
            else:
                idx = len(self.vectors)
                delta = orig & 0x3ffffff
                if delta == 0:
                    target = None
                    print(f"Vector #{i}: Loop\n")
                else:
                    target = (delta << 2) + vbar + 0x80 * i
                    print(f"Vector #{i}: 0x{target:x}\n")
                self.vectors.append((i, target))
                self.u.disassemble_at(addr, 16)
            self.p.write32(addr, self.hvc(idx))

        self.p.dc_cvau(vbar_phys, 0x800)
        self.p.ic_ivau(vbar_phys, 0x800)

        self.vbar_el1 = vbar


    def init(self):
        self.adt = load_adt(self.u.get_adt())
        self.iodev = self.p.iodev_whoami()
        self.tba = self.u.ba.copy()
        self.device_addr_tbl = self.adt.build_addr_lookup()
        self.print_tracer = trace.PrintTracer(self, self.device_addr_tbl)

        # disable unused USB iodev early so interrupts can be reenabled in hv_init()
        for iodev in (IODEV.USB0, IODEV.USB1):
            if iodev != self.iodev:
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
        self.iface.set_event_handler(EVENT.MMIOTRACE, self.handle_mmiotrace)
        self.iface.set_event_handler(EVENT.IRQTRACE, self.handle_irqtrace)

        # Map MMIO range as HW by default)
        self.add_tracer(range(0x2_00000000, 0x7_00000000), "HW", TraceMode.OFF)

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
        amx_ctl = AMX_CTL(self.u.mrs(AMX_CTL_EL1))
        amx_ctl.EN_EL1 = 1
        self.u.msr(AMX_CTL_EL1, amx_ctl.value)

        # Set guest AP keys
        self.u.msr(APVMKEYLO_EL2, 0x4E7672476F6E6147)
        self.u.msr(APVMKEYHI_EL2, 0x697665596F755570)
        self.u.msr(APSTS_EL12, 1)

        self.map_vuart()

        actlr = ACTLR(self.u.mrs(ACTLR_EL12))
        actlr.EnMDSB = 1
        self.u.msr(ACTLR_EL12, actlr.value)

        self.setup_adt()

    def map_vuart(self):
        zone = irange(0x2_35200000, 0x4000)
        self.p.hv_map_vuart(0x2_35200000, getattr(IODEV, self.iodev.name + "_SEC"))
        self.add_tracer(zone, "VUART", TraceMode.RESERVED)

    def map_essential(self):
        # Things we always map/take over, for the hypervisor to work
        _pmu = {}

        def wh(base, off, data, width):
            print(f"W {base:x}+{off:x}:{width} = 0x{data:x}: Dangerous write")
            _pmu[base + off] = (data & 0xff0f) | ((data & 0xf) << 4)

        def rh(base, off, width):
            data = self.p.read32(base + off)
            ret = _pmu.setdefault(base + off, data)
            print(f"R {base:x}+{off:x}:{width} = 0x{data:x} -> 0x{ret:x}")
            return ret

        if self.iodev == IODEV.USB0:
            pmgr_hooks = (0x23b700420, 0x23d280098, 0x23d280088)
        elif self.iodev == IODEV.USB1:
            pmgr_hooks = (0x23b700448, 0x23d2800a0, 0x23d280090)

        for addr in pmgr_hooks:
            self.map_hook(addr, 4, write=wh, read=rh)
            # TODO: turn into a real tracer
            self.add_tracer(irange(addr, 4), "PMU HACK", TraceMode.RESERVED)

    def setup_adt(self):
        self.adt["product"].product_name += " on m1n1 hypervisor"
        self.adt["product"].product_description += " on m1n1 hypervisor"
        soc_name = "Virtual " + self.adt["product"].product_soc_name + " on m1n1 hypervisor"
        self.adt["product"].product_soc_name = soc_name

        if self.iodev in (IODEV.USB0, IODEV.USB1):
            idx = int(str(self.iodev)[-1])
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
        for name in ("/cpus/cpu1",
                     "/cpus/cpu2",
                     "/cpus/cpu3",
                     "/cpus/cpu4",
                     "/cpus/cpu5",
                     "/cpus/cpu6",
                     "/cpus/cpu7",
                    ):
            print(f"Removing ADT node {name}")
            try:
                del self.adt[name]
            except KeyError:
                pass

        #for cpu in list(self.adt["cpus"]):
            #if cpu.name != "cpu0":
                #print(f"Removing ADT node {cpu._path}")
                #try:
                    #del self.adt["cpus"][cpu.name]
                #except KeyError:
                    #pass

    def set_bootargs(self, boot_args):
        if "-v" in boot_args.split():
            self.tba.video.display = 0
        else:
            self.tba.video.display = 1
        print(f"Setting boot arguments to {boot_args!r}")
        self.tba.cmdline = boot_args

    def load_macho(self, data, symfile=None):
        if isinstance(data, str):
            data = open(data, "rb")

        self.macho = macho = MachO(data)
        symbols = None
        if symfile is not None:
            if isinstance(symfile, str):
                symfile = open(symfile, "rb")
            syms = MachO(symfile)
            macho.add_symbols("com.apple.kernel", syms)
            self.xnu_mode = True

        self.symbols = [(v, k) for k, v in macho.symbols.items()]
        self.symbols.sort()

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
        sepfw_start, sepfw_length = self.u.adt["chosen"]["memory-map"].SEPFW
        tc_start, tc_size = self.u.adt["chosen"]["memory-map"].TrustCache

        image_size = align(len(image))
        sepfw_off = image_size
        image_size += align(sepfw_length)
        self.bootargs_off = image_size
        bootargs_size = 0x4000
        image_size += bootargs_size

        print(f"Total region size: 0x{image_size:x} bytes")

        self.phys_base = phys_base = guest_base = self.u.heap_top
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

        self.entry = macho.entry - macho.vmin + guest_base

        print(f"Mapping guest physical memory...")
        self.map_hw(0x800000000, 0x800000000, self.u.ba.phys_base - 0x800000000)
        self.map_hw(phys_base, phys_base, self.u.ba.mem_size_actual - phys_base + 0x800000000)

        print(f"Loading kernel image (0x{len(image):x} bytes)...")
        self.u.compressed_writemem(guest_base, image, True)
        self.p.dc_cvau(guest_base, len(image))
        self.p.ic_ivau(guest_base, len(image))

        print(f"Copying SEPFW (0x{sepfw_length:x} bytes)...")
        self.p.memcpy8(guest_base + sepfw_off, sepfw_start, sepfw_length)

        print(f"Copying TrustCache (0x{tc_size:x} bytes)...")
        self.p.memcpy8(tc_base, tc_start, tc_size)

        print(f"Adjusting addresses in ADT...")
        self.adt["chosen"]["memory-map"].SEPFW = (guest_base + sepfw_off, sepfw_length)
        self.adt["chosen"]["memory-map"].TrustCache = (tc_base, tc_size)
        self.adt["chosen"]["memory-map"].DeviceTree = (self.adt_base, align(self.u.ba.devtree_size))
        self.adt["chosen"]["memory-map"].BootArgs = (guest_base + self.bootargs_off, bootargs_size)

        print(f"Setting up bootargs at 0x{guest_base + self.bootargs_off:x}...")

        self.tba.mem_size = mem_size
        self.tba.phys_base = phys_base
        self.tba.virt_base = 0xfffffe0010000000 + (phys_base & (32 * 1024 * 1024 - 1))
        self.tba.devtree = self.adt_base - phys_base + self.tba.virt_base
        self.tba.top_of_kernel_data = guest_base + image_size

        self.sym_offset = macho.vmin - guest_base + self.tba.phys_base - self.tba.virt_base

        self.iface.writemem(guest_base + self.bootargs_off, BootArgs.build(self.tba))

    def load_system_map(self, path):
        # Assume Linux, no pac_mask
        self.pac_mask = 0
        self.sym_offset = 0
        self.xnu_mode = False
        self.symbols = []
        with open(path) as fd:
            for line in fd.readlines():
                addr, t, name = line.split()
                self.symbols.append((int(addr, 16), name))
        self.symbols.sort()

    def _handle_sigint(self, signal=None, stack=None):
        self._sigint_pending = True

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
        self.p.fb_shutdown()

        print("Enabling SPRR...")
        self.u.msr(SPRR_CONFIG_EL1, 1)

        print("Enabling GXF...")
        self.u.msr(GXF_CONFIG_EL1, 1)

        print(f"Jumping to entrypoint at 0x{self.entry:x}")

        self.iface.dev.timeout = None
        self.default_sigint = signal.signal(signal.SIGINT, self._handle_sigint)

        # Does not return
        self.p.hv_start(self.entry, self.guest_base + self.bootargs_off)

from . import trace

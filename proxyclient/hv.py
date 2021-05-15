#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import sys, traceback, struct, array, bisect, os

from asm import ARMAsm
from tgtypes import *
from proxy import IODEV, START, EXC, EXC_RET, ExcInfo
from utils import *
from sysreg import *
from macho import MachO
from adt import load_adt
import xnutools
import shell

PAC_MASK = 0xfffff00000000000

class HV:
    PTE_VALID               = 1 << 0

    PTE_MEMATTR_UNCHANGED   = 0b1111 << 2
    PTE_S2AP_RW             = 0b11 << 6
    PTE_SH_NS               = 0b11 << 8
    PTE_ACCESS              = 1 << 10
    PTE_ATTRIBUTES          = PTE_ACCESS | PTE_SH_NS | PTE_S2AP_RW | PTE_MEMATTR_UNCHANGED

    SPTE_MAP                = 0 << 50
    SPTE_HOOK               = 1 << 50

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
        SPRR_UMASK_EL1: SPRR_UMASK_EL12,
        APCTL_EL1: APCTL_EL12,
        APSTS_EL1: APSTS_EL12,
        KERNELKEYLO_EL12: KERNELKEYLO_EL12,
        KERNELKEYHI_EL12: KERNELKEYHI_EL12,
    }

    def __init__(self, iface, proxy, utils):
        self.iface = iface
        self.p = proxy
        self.u = utils
        self.vbar_el1 = None
        self.want_vbar = None
        self.vectors = [None]
        self.step = False
        self.sym_offset = 0
        self.symbols = []
        self.sysreg = {}

    def unmap(self, ipa, size):
        assert self.p.hv_map(ipa, 0, size, 0) >= 0

    def map_hw(self, ipa, pa, size):
        assert self.p.hv_map(ipa, pa | self.PTE_ATTRIBUTES | self.PTE_VALID, size, 1) >= 0

    def map_sw(self, ipa, pa, size):
        assert self.p.hv_map(ipa, pa | self.SPTE_MAP, size, 1) >= 0

    def addr(self, addr):
        unslid_addr = addr + self.sym_offset
        if addr < self.tba.virt_base or unslid_addr < self.macho.vmin:
            return f"0x{addr:x}"

        saddr, name = self.sym(addr)

        if name is None:
            return f"0x{addr:x} (0x{unslid_addr:x})"

        return f"0x{addr:x} ({name}+0x{unslid_addr - saddr:x})"


    def sym(self, addr):
        unslid_addr = addr + self.sym_offset

        if addr < self.tba.virt_base or unslid_addr < self.macho.vmin:
            return None, None

        idx = bisect.bisect_left(self.symbols, (unslid_addr + 1, "")) - 1
        if idx < 0 or idx >= len(self.symbols):
            return f"0x{addr:x} (0x{unslid_addr:x})"

        return self.symbols[idx]

    def handle_msr(self, ctx, iss=None):
        if iss is None:
            iss = ctx.esr.ISS
        iss = ESR_ISS_MSR(iss)
        enc = iss.Op0, iss.Op1, iss.CRn, iss.CRm, iss.Op2

        if enc in sysreg_rev:
            name = sysreg_rev[enc]
        else:
            name = f"s{iss.Op0}_{iss.Op1}_c{iss.CRn}_c{iss.CRm}_{iss.Op2}"

        skip = set()
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
                value = self.u.mrs(self.MSR_REDIRECTS.get(enc, enc))
                print(f"= {value:x}")
                if iss.Rt != 31:
                    ctx.regs[iss.Rt] = value
            else:
                if iss.Rt != 31:
                    value = ctx.regs[iss.Rt]
                print(f"Pass: msr {name}, x{iss.Rt} = {value:x}", end=" ")
                sys.stdout.flush()
                self.u.msr(self.MSR_REDIRECTS.get(enc, enc), value, call=self.p.gl2_call)
                print("(OK)")

        ctx.elr += 4

        self.patch_exception_handling()

        return True

    def handle_impdef(self, ctx):
        if ctx.esr.ISS == 0x20:
            return self.handle_msr(ctx, self.u.mrs(AFSR1_EL1))

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

    def handle_sync(self, ctx):
        if ctx.esr.EC == ESR_EC.MSR:
            return self.handle_msr(ctx)

        if ctx.esr.EC == ESR_EC.IMPDEF:
            return self.handle_impdef(ctx)

        if ctx.esr.EC == ESR_EC.HVC:
            return self.handle_hvc(ctx)

    def handle_exception(self, reason, code, info):
        self.ctx = ctx = ExcInfo.parse(self.iface.readmem(info, ExcInfo.sizeof()))

        handled = False

        try:
            if code == EXC.SYNC:
                handled = self.handle_sync(ctx)
            elif code == EXC.FIQ:
                self.u.msr(CNTV_CTL_EL0, 0)
                self.u.print_exception(code, ctx)
                handled = True
        except Exception as e:
            print(f"Python exception while handling guest exception:")
            traceback.print_exc()

        if handled:
            ret = EXC_RET.HANDLED
        else:
            print(f"Guest exception: {code.name}")

            self.u.print_exception(code, ctx)

            locals = {
                "hv": self,
                "iface": self.iface,
                "p": self.p,
                "u": self.u,
            }

            for attr in dir(self):
                a = getattr(self, attr)
                if callable(a):
                    locals[attr] = getattr(self, attr)

            ret = shell.run_shell(locals, "Entering debug shell", "Returning from exception")

            if ret is None:
                ret = EXC_RET.EXIT_GUEST

        self.iface.writemem(info, ExcInfo.build(self.ctx))

        if ret == EXC_RET.HANDLED and self.step:
            ret = EXC_RET.STEP
        self.p.exit(ret)

    def skip(self):
        self.ctx.elr += 4
        raise shell.ExitConsole(EXC_RET.HANDLED)

    def cont(self):
        raise shell.ExitConsole(EXC_RET.HANDLED)

    def exit(self):
        raise shell.ExitConsole(EXC_RET.EXIT_GUEST)

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
            lr = self.ctx.regs[30] | PAC_MASK

        print("Stack trace:")
        while frame:
            print(f" - {self.addr(lr - 4)}")
            lrp = self.p.hv_translate(frame + 8)
            fpp = self.p.hv_translate(frame)
            if not fpp:
                break
            lr = self.p.read64(lrp) | PAC_MASK
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

        print("Initializing hypervisor over iodev %s" % self.iodev)
        self.p.hv_init()

        self.iface.set_handler(START.EXCEPTION_LOWER, EXC.SYNC, self.handle_exception)
        self.iface.set_handler(START.EXCEPTION_LOWER, EXC.IRQ, self.handle_exception)
        self.iface.set_handler(START.EXCEPTION_LOWER, EXC.FIQ, self.handle_exception)
        self.iface.set_handler(START.EXCEPTION_LOWER, EXC.SERROR, self.handle_exception)

        self.map_hw(0x2_00000000, 0x2_00000000, 0x5_00000000)

        hcr = HCR(self.u.mrs(HCR_EL2))
        hcr.TACR = 1
        hcr.TIDCP = 0
        hcr.TVM = 0
        hcr.FMO = 0
        hcr.IMO = 0
        self.u.msr(HCR_EL2, hcr.value)

        # Trap dangerous things
        hacr = HACR(0)
        #hacr.TRAP_CPU_EXT = 1
        #hacr.TRAP_SPRR = 1
        #hacr.TRAP_GXF = 1
        hacr.TRAP_CTRR = 1
        hacr.TRAP_EHID = 1
        hacr.TRAP_HID = 1
        hacr.TRAP_ACC = 1
        self.u.msr(HACR_EL2, hacr.value)

        # Enable AMX
        amx_ctl = AMX_CTL(self.u.mrs(AMX_CTL_EL1))
        amx_ctl.EN_EL1 = 1
        self.u.msr(AMX_CTL_EL1, amx_ctl.value)

        # Set guest AP keys
        self.u.msr(APVMKEYLO_EL2, 0x4E7672476F6E6147)
        self.u.msr(APVMKEYHI_EL2, 0x697665596F755570)
        self.u.msr(APSTS_EL12, 1)

        #self.p.hv_map_vuart(0x2_35200000, getattr(IODEV, self.iodev.name + "_SEC"))

        actlr = ACTLR(self.u.mrs(ACTLR_EL12))
        actlr.EnMDSB = 1
        self.u.msr(ACTLR_EL12, actlr.value)

        self.setup_adt()

    def setup_adt(self):
        if self.iodev in (IODEV.USB0, IODEV.USB1):
            idx = int(str(self.iodev)[-1])
            for prefix in ("dart-usb%d",
                           "atc-phy%d",
                           "usb-drd%d",
                           "acio%d",
                           "apciec%d",
                           "dart-apciec%d",
                           "apciec%d-piodma"):
                name = prefix % idx
                print(f"Removing ADT node /arm-io/{name}")
                try:
                    del self.adt["arm-io"][name]
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
        adt_base = guest_base
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
        self.adt["chosen"]["memory-map"].DeviceTree = (adt_base, align(self.u.ba.devtree_size))
        self.adt["chosen"]["memory-map"].BootArgs = (guest_base + self.bootargs_off, bootargs_size)

        adt_blob = self.adt.build()
        print(f"Uploading ADT (0x{len(adt_blob):x} bytes)...")
        self.iface.writemem(adt_base, adt_blob)

        print(f"Setting up bootargs at 0x{guest_base + self.bootargs_off:x}...")

        self.tba.mem_size = mem_size
        self.tba.phys_base = phys_base
        self.tba.virt_base = 0xfffffe0010000000 + (phys_base & (32 * 1024 * 1024 - 1))
        self.tba.devtree = adt_base - phys_base + self.tba.virt_base
        self.tba.top_of_kernel_data = guest_base + image_size

        self.sym_offset = macho.vmin - guest_base + self.tba.phys_base - self.tba.virt_base

        self.iface.writemem(guest_base + self.bootargs_off, BootArgs.build(self.tba))

    def start(self):
        print(f"Disabling other iodevs...")
        for iodev in IODEV:
            if iodev != self.iodev:
                print(f" - {iodev!s}")
                self.p.iodev_set_usage(iodev, 0)

        print(f"Shutting down framebuffer...")
        self.p.fb_shutdown()

        print(f"Enabling SPRR...")
        self.u.msr(SPRR_CONFIG_EL1, 1)

        print(f"Enabling GXF...")
        self.u.msr(GXF_CONFIG_EL1, 1)

        print(f"Jumping to entrypoint at 0x{self.entry:x}")

        self.iface.dev.timeout = None

        # Does not return
        self.p.hv_start(self.entry, self.guest_base + self.bootargs_off)

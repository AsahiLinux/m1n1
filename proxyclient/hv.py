#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import sys

from tgtypes import *
from proxy import IODEV, START, EXC, EXC_RET, ExcInfo
from utils import *
from sysreg import *
from macho import MachO
from adt import load_adt
import shell

class HV:
    PTE_VALID               = 1 << 0

    PTE_MEMATTR_UNCHANGED   = 0b1111 << 2
    PTE_S2AP_RW             = 0b11 << 6
    PTE_SH_NS               = 0b11 << 8
    PTE_ACCESS              = 1 << 10
    PTE_ATTRIBUTES          = PTE_ACCESS | PTE_SH_NS | PTE_S2AP_RW | PTE_MEMATTR_UNCHANGED

    SPTE_MAP                = 0 << 50
    SPTE_HOOK               = 1 << 50

    def __init__(self, iface, proxy, utils):
        self.iface = iface
        self.p = proxy
        self.u = utils

    def unmap(self, ipa, size):
        assert self.p.hv_map(ipa, 0, size, 0) >= 0

    def map_hw(self, ipa, pa, size):
        assert self.p.hv_map(ipa, pa | self.PTE_ATTRIBUTES | self.PTE_VALID, size, 1) >= 0

    def map_sw(self, ipa, pa, size):
        assert self.p.hv_map(ipa, pa | self.SPTE_MAP, size, 1) >= 0

    def handle_exception(self, reason, code, info):
        self.ctx = ctx = ExcInfo.parse(self.iface.readmem(info, ExcInfo.sizeof()))

        print(f"Guest exception: {code.name}")

        self.u.print_exception(code, ctx)

        locals = {
            "hv": self,
            "iface": self.iface,
            "p": self.p,
            "u": self.u,
        }

        for attr in dir(self):
            locals[attr] = getattr(self, attr)

        ret = shell.run_shell(locals, "Entering debug shell", "Returning from exception")

        if ret is None:
            ret = EXC_RET.EXIT_GUEST

        self.iface.writemem(info, ExcInfo.build(self.ctx))
        self.p.exit(ret)

    def skip(self):
        self.ctx.elr += 4
        raise shell.ExitConsole(EXC_RET.HANDLED)

    def cont(self):
        raise shell.ExitConsole(EXC_RET.HANDLED)

    def exit(self):
        raise shell.ExitConsole(EXC_RET.EXIT_GUEST)

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
        self.map_hw(0x8_00000000, 0x8_00000000, 0x4_00000000)

        self.p.hv_map_vuart(0x2_35200000)

        self.setup_adt()

    def setup_adt(self):
        if self.iodev in (IODEV.USB0, IODEV.USB1):
            idx = str(self.iodev)[-1]
            for prefix in ("dart-usb", "atc-phy", "usb-drd"):
                name = f"{prefix}{idx}"
                print(f"Removing ADT node /arm-io/{name}")
                try:
                    del self.adt["arm-io"][name]
                except KeyError:
                    pass

        for cpu in list(self.adt["cpus"]):
            if cpu.name != "cpu0":
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

    def load_macho(self, data):
        if isinstance(data, str):
            data = open(data, "rb").read()

        macho = MachO(data)
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
        adt_base = guest_base
        guest_base += align(self.u.ba.devtree_size)
        tc_base = guest_base
        guest_base += align(tc_size)
        self.guest_base = guest_base

        print(f"Physical memory base: 0x{phys_base:x}")
        print(f"Guest region start: 0x{guest_base:x}")

        self.entry = macho.entry - macho.vmin + guest_base

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
        self.tba.top_of_kdata = guest_base + image_size

        self.iface.writemem(guest_base + self.bootargs_off, BootArgs.build(self.tba))

    def start(self):
        print(f"Disabling other iodevs...")
        for iodev in IODEV:
            if iodev != self.iodev:
                print(f" - {iodev!s}")
                self.p.iodev_set_usage(iodev, 0)

        print(f"Shutting down framebuffer...")
        self.p.fb_shutdown()

        print(f"Jumping to entrypoint at 0x{self.entry:x}")

        self.iface.dev.timeout = None

        # Does not return
        self.p.hv_start(self.entry, self.guest_base + self.bootargs_off)

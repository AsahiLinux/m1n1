#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

from tgtypes import *
from proxy import IODEV
from utils import *
from sysreg import *
from macho import MachO

class HV:
    PTE_VALID               = 1 << 0

    PTE_MEMATTR_UNCHANGED   = 0b1111 << 2
    PTE_S2AP_RW             = 0b11 << 6
    PTE_SH_NS               = 0b11 << 8
    PTE_ACCESS              = 1 << 10
    PTE_ATTRIBUTES          = PTE_ACCESS | PTE_SH_NS | PTE_S2AP_RW | PTE_MEMATTR_UNCHANGED

    SPTE_MAP                = 0 << 48
    SPTE_HOOK               = 1 << 48

    def __init__(self, iface, proxy, utils):
        self.iface = iface
        self.p = proxy
        self.u = utils
        self.adt = self.u.adt

    def unmap(self, ipa, size):
        assert self.p.hv_map(ipa, 0, size, 0) >= 0

    def map_hw(self, ipa, pa, size):
        assert self.p.hv_map(ipa, pa | self.PTE_ATTRIBUTES | self.PTE_VALID, size, 1) >= 0

    def map_sw(self, ipa, pa, size):
        assert self.p.hv_map(ipa, pa | self.SPTE_MAP, size, 1) >= 0

    def init(self):
        self.iodev = self.p.iodev_whoami()

        print("Initializing hypervisor over iodev %s" % self.iodev)
        self.p.hv_init()

        self.map_hw(0x2_00000000, 0x2_00000000, 0x5_00000000)
        self.map_hw(0x8_00000000, 0x8_00000000, 0x4_00000000)

    def load_macho(self, data):
        if isinstance(data, str):
            data = open(data, "rb").read()

        macho = MachO(data)
        image = macho.prepare_image()
        sepfw_start, sepfw_length = self.u.adt["chosen"]["memory-map"].SEPFW

        image_size = align(len(image))
        sepfw_off = image_size
        image_size += align(sepfw_length)
        self.bootargs_off = image_size
        image_size += 0x4000

        print(f"Total region size: 0x{image_size:x} bytes")

        self.guest_base = guest_base = self.u.heap_top
        print(f"Guest region start: 0x{guest_base:x}")

        self.entry = macho.entry - macho.vmin + guest_base

        print(f"Loading kernel image (0x{len(image):x} bytes)...")
        self.u.compressed_writemem(guest_base, image, True)
        self.p.dc_cvau(guest_base, len(image))
        self.p.ic_ivau(guest_base, len(image))

        print(f"Copying SEPFW (0x{sepfw_length:x} bytes)...")
        self.p.memcpy8(guest_base + sepfw_off, sepfw_start, sepfw_length)

        print(f"Adjusting SEPFW address in ADT...")
        self.adt["chosen"]["memory-map"].SEPFW = (guest_base + sepfw_off, sepfw_length)

        if self.iodev in (IODEV.USB0, IODEV.USB1):
            idx = str(self.iodev)[-1]
            for prefix in ("dart-usb", "atc-phy", "usb-drd"):
                name = f"{prefix}{idx}"
                print(f"Removing ADT node /arm-io/{name}")
                del self.adt["arm-io"][name]

        for cpu in list(self.adt["cpus"]):
            if cpu.name != "cpu0":
                print(f"Removing ADT node {cpu._path}")
                del self.adt["cpus"][cpu.name]

        self.u.push_adt()

        print(f"Setting up bootargs...")
        tba = self.u.ba.copy()
        mem_top = tba.phys_base + tba.mem_size
        devtree = tba.devtree - tba.virt_base + tba.phys_base

        tba.mem_size = mem_top - guest_base
        tba.phys_base = guest_base
        tba.virt_base = 0xfffffe0010000000 + (guest_base & (32 * 1024 * 1024 - 1))
        tba.devtree = devtree - tba.phys_base + tba.virt_base
        tba.top_of_kdata = guest_base + image_size

        self.iface.writemem(guest_base + self.bootargs_off, BootArgs.build(tba))

    def start(self):
        print(f"Disabling other iodevs...")
        for iodev in IODEV:
            if iodev != self.iodev:
                print(f" - {iodev!s}")
                self.p.iodev_set_usage(iodev, 0)

        print(f"Jumping to entrypoint at 0x{self.entry:x}")

        self.p.reboot(self.entry, self.guest_base + self.bootargs_off, el1=True)
        self.iface.ttymode()

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
import serial
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import argparse, pathlib

# FreeBSD's setup differs from Linux's in the following primary ways:
#
# 1.) We pretend our kernel is an initramfs and pick it up as such in a modified
#    loader build.  This is the simplest way to avoid having ad-hoc
#    interpretations of stuff in m1n1 for our quirky development setup.
#
# 2.) U-Boot and dtb are required, loader/kernel are not.  The latter are
#    assumed to be discoverable by the standard U-Boot process on disk if they
#    are not specified.  Otherwise, we'll load them from memory if they are
#    provided.
#
parser = argparse.ArgumentParser(description='(FreeBSD) kernel loader for m1n1')
parser.add_argument('u_boot', type=pathlib.Path, help="load u-boot before linux")
parser.add_argument('dtb', type=pathlib.Path)
parser.add_argument('-l', '--loader', type=pathlib.Path)
parser.add_argument('-k', '--kernel', type=pathlib.Path)
parser.add_argument('-b', '--bootargs', type=str, metavar='"boot arguments"')
parser.add_argument('-t', '--tty', type=str)
args = parser.parse_args()

from m1n1.setup import *

if args.tty is not None:
    tty_dev = serial.Serial(args.tty)
    tty_dev.reset_input_buffer()
    tty_dev.baudrate = 1500000
else:
    tty_dev = None

if args.loader is not None:
    loader = args.loader.read_bytes()
    loader_size = len(loader)
else:
    loader = None
    loader_size = 0

dtb = args.dtb.read_bytes()

if args.kernel is not None:
    kernel = args.kernel.read_bytes()
    kernel_size = len(kernel)
else:
    kernel = None
    kernel_size = 0

if args.bootargs is not None:
    print('Setting boot args: "{}"'.format(args.bootargs))
    p.kboot_set_chosen("bootarg", args.bootargs)

dtb_addr = u.malloc(len(dtb))
print("Loading DTB to 0x%x..." % dtb_addr)

iface.writemem(dtb_addr, dtb)

loader_base = u.memalign(2 * 1024 * 1024, loader_size)

print("loader_base: 0x%x" % loader_base)

assert not (loader_base & 0xffff)

if kernel is not None:
    kernel_base = u.memalign(65536, kernel_size)
    print("Loading %d kernel bytes to 0x%x..." % (kernel_size, kernel_base))
    iface.writemem(kernel_base, kernel, True)
    p.kboot_set_initrd(kernel_base, kernel_size)

uboot = bytearray(args.u_boot.read_bytes())
uboot_size = len(uboot)
uboot_addr = u.memalign(2*1024*1024, len(uboot))
print("Loading u-boot to 0x%x..." % uboot_addr)

bootenv_start = uboot.find(b"bootcmd=run distro_bootcmd")
bootenv_len = uboot[bootenv_start:].find(b"\x00\x00")
bootenv_old = uboot[bootenv_start:bootenv_start+bootenv_len]
bootenv = str(bootenv_old, "ascii").split("\x00")
bootenv = list(filter(lambda x: not (x.startswith("baudrate") or (x.startswith("boot_") and not x.startswith("boot_efi_")) or x.startswith("distro_bootcmd")), bootenv))

if loader is not None:
    # dtb_addr not used here, the prepared fdt's at a different location.  If
    # we use this one, we won't get any of our /chosen additions, for instance.
    bootcmd = "distro_bootcmd=bootefi 0x%x - 0x%x" % (loader_base, loader_size)
else:
    bootcmd = "distro_bootcmd=devnum=0; run usb_boot"

if tty_dev is not None:
	bootenv.append("baudrate=%d" % tty_dev.baudrate)
bootenv.append(bootcmd)
if args.bootargs is not None:
    bootenv.append("bootargs=" + args.bootargs)

bootenv_new = b"\x00".join(map(lambda x: bytes(x, "ascii"), bootenv))
bootenv_new = bootenv_new.ljust(len(bootenv_old), b"\x00")

if len(bootenv_new) > len(bootenv_old):
    raise Exception("New bootenv cannot be larger than original bootenv")
uboot[bootenv_start:bootenv_start+bootenv_len] = bootenv_new

u.compressed_writemem(uboot_addr, uboot, True)
p.dc_cvau(uboot_addr, uboot_size)
p.ic_ivau(uboot_addr, uboot_size)

boot_addr = uboot_addr

p.smp_start_secondaries()

if p.kboot_prepare_dt(dtb_addr):
    print("DT prepare failed")
    sys.exit(1)

iface.dev.timeout = 40

if loader is not None:
    print("Loading %d bytes to 0x%x..0x%x..." % (loader_size, loader_base, loader_base + loader_size))
    iface.writemem(loader_base, loader, True)

    p.dc_cvau(loader_base, loader_size)
    p.ic_ivau(loader_base, loader_size)

print("Ready to boot")

daif = u.mrs(DAIF)
daif = 0xc0
u.msr(DAIF, daif)
print("DAIF: %x" % daif)

p.kboot_boot(boot_addr)

iface.ttymode(tty_dev)

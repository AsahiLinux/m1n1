#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
import serial
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import argparse, pathlib

parser = argparse.ArgumentParser(description='(Linux) kernel loader for m1n1')
parser.add_argument('payload', type=pathlib.Path)
parser.add_argument('dtb', type=pathlib.Path)
parser.add_argument('initramfs', nargs='?', type=pathlib.Path)
parser.add_argument('--compression', choices=['auto', 'none', 'gz', 'xz'], default='auto')
parser.add_argument('-b', '--bootargs', type=str, metavar='"boot arguments"')
parser.add_argument('-t', '--tty', type=str)
parser.add_argument('-u', '--u-boot', type=pathlib.Path, help="load u-boot before linux")
args = parser.parse_args()

from m1n1.setup import *

if args.compression == 'auto':
    suffix = args.payload.suffix
    if suffix == '.gz':
        args.compression = 'gz'
    elif suffix == '.xz':
        args.compression = 'xz'
    else:
        raise ValueError('unknown compression for {}'.format(args.payload))

if args.tty is not None:
    tty_dev = serial.Serial(args.tty)
    tty_dev.reset_input_buffer()
    tty_dev.baudrate = 1500000
else:
    tty_dev = None

payload = args.payload.read_bytes()
dtb = args.dtb.read_bytes()
if args.initramfs is not None:
    initramfs = args.initramfs.read_bytes()
    initramfs_size = len(initramfs)
else:
    initramfs = None
    initramfs_size = 0

if args.bootargs is not None:
    print('Setting boot args: "{}"'.format(args.bootargs))
    p.kboot_set_chosen("bootargs", args.bootargs)

if args.compression != 'none':
    compressed_size = len(payload)
    compressed_addr = u.malloc(compressed_size)

    print("Loading %d bytes to 0x%x..0x%x..." % (compressed_size, compressed_addr, compressed_addr + compressed_size))
    iface.writemem(compressed_addr, payload, True)

dtb_addr = u.malloc(len(dtb))
print("Loading DTB to 0x%x..." % dtb_addr)

iface.writemem(dtb_addr, dtb)

kernel_size = 512 * 1024 * 1024
kernel_base = u.memalign(2 * 1024 * 1024, kernel_size)
boot_addr = kernel_base

print("Kernel_base: 0x%x" % kernel_base)

assert not (kernel_base & 0xffff)

if initramfs is not None:
    initramfs_base = u.memalign(65536, initramfs_size)
    print("Loading %d initramfs bytes to 0x%x..." % (initramfs_size, initramfs_base))
    iface.writemem(initramfs_base, initramfs, True)
    p.kboot_set_initrd(initramfs_base, initramfs_size)


if args.u_boot:
    uboot = bytearray(args.u_boot.read_bytes())
    uboot_size = len(uboot)
    uboot_addr = u.memalign(2*1024*1024, len(uboot))
    print("Loading u-boot to 0x%x..." % uboot_addr)

    bootenv_start = uboot.find(b"bootcmd=run distro_bootcmd")
    bootenv_len = uboot[bootenv_start:].find(b"\x00\x00")
    bootenv_old = uboot[bootenv_start:bootenv_start+bootenv_len]
    bootenv = str(bootenv_old, "ascii").split("\x00")
    bootenv = list(filter(lambda x: not (x.startswith("baudrate") or x.startswith("boot_") or x.startswith("distro_bootcmd")), bootenv))

    if initramfs is not None:
        bootcmd = "distro_bootcmd=booti 0x%x 0x%x:0x%x $fdtcontroladdr" % (kernel_base, initramfs_base, initramfs_size)
    else:
        bootcmd = "distro_bootcmd=booti 0x%x - $fdtcontroladdr" % (kernel_base)

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

if args.compression == 'none':
    kernel_size = len(payload)
    print("Loading %d bytes to 0x%x..0x%x..." % (kernel_size, kernel_base, kernel_base + kernel_size))
    iface.writemem(kernel_base, payload, True)
elif args.compression == 'gz':
    print("Uncompressing gz ...")
    kernel_size = p.gzdec(compressed_addr, compressed_size, kernel_base, kernel_size)
elif args.compression == 'xz':
    print("Uncompressing xz ...")
    kernel_size = p.xzdec(compressed_addr, compressed_size, kernel_base, kernel_size)
else:
    raise ValueError('unsupported compression {}'.format(args.compression))

print(kernel_size)

if kernel_size < 0:
    raise Exception("Decompression error!")

print("Decompress OK...")

p.dc_cvau(kernel_base, kernel_size)
p.ic_ivau(kernel_base, kernel_size)

print("Ready to boot")

daif = u.mrs(DAIF)
daif = 0xc0
u.msr(DAIF, daif)
print("DAIF: %x" % daif)

p.kboot_boot(boot_addr)

iface.ttymode(tty_dev)

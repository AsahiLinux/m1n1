#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import argparse, pathlib, time

parser = argparse.ArgumentParser(description='Mach-O loader for m1n1')
parser.add_argument('-q', '--quiet', action="store_true", help="Disable framebuffer")
parser.add_argument('-n', '--no-sepfw', action="store_true", help="Do not preserve SEPFW")
parser.add_argument('-c', '--call', action="store_true", help="Use call mode")
parser.add_argument('-r', '--raw', action="store_true", help="Image is raw")
parser.add_argument('-E', '--entry-point', action="store", type=int, help="Entry point for the raw image", default=0x800)
parser.add_argument('-x', '--xnu', action="store_true", help="Set up for chainloading XNU")
parser.add_argument('payload', type=pathlib.Path)
parser.add_argument('boot_args', default=[], nargs="*")
args = parser.parse_args()

from m1n1.setup import *
from m1n1.tgtypes import BootArgs
from m1n1.macho import MachO
from m1n1 import asm

new_base = u.base

if args.raw:
    image = args.payload.read_bytes()
    image += b"\x00\x00\x00\x00"
    entry = new_base + args.entry_point
else:
    macho = MachO(args.payload.read_bytes())
    image = macho.prepare_image()
    image += b"\x00\x00\x00\x00"
    entry = macho.entry
    entry -= macho.vmin
    entry += new_base

if args.quiet:
    p.iodev_set_usage(IODEV.FB, 0)

if args.no_sepfw:
    sepfw_start, sepfw_length = 0, 0
else:
    sepfw_start, sepfw_length = u.adt["chosen"]["memory-map"].SEPFW

image_size = align(len(image))
sepfw_off = image_size
image_size += align(sepfw_length)
bootargs_off = image_size
bootargs_size = 0x4000
image_size += bootargs_size

print(f"Total region size: 0x{image_size:x} bytes")
image_addr = u.malloc(image_size)

print(f"Loading kernel image (0x{len(image):x} bytes)...")
u.compressed_writemem(image_addr, image, True)
p.dc_cvau(image_addr, len(image))

if not args.no_sepfw:
    print(f"Copying SEPFW (0x{sepfw_length:x} bytes)...")
    p.memcpy8(image_addr + sepfw_off, sepfw_start, sepfw_length)
    print(f"Adjusting addresses in ADT...")
    u.adt["chosen"]["memory-map"].SEPFW = (new_base + sepfw_off, sepfw_length)
    u.adt["chosen"]["memory-map"].BootArgs = (image_addr + bootargs_off, bootargs_size)

    u.push_adt()

    print("Setting secondary CPU RVBARs...")

    rvbar = entry & ~0xfff
    for cpu in u.adt["cpus"][1:]:
        addr, size = cpu.cpu_impl_reg
        print(f"  {cpu.name}: [0x{addr:x}] = 0x{rvbar:x}")
        p.write64(addr, rvbar)

print("Setting up bootargs...")
tba = u.ba.copy()

tba.top_of_kernel_data = new_base + image_size

if len(args.boot_args) > 0:
    boot_args = " ".join(args.boot_args)
    if "-v" in boot_args.split():
        tba.video.display = 0
    else:
        tba.video.display = 1
    print(f"Setting boot arguments to {boot_args!r}")
    tba.cmdline = boot_args

if args.xnu:
    # Fix virt_base, since we often install m1n1 with it set to 0 which xnu does not like
    tba.virt_base = 0xfffffe0010000000 + (tba.phys_base & (32 * 1024 * 1024 - 1))
    tba.devtree = u.ba.devtree - u.ba.virt_base + tba.virt_base

iface.writemem(image_addr + bootargs_off, BootArgs.build(tba))

print(f"Copying stub...")

stub = asm.ARMAsm(f"""
1:
        ldp x4, x5, [x1], #16
        stp x4, x5, [x2]
        dc cvau, x2
        ic ivau, x2
        add x2, x2, #16
        sub x3, x3, #16
        cbnz x3, 1b

        ldr x1, ={entry}
        br x1
""", image_addr + image_size)

iface.writemem(stub.addr, stub.data)
p.dc_cvau(stub.addr, stub.len)
p.ic_ivau(stub.addr, stub.len)

print(f"Entry point: 0x{entry:x}")

if args.xnu:
    p.display_shutdown(0)

if args.call:
    print(f"Shutting down MMU...")
    try:
        p.mmu_shutdown()
    except ProxyCommandError:
        pass
    print(f"Jumping to stub at 0x{stub.addr:x}")
    p.call(stub.addr, new_base + bootargs_off, image_addr, new_base, image_size, reboot=True)
else:
    print(f"Reloading into stub at 0x{stub.addr:x}")
    p.reload(stub.addr, new_base + bootargs_off, image_addr, new_base, image_size)

iface.nop()
print("Proxy is alive again")

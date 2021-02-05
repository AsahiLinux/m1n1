#!/usr/bin/python

import argparse, pathlib

parser = argparse.ArgumentParser(description='(Linux) kernel loader for m1n1')
parser.add_argument('payload', nargs=1, type=pathlib.Path)
parser.add_argument('dtb', nargs=1, type=pathlib.Path)
parser.add_argument('initramfs', nargs='?', type=pathlib.Path)
parser.add_argument('--compression', choices=['auto', 'none', 'gz', 'xz'], default='auto')
parser.add_argument('-b', '--bootargs', type=str, metavar='"boot arguments"')
args = parser.parse_args()

from setup import *

if args.compression == 'auto':
    suffix = args.payload[0].suffix
    if suffix == '.gz':
        args.compression = 'gz'
    elif suffix == '.xz':
        args.compression = 'xz'
    else:
        raise ValueError('unknown compression for {}'.format(args.payload))


payload = args.payload[0].read_bytes()
dtb = args.dtb[0].read_bytes()
if args.initramfs is not None:
    initramfs = args.initramfs[0].read_bytes()
    initramfs_size = len(initramfs)
else:
    initramfs = None
    initramfs_size = 0

if args.bootargs is not None:
    bootargs = bytes(args.bootargs, encoding="utf-8")
    print('Setting boot args: "{}"'.format(args.bootargs))
    bootargs_addr = u.malloc(len(bootargs) + 1)
    iface.writemem(bootargs_addr, bootargs, len(bootargs))
    p.memset8(bootargs_addr + len(bootargs) , 0, 1)
    p.kboot_set_bootargs(bootargs_addr)

if args.compression != 'none':
    compressed_size = len(payload)
    compressed_addr = u.malloc(compressed_size)

    print("Loading %d bytes to 0x%x..0x%x..." % (compressed_size, compressed_addr, compressed_addr + compressed_size))
    iface.writemem(compressed_addr, payload, True)

dtb_addr = u.malloc(len(dtb))
print("Loading DTB to 0x%x..." % dtb_addr)

iface.writemem(dtb_addr, dtb)

kernel_size = 32 * 1024 * 1024
kernel_base = u.memalign(2 * 1024 * 1024, kernel_size)

print("Kernel_base: 0x%x" % kernel_base)

assert not (kernel_base & 0xffff)

if initramfs is not None:
    initramfs_base = u.memalign(65536, initramfs_size)
    print("Loading %d initramfs bytes to 0x%x..." % (initramfs_size, initramfs_base))
    iface.writemem(initramfs_base, initramfs, True)
    p.kboot_set_initrd(initramfs_base, initramfs_size)

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
daif |= 0x3c0
u.msr(DAIF, daif)
print("DAIF: %x" % daif)

p.kboot_boot(kernel_base)
iface.ttymode()

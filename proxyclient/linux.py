#!/usr/bin/python

import argparse, pathlib

parser = argparse.ArgumentParser(description='(Linux) kernel loader for m1n1')
parser.add_argument('payload', nargs=1, type=pathlib.Path)
parser.add_argument('dtb', nargs=1, type=pathlib.Path)
parser.add_argument('initramfs', nargs='?', type=pathlib.Path)
args = parser.parse_args()

from setup import *

payload = args.payload[0].read_bytes()
dtb = args.dtb[0].read_bytes()
if args.initramfs is not None:
    initramfs = args.initramfs[0].read_bytes()
    initramfs_size = len(initramfs)
else:
    initramfs = None
    initramfs_size = 0

compressed_size = len(payload)
compressed_addr = u.malloc(compressed_size)

dtb_addr = u.malloc(len(dtb))

print("Loading %d bytes to 0x%x..0x%x..." % (compressed_size, compressed_addr, compressed_addr + compressed_size))

iface.writemem(compressed_addr, payload, True)

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

#kernel_size = p.xzdec(compressed_addr, compressed_size)

#if kernel_size < 0:
    #raise Exception("Decompression header check error!",)

#print("Uncompressed kernel size: %d bytes" % kernel_size)
print("Uncompressing...")

iface.dev.timeout = 40

kernel_size = p.gzdec(compressed_addr, compressed_size, kernel_base, kernel_size)
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

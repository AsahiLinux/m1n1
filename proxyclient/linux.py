#!/usr/bin/python

from setup import *

payload = open(sys.argv[1], "rb").read()
dtb = open(sys.argv[2], "rb").read()
if len(sys.argv) > 3:
    initramfs = open(sys.argv[3], "rb").read()
    initramfs_size = len(initramfs)
else:
    initramfs = None
    initramfs_size = 0

kernel_base = 0x820000000
initramfs_base = 0x830000000

compressed_size = len(payload)
compressed_addr = u.malloc(compressed_size)

dtb_addr = u.malloc(len(dtb))

print("Loading %d bytes to 0x%x..." % (compressed_size, compressed_addr))

iface.writemem(compressed_addr, payload, True)

print("Loading DTB to 0x%x..." % dtb_addr)

iface.writemem(dtb_addr, dtb)

if initramfs is not None:
    print("Loading %d initramfs bytes to 0x%x..." % (initramfs_size, initramfs_base))

    iface.writemem(initramfs_base, initramfs, True)

#kernel_size = p.xzdec(compressed_addr, compressed_size)
kernel_size = 32 * 1024 * 1024

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

p.vector(kernel_base, dtb_addr)

iface.ttymode()

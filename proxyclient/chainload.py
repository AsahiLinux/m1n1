#!/usr/bin/python

from setup import *

payload = open(sys.argv[1], "rb").read()

try:
    # Try to use the m1n1 heap to avoid wasting 128MB RAM on every load
    new_base = p.memalign(0x10000, len(payload))
except:
    # Fall back to proxy heap, which will be at the right place in old versions
    new_base = u.memalign(0x10000, len(payload))

# FIXME: this will currently still waste the whole m1n1 size including payload area (64+MB) on each
# chainload. The best way to fix this is to support in-place chainloading, which has other
# advantages.

print("Loading %d bytes to 0x%x" % (len(payload), new_base))

iface.writemem(new_base + 0x4000, payload[0x4000:], True)

entry = new_base + 0x4800

print("Jumping to 0x%x" % entry)

p.reboot(entry, u.ba_addr)

iface.nop()
print("Proxy is alive again")

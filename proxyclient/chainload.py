#!/usr/bin/env python3

from setup import *
from tgtypes import *

payload = open(sys.argv[1], "rb").read()

obj = MachO.parse(payload)

vmin, vmax = (1 << 64), 0

entry = None

for cmd in obj.cmds:
    if cmd.cmd == LoadCmdType.SEGMENT_64:
        vmin = min(vmin, cmd.args.vmaddr)
        vmax = max(vmax, cmd.args.vmaddr + cmd.args.vmsize)
    elif cmd.cmd == LoadCmdType.UNIXTHREAD:
        entry = cmd.args[0].data.pc

memory_size = vmax - vmin

# FIXME: this will currently still waste the whole m1n1 size including payload area (64+MB) on each
# chainload. The best way to fix this is to support in-place chainloading, which has other
# advantages.

try:
    # Try to use the m1n1 heap to avoid wasting 128MB RAM on every load
    new_base = p.memalign(0x10000, memory_size)
except:
    # Fall back to proxy heap, which will be at the right place in old versions
    new_base = u.memalign(0x10000, memory_size)

for cmd in obj.cmds:
    if cmd.cmd == LoadCmdType.SEGMENT_64:
        if cmd.args.fileoff == 0:
            continue # do not load mach-o headers, not needed for now
        dest = cmd.args.vmaddr - vmin + new_base
        end = min(len(payload), cmd.args.fileoff + cmd.args.filesize)
        size = end - cmd.args.fileoff
        print("Loading %d bytes from 0x%x to 0x%x" % (size, cmd.args.fileoff, dest))
        iface.writemem(dest, payload[cmd.args.fileoff:end], True)
        if cmd.args.vmsize > size:
            clearsize = cmd.args.vmsize - size
            print("Zeroing %d bytes from 0x%x to 0x%x" % (clearsize, dest + size, dest + size + clearsize))
            p.memset8(dest + size, 0, clearsize)

p.dc_cvau(new_base, memory_size)
p.ic_ivau(new_base, memory_size)

entry -= vmin
entry += new_base

print("Jumping to 0x%x" % entry)

try:
    p.mmu_shutdown()
except:
    pass

p.reboot(entry, u.ba_addr)

iface.nop()
print("Proxy is alive again")

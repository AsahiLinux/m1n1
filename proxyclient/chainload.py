#!/usr/bin/env python3

import argparse, pathlib

parser = argparse.ArgumentParser(description='Mach-O loader for m1n1')
parser.add_argument('payload', type=pathlib.Path)
parser.add_argument('-1', '--el1', action="store_true")
parser.add_argument('-s', '--sepfw', action="store_true")
args = parser.parse_args()

from setup import *
from tgtypes import *
import adt
import asm

payload = args.payload.read_bytes()

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

image = bytearray(memory_size)

new_base = u.base

def align(v, a=16384):
    return (v + a - 1) & ~(a - 1)

for cmdi, cmd in enumerate(obj.cmds):
    is_m1n1 = None
    if cmd.cmd == LoadCmdType.SEGMENT_64:
        if is_m1n1 is None:
            is_m1n1 = cmd.args.segname == "_HDR"
        dest = cmd.args.vmaddr - vmin
        end = min(len(payload), cmd.args.fileoff + cmd.args.filesize)
        size = end - cmd.args.fileoff
        print(f"LOAD: {cmd.args.segname} {size} bytes from {cmd.args.fileoff:x} to {dest + new_base:x}")
        image[dest:dest + size] = payload[cmd.args.fileoff:end]
        if cmd.args.vmsize > size:
            clearsize = cmd.args.vmsize - size
            if cmd.args.segname == "PYLD":
                print("SKIP: %d bytes from 0x%x to 0x%x" % (clearsize, dest + new_base + size, dest + new_base + size + clearsize))
                memory_size -= clearsize - 4 # leave a payload end marker
                image = image[:memory_size]
            else:
                print("ZERO: %d bytes from 0x%x to 0x%x" % (clearsize, dest + new_base + size, dest + new_base + size + clearsize))
                image[dest + size:dest + cmd.args.vmsize] = bytes(clearsize)

entry -= vmin
entry += new_base

if args.sepfw:
    adt_base = u.ba.devtree - u.ba.virt_base + u.ba.phys_base
    adt_size = u.ba.devtree_size
    print(f"Fetching ADT ({adt_size} bytes)...")
    adt = adt.load_adt(iface.readmem(adt_base, u.ba.devtree_size))

    sepfw_start, sepfw_length = adt["chosen"]["memory-map"].SEPFW

else:
    sepfw_start, sepfw_length = 0, 0

image_size = align(len(image))
sepfw_off = image_size
image_size += align(sepfw_length)
bootargs_off = image_size
image_size += 0x4000

print(f"Total region size: 0x{image_size:x} bytes")
image_addr = u.malloc(image_size)

print(f"Loading kernel image (0x{len(image):x} bytes)...")
u.compressed_writemem(image_addr, image, True)
p.dc_cvau(image_addr, len(image))

if args.sepfw:
    print(f"Copying SEPFW (0x{sepfw_length:x} bytes)...")
    p.memcpy8(image_addr + sepfw_off, sepfw_start, sepfw_length)

print(f"Setting up bootargs...")
tba = u.ba.copy()
#tba.phys_base = new_base
#tba.virt_base = 0xfffffe0010000000 + new_base & (32 * 1024 * 1024 - 1)
tba.top_of_kdata = new_base + image_size

iface.writemem(image_addr + bootargs_off, BootArgs.build(tba))

print(f"Copying stub...")

stub = asm.ARMAsm(f"""
1:
        ldp x4, x5, [x1], #8
        stp x4, x5, [x2]
        dc cvau, x2
        ic ivau, x2
        add x2, x2, #8
        sub x3, x3, #8
        cbnz x3, 1b

        ldr x1, ={entry}
        br x1
""", image_addr + image_size)

iface.writemem(stub.addr, stub.data)
p.dc_cvau(stub.addr, stub.len)
p.ic_ivau(stub.addr, stub.len)

if args.el1:
    print("Setting up EL1 config")

    # Enable physical timer for EL1
    u.msr(CNTHCTL_EL2, 3 << 10) # EL1PTEN | EL1PCTEN

    # Unredirect IRQs/FIQs
    u.msr(HCR_EL2, u.mrs(HCR_EL2) & ~(3 << 3)) # ~(IMO | FMO)

print(f"Jumping to stub at 0x{stub.addr:x}")

p.reboot(stub.addr, new_base + bootargs_off, image_addr, new_base, image_size, el1=args.el1)

iface.nop()
print("Proxy is alive again")

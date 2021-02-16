from setup import *
import asm
import struct

'''
total accessible MMIO space is from 0x0 to 0x4000
everything after 0x0300 reads back as zeros

NOTE: some of the registers or bits called "read-only" might still have some meaning
and be flags (e.g. some bit i couldn't set might be a busy flag that was already cleared again 
by the time i read the register the second time)

base
0x00 - 0x20: seems to be read only, any writes are ignored

0x20: can set 0xfff007f3 bits
0x24: can set 0xfffff0f1 bits
0x28: can't set any bits
0x2c: can set 0xefffffff bits

0x30: can set 0xfff0fff
0x34: 0xffff
0x38: can't set any bits
0x3c: can't set any bits

0x40: probably error status. writing to most bits clears them. seems to start at 0x3080000
0x44: read-only, 0x0100_0000, maybe another error status that i haven't triggered yet?
0x48: read-only, 0x3000_0300, maybe another error status that i haven't triggered yet?
0x4c: read-only, 0x0 or 0x1, but can't modify any bits

0x50: read-only, seems to change on translation faults, maybe fault address?
0x54: read-only, 0x0
0x58: read-only, 0x0
0x5c: read-only, 0x0

0x60:
    can set 0x8001ffff bits, initial value was 0x80016100.
    setting 0x400 seems to kill the framebuffer
    setting 0x8000 seems to locked down the DART for further configuration changes

0x64: can set 0xfffffff, no effect observed
0x68: starts at 0xf0f0f, can only clear/set these bits
0x6c: can set 0xffffff, starts at 0x80808

0x70: can set 0x3f3f3f3f, setting to zero breaks translation. maybe some kind of access/enable flags?
    needs at least 0x00010000 for the framebuffer to work
0x74: stuck at zero
0x78: stuck at zero
0x7c: can set 0x7070707, starts at 0x1010101, can clear all bits. no effect observed

0x80: can set bits up to 0xf0f0f0f, starts at 0x03020100. changing the lowest byte breaks disp0
    this seems to remap devices. if i copy the TCR and TBBRs from 0x100/0x200..20c to 0x104/0x210..21c and then set this to 0x03020101 everything still works
0x84: can set bits up to 0xf0f0f0f, starts at 0x07060504
0x88: can set bits up to 0xf0f0f0f, starts at 0x0b0a0908
0x8c: can set bits up to 0xf0f0f0f, starts at 0x0f0e0d0c

0x90 - 0x9c: stuck at 0
0xa0 - 0xac: stuck at 0
0xb0 - 0xbc: stuck at 0 

0xc0: 000cddea -> 000fffff
0xc4: 0f9baee6 -> 0fffffff
0xc8: 000edbd4 -> 001fffff
0xcc: 00000000 -> 00000007

0xd0 - 0xdc: stuck at 0
0xe0 - 0xec: stuck at 0

0xf0: starts as 0, can only set 0x00000001 with no visible effect
0xf4: stuck at 0
0xf8: stuck at 0
0xfc: starts at 0x00007fff, can set 0x0000ffff with no effect, can clear all bits
        bit 0: enables/disables framebuffer. maybe enable/disable one device? would fir the 16 bits
        rest seems to have no effect


from 0x100 to 0x140 there are 16 TCR registers 
    bits that can be set to 1: 0xff1bdf
    0x80 seems to be translation enabled
    0x100 might be another mode or flag (maybe). seems to be used with all TBBRs = 0.


from 0x200 to 0x300 there are 16x4 TTBR regsiters. bits that can be set: 0x8fffffff
    bit 31 indicates an entry is valid
    the lower bits point to l1_pagetable_base>>12

    l1_pagetable_base is a 0x4000 bytes array of 64 bit integers. each entry points to another
    2nd level l2_pagetable_base.
    the lowest bit indicates if an entry is active

    l2_pagetable_base is identical to l1_pagetable_base except that its entries now directly
    point to physical memory. the lowest two bits are set.
'''


class DART:
    def __init__(self, base):
        self.base = base

    def dump_table2(self, base, l1_addr):
        tbl = iface.readmem(l1_addr, 0x4000)

        for i in range(0, len(tbl)//8):
            pte = struct.unpack("<Q",tbl[i*8:i*8+8])[0]
            if not (pte & 0b11):
                continue

            print("    page: %016x ... %016x -> %016x [%s]" % (base + i*0x4000, base + (i+1)*0x4000, pte&~0b11, bin(pte&0b11)))


    def dump_table(self, base, l1_addr):
        tbl = iface.readmem(l1_addr, 0x4000)

        for i in range(0, len(tbl)//8):
            pte = struct.unpack("<Q",tbl[i*8:i*8+8])[0]
            if not (pte & 0b11):
                continue

            print("  table: %016x ... %016x -> %016x [%s]" % (base + i*0x4000*0x4000, base + (i+1)*0x4000*0x4000, pte&~0b11, bin(pte&0b11)))
            self.dump_table2(base + i*0x4000*0x4000, pte & ~0b11)

    def dump_ttbr(self, idx, ttbr):
        if not ttbr & (1<<31):
            return
        
        l1_addr = (ttbr & ~(1<<31)) << 12
        print("  TTBR%d: %09x" % (idx, l1_addr))

        self.dump_table(0, l1_addr)
 

    def dump_device(self, idx):
        tcr = p.read32(self.base + 0x100 + 4*idx)
        ttbrs = [p.read32(self.base + 0x200 + 16*idx + 4*i) for i in range(4)]
        ttbrs_str = " ".join("%08x" % t for t in ttbrs)
        print("dev %02x: TCR=%08x TTBRs = [%s]" % (idx, tcr, ttbrs_str))

        if (tcr & 0x80) and (tcr & 0x100):
            print("  mode: INVALID")
        elif tcr & 0x80:
            print("  mode: TRANSLATE")

            for idx, ttbr in enumerate(ttbrs):
                self.dump_ttbr(idx, ttbr)
        elif tcr & 0x100:
            print("  mode: 0x100, UNKNOWN MODE")
        else:
            print("  mode: UNKNOWN")

    def dump_all(self):
        for i in range(16):
            self.dump_device(i)

# disp0 DART
# note that there's another range just before this one
disp0 = DART(0x231304000)
disp0.dump_all()



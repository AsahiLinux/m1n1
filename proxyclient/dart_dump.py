from setup import *
import asm
import struct

class DART:
    def __init__(self, base):
        self.base = base

    def dump_table2(self, base, l1_addr):
        tbl = iface.readmem(l1_addr, 0x4000)

        for i in range(0, len(tbl)//8):
            pte = struct.unpack("<Q",tbl[i*8:i*8+8])[0]
            if not (pte & 0b01):
                #print("    page (%d): %08x ... %08x -> DISABLED" % (i, base + i*0x4000, base + (i+1)*0x4000))
                continue

            print("    page (%d): %08x ... %08x -> %016x [%s]" % (i, base + i*0x4000, base + (i+1)*0x4000, pte&~0b11, bin(pte&0b11)))

    def dump_table(self, base, l1_addr):
        tbl = iface.readmem(l1_addr, 0x4000)

        for i in range(0, len(tbl)//8):
            pte = struct.unpack("<Q",tbl[i*8:i*8+8])[0]
            if not (pte & 0b01):
                #print("  table (%d): %08x ... %08x -> DISABLED" % (i, base + i*0x2000000, base + (i+1)*0x2000000))
                continue

            print("  table (%d): %08x ... %08x -> %016x [%s]" % (i, base + i*0x2000000, base + (i+1)*0x2000000, pte&~0b11, bin(pte&0b11)))
            self.dump_table2(base + i*0x2000000, pte & ~0b11)

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

if len(sys.argv) > 1:
    dart_addr = int(sys.argv[1], 16)
else:
    dart_addr = 0x231304000
# disp0 DART
# note that there's another range just before this one
disp0 = DART(dart_addr)
disp0.dump_all()

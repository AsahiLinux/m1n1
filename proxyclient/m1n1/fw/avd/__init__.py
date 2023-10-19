# SPDX-License-Identifier: MIT
from ...hw.dart import DART
from ...proxyutils import RegMonitor
from ...utils import *
from .decoder import *

import contextlib
import struct

class AVDDevice:
    def __init__(self, u, dev_path="/arm-io/avd", dart_path="/arm-io/dart-avd"):
        self.u = u
        self.p = u.proxy
        self.iface = u.iface

        self.PAGE_SIZE = 0x4000
        self.base = u.adt[dev_path].get_reg(0)[0] # 0x268000000
        self.node = u.adt[dev_path]

        self.p.pmgr_adt_clocks_enable(dev_path)
        self.p.pmgr_adt_clocks_enable(dart_path)
        dart = DART.from_adt(u, dart_path)
        dart.initialize()
        self.dart = dart

        mon = RegMonitor(u)
        AVD_REGS = [
            #(0x1000000, 0x4000, "unk0"),
            #(0x1010000, 0x4000, "dart"),
            #(0x1002000, 0x1000, "unk2"),
            #(0x1070000, 0x4000, "piodma"),
            #(0x108c000, 0xc000, "cmd"),
            #(0x1098000, 0x4000, "mbox"),
            #(0x10a3000, 0x1000, "unka"),
            (0x1100000, 0xc000, "dec"),
            (0x110c000, 0x4000, "dma"),
            #(0x1400000, 0x4000, "wrap"),
        ]
        for x in AVD_REGS:
            mon.add(self.base + x[0], x[1], name=x[2])
        self.mon = mon

        iomon = RegMonitor(u, ascii=True)
        iomon1 = RegMonitor(u, ascii=True)
        def readmem_iova(addr, size, readfn=None):
            try:
                return self.dart.ioread(0, addr, size)
            except Exception as e:
                print(e)
                return None
        def readmem_iova1(addr, size, readfn=None):
            try:
                return self.dart.ioread(1, addr, size)
            except Exception as e:
                print(e)
                return None
        iomon.readmem = readmem_iova
        iomon1.readmem = readmem_iova1
        self.iomon = iomon
        self.iomon1 = iomon1
        self.stfu = False
        self.decoder = AVDDec(self)

    def log(self, x): print(f"[AVD] {x}")
    def poll(self): self.mon.poll()

    def avd_r32(self, off): return self.p.read32(self.base + off)
    def avd_w32(self, off, x):
        if (not self.stfu):
            self.log("w32(0x%x, 0x%x)" % (off, x))
        return self.p.write32(self.base + off, x)
    def avd_r64(self, off): return self.p.read64(self.base + off)
    def avd_w64(self, off, x): return self.p.write64(self.base + off, x)
    def avd_wbuf(self, off, buf):
        for n in range(len(buf) // 4):
            x = struct.unpack("<I", buf[n*4:(n+1)*4])[0]
            self.p.write32(self.base + off + (n*4), x)

    def boot(self):
        self.avd_w32(0x1000000, 0xfff)
        self.p.mask32(0x269010060, self.p.read32(0x269010060), 0x80016100)
        self.p.mask32(0x269010068, self.p.read32(0x269010068), 0xf0f0f)
        self.p.mask32(0x26901006c, self.p.read32(0x26901006c), 0x80808)
        self.p.memset32(self.base + 0x1080000, 0, 0xc000) # CODE
        self.p.memset32(self.base + 0x108c000, 0, 0xc000) # SRAM
        with contextlib.redirect_stdout(None):
            self.wrap_ctrl_device_init()
            self.avd_dma_tunables_stage0()
        self.poll()

    def avd_mcpu_start(self):
        avd_r32 = self.avd_r32; avd_w32 = self.avd_w32
        avd_w32(0x1098008, 0xe)
        avd_w32(0x1098010, 0x0)
        avd_w32(0x1098048, 0x0)

        avd_w32(0x1098010, 0x0)
        avd_w32(0x1098048, 0x0)

        avd_w32(0x1098050, 0x1)
        avd_w32(0x1098068, 0x1)
        avd_w32(0x109805c, 0x1)
        avd_w32(0x1098074, 0x1)

        avd_w32(0x1098010, 0x2) # Enable mailbox interrupts
        avd_w32(0x1098048, 0x8) # Enable mailbox interrupts
        avd_w32(0x1098008, 0x1)
        assert((avd_r32(0x1098090) == 0x1))
        self.avd_w32(0x1400014, 0x0)

    def mcpu_boot(self, fw):
        if (isinstance(fw, str)):
            fw = open(fw, "rb").read()[:0xc000]
        else:
            fw = fw[:0xc000]
        self.avd_wbuf(0x1080000, fw)
        self.avd_mcpu_start()

    def mcpu_decode_init(self, fw):
        self.mcpu_boot(fw=fw)
        dump = """
        26908ee80: 00000000 00000000 00000000 00000000 04020002 00020002 04020002 04020002
        26908eea0: 04020002 00070007 00070007 00070007 00070007 00070007 04020002 00020002
        26908eec0: 04020002 04020002 04020002 00070007 00070007 00070007 00070007 00070007
        26908eee0: 04020002 02020202 04020002 04020002 04020202 00070007 00070007 00070007
        26908ef00: 00070007 00070007 00000000 00000000 00000000 00000000 00000000 00000000
        """
        for line in dump.strip().splitlines():
            offset = int(line.split()[0].replace(":", ""), 16)
            vals = line.split()[1:]
            for n,arg in enumerate(vals[:8]):
                self.avd_w32(offset + (n*4) - self.base, int(arg, 16))
        self.avd_w32(0x1098054, 0x108eb30)

    def wrap_ctrl_device_init(self):
        avd_w32 = self.avd_w32
        avd_w32(0x1400014, 0x1)
        avd_w32(0x1400018, 0x1)
        avd_w32(0x1070000, 0x0) # PIODMA cfg
        avd_w32(0x1104064, 0x3)
        avd_w32(0x110cc90, 0xffffffff) # IRQ clear
        avd_w32(0x110cc94, 0xffffffff) # IRQ clear
        avd_w32(0x110ccd0, 0xffffffff) # IRQ clear
        avd_w32(0x110ccd4, 0xffffffff) # IRQ clear
        avd_w32(0x110cac8, 0xffffffff) # IRQ clear
        avd_w32(0x1070024, 0x26907000)
        avd_w32(0x1400014, 0x0) # idle thing

    def avd_dma_tunables_stage0(self):
        avd_w32 = self.avd_w32; avd_r32 = self.avd_r32

        avd_w32(0x1070024, 0x26907000)
        avd_w32(0x1400000, 0x3)
        avd_w32(0x1104000, 0x0)
        avd_w32(0x110405c, 0x0)
        avd_w32(0x1104110, 0x0)
        avd_w32(0x11040f4, 0x1555)

        avd_w32(0x1100000, 0xc0000000)
        avd_w32(0x1101000, 0xc0000000)
        avd_w32(0x1102000, 0xc0000000)
        avd_w32(0x1103000, 0xc0000000)
        avd_w32(0x1104000, 0xc0000000)
        avd_w32(0x1105000, 0xc0000000)
        avd_w32(0x1106000, 0xc0000000)
        avd_w32(0x1107000, 0xc0000000)
        avd_w32(0x1108000, 0xc0000000)
        avd_w32(0x1109000, 0xc0000000)
        avd_w32(0x110a000, 0xc0000000)
        avd_w32(0x110b000, 0xc0000000)

        avd_w32(0x110c010, 0x1)
        avd_w32(0x110c018, 0x1)

        avd_w32(0x110c040, avd_r32(0x110c040) | 0xc0000000)
        avd_w32(0x110c080, avd_r32(0x110c080) | 0xc0000000)
        avd_w32(0x110c0c0, avd_r32(0x110c0c0) | 0xc0000000)
        avd_w32(0x110c100, avd_r32(0x110c100) | 0xc0000000)

        avd_w32(0x110c140, avd_r32(0x110c140) | 0xc0000000)
        avd_w32(0x110c180, avd_r32(0x110c180) | 0xc0000000)
        avd_w32(0x110c1c0, avd_r32(0x110c1c0) | 0xc0000000)
        avd_w32(0x110c200, avd_r32(0x110c200) | 0xc0000000)

        avd_w32(0x110c240, avd_r32(0x110c240) | 0xc0000000)
        avd_w32(0x110c280, avd_r32(0x110c280) | 0xc0000000)
        avd_w32(0x110c2c0, avd_r32(0x110c2c0) | 0xc0000000)
        avd_w32(0x110c300, avd_r32(0x110c300) | 0xc0000000)

        avd_w32(0x110c340, avd_r32(0x110c340) | 0xc0000000)
        avd_w32(0x110c380, avd_r32(0x110c380) | 0xc0000000)
        avd_w32(0x110c3c0, avd_r32(0x110c3c0) | 0xc0000000)
        avd_w32(0x110c400, avd_r32(0x110c400) | 0xc0000000)

        avd_w32(0x110c440, avd_r32(0x110c440) | 0xc0000000)
        avd_w32(0x110c480, avd_r32(0x110c480) | 0xc0000000)
        avd_w32(0x110c4c0, avd_r32(0x110c4c0) | 0xc0000000)
        avd_w32(0x110c500, avd_r32(0x110c500) | 0xc0000000)

        avd_w32(0x110c540, avd_r32(0x110c540) | 0xc0000000)
        avd_w32(0x110c580, avd_r32(0x110c580) | 0xc0000000)
        avd_w32(0x110c5c0, avd_r32(0x110c5c0) | 0xc0000000)
        avd_w32(0x110c600, avd_r32(0x110c600) | 0xc0000000)

        avd_w32(0x110c640, avd_r32(0x110c640) | 0xc0000000)
        avd_w32(0x110c680, avd_r32(0x110c680) | 0xc0000000)
        avd_w32(0x110c6c0, avd_r32(0x110c6c0) | 0xc0000000)
        avd_w32(0x110c700, avd_r32(0x110c700) | 0xc0000000)

        avd_w32(0x110c740, avd_r32(0x110c740) | 0xc0000000)
        avd_w32(0x110c780, avd_r32(0x110c780) | 0xc0000000)
        avd_w32(0x110c7c0, avd_r32(0x110c7c0) | 0xc0000000)
        avd_w32(0x110c800, avd_r32(0x110c800) | 0xc0000000)

        avd_w32(0x110c840, avd_r32(0x110c840) | 0xc0000000)
        avd_w32(0x110c880, avd_r32(0x110c880) | 0xc0000000)
        avd_w32(0x110c8c0, avd_r32(0x110c8c0) | 0xc0000000)
        avd_w32(0x110c900, avd_r32(0x110c900) | 0xc0000000)

        avd_w32(0x110c940, avd_r32(0x110c940) | 0xc0000000)
        avd_w32(0x110c980, avd_r32(0x110c980) | 0xc0000000)
        avd_w32(0x110c9c0, avd_r32(0x110c9c0) | 0xc0000000)
        avd_w32(0x110ca00, avd_r32(0x110ca00) | 0xc0000000)

        avd_w32(0x110ca40, avd_r32(0x110ca40) | 0xc0000000)
        avd_w32(0x110ca80, avd_r32(0x110ca80) | 0xc0000000)
        avd_w32(0x110cac0, avd_r32(0x110cac0) | 0xc0000000)
        avd_w32(0x110cb00, avd_r32(0x110cb00) | 0xc0000000)

        avd_w32(0x110cb40, avd_r32(0x110cb40) | 0xc0000000)
        avd_w32(0x110cb80, avd_r32(0x110cb80) | 0xc0000000)
        avd_w32(0x110cbc0, avd_r32(0x110cbc0) | 0xc0000000)
        avd_w32(0x110cc00, avd_r32(0x110cc00) | 0xc0000000)

        avd_w32(0x110cc40, avd_r32(0x110cc40) | 0xc0000000)
        avd_w32(0x110cc80, avd_r32(0x110cc80) | 0xc0000000)
        avd_w32(0x110ccc0, avd_r32(0x110ccc0) | 0xc0000000)
        avd_w32(0x110cd00, avd_r32(0x110cd00) | 0xc0000003)

        avd_w32(0x110c044, 0x40)
        avd_w32(0x110c084, 0x400040)
        avd_w32(0x110c244, 0x800034)
        avd_w32(0x110c284, 0x18)
        avd_w32(0x110c2c4, 0xb40020)
        avd_w32(0x110c3c4, 0xd40030)
        avd_w32(0x110c404, 0x180014)
        avd_w32(0x110c444, 0x104001c)
        avd_w32(0x110c484, 0x2c0014)
        avd_w32(0x110c4c4, 0x1200014)
        avd_w32(0x110c504, 0x400018)
        avd_w32(0x110c544, 0x1340024)
        avd_w32(0x110c584, 0x580014)
        avd_w32(0x110c5c4, 0x1580014)
        avd_w32(0x110c1c4, 0x6c0048)
        avd_w32(0x110c204, 0xb40048)
        avd_w32(0x110c384, 0xfc0038)
        avd_w32(0x110c604, 0x1340030)
        avd_w32(0x110c644, 0x16c00b0)
        avd_w32(0x110c684, 0x21c00b0)
        avd_w32(0x110c844, 0x164001c)
        avd_w32(0x110c884, 0x2cc0028)
        avd_w32(0x110c744, 0x1800018)
        avd_w32(0x110c784, 0x2f40020)
        avd_w32(0x110c7c4, 0x1980018)
        avd_w32(0x110c804, 0x314001c)
        avd_w32(0x110c8c4, 0x1b00024)
        avd_w32(0x110c904, 0x3300040)
        avd_w32(0x110c944, 0x1d4001c)
        avd_w32(0x110c984, 0x370002c)
        avd_w32(0x110c9c4, 0x1f00030)
        avd_w32(0x110ca04, 0x39c003c)
        avd_w32(0x110ca44, 0x2200014)
        avd_w32(0x110ca84, 0x3d80014)
        avd_w32(0x110cb04, 0x2340014)
        avd_w32(0x110cb44, 0x3ec0014)
        avd_w32(0x110cac4, 0x2480080)
        avd_w32(0x110cc8c, 0x2c80014)
        avd_w32(0x110cccc, 0x2dc0014)
        avd_w32(0x110cc88, 0x2f00060)
        avd_w32(0x110ccc8, 0x3500054)
        avd_w32(0x110cb84, 0x3a4001c)
        avd_w32(0x110cbc4, 0x4000040)
        avd_w32(0x110cc04, 0x3c00040)
        avd_w32(0x110cc44, 0x44000c0)

        avd_w32(0x110405c, avd_r32(0x110405c) | 0x500000)
        avd_w32(0x109807c, 0x1)
        avd_w32(0x1098080, 0xffffffff)

    def ioread(self, iova, size, stream=0):
        data = self.dart.ioread(stream, iova & 0xFFFFFFFFFF, size)
        return data

    def iowrite(self, iova, data, stream=0):
        self.dart.iowrite(stream, iova & 0xFFFFFFFFFF, data)

    def iomap_at(self, iova, phys, size, stream):
        self.dart.iomap_at(stream, iova & 0xFFFFFFFFFF, phys, size)

    def ioalloc_at(self, iova, size, stream=0, val=0):
        phys = self.u.heap.memalign(self.PAGE_SIZE, size)
        self.p.memset32(phys, val, size)
        self.dart.iomap_at(stream, iova & 0xFFFFFFFFFF, phys, size)

    def iowrite32(self, iova, val, stream=0):
        data = struct.pack("<I", val)
        self.dart.iowrite(stream, iova & 0xFFFFFFFFFF, data)

    def ioread32(self, iova, stream=0):
        data = self.dart.ioread(stream, iova & 0xFFFFFFFFFF, 0x4)
        return struct.unpack("<I", data)[0]

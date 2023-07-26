# SPDX-License-Identifier: MIT
from ..common import *
from ...utils import align
from ...hw.dart import DART
from ...hw.isp import *

import atexit
from construct import *
import struct
import time

from .isp_chan import ISPChannelTable

class ISPSurface:
    def __init__(self, index, phys, iova, size, name):
        self.index = index
        self.phys = phys
        self.iova = iova
        self.size = size
        self.name = name

    def __str__(self):
        s = 'surface: [name: %s index: %d phys: 0x%x iova: 0x%x size: 0x%x]' % (self.name, self.index, self.phys, self.iova, self.size)
        return s

class ISPMemoryManager:
    def __init__(self, isp, start_index=0x8):
        self.isp = isp
        self.index = start_index
        self.map = {}
        self._stfu = False

    @property
    def stfu(self): self._stfu = True

    def log(self, *args):
        if (not self._stfu):
            if (args): print("ISP: MMGR:", *args)
            else: print()

    def alloc_size(self, size, name="NULL"):
        size = align(size, self.isp.page_size)
        phys = self.isp.u.memalign(self.isp.page_size, size)
        self.isp.p.memset32(phys, 0, size)
        iova = self.isp.dart.iomap(0, phys, size)

        surf = ISPSurface(self.index, phys, iova, size, name)
        self.map[self.index] = surf
        self.log(f'Mapped {surf}')
        self.index += 1
        return surf

    def free_surf(self, surf):
        if (surf.index not in self.map): return
        # this is python, we don't "free"
        self.log(f'Freed {surf}')

    def index_iova(self, iova):
        surf = [self.map[index] for index in self.map if self.map[index].iova == iova]
        if (len(surf) == 1): return surf[0]
        else: return None

    def dump(self):
        for index in self.map:
            surf = self.map[index]
            self.log(surf)


class ISPASC:
    def __init__(self, isp):
        self.isp = isp
        self.regs = self.isp.regs

    def boot(self):
        self.regs.ISP_ASC_CONTROL = 0x0
        self.regs.ISP_ASC_CONTROL = 0x10

    def shutdown(self):
        self.regs.ISP_ASC_CONTROL = 0x0

    def enable_interrupts(self):
        self.regs.ISP_IRQ_ENABLE = 0x0
        self.regs.ISP_IRQ_ENABLE = 0xf

    def disable_interrupts(self):
        self.regs.ISP_IRQ_ENABLE = 0x0

    def is_ready(self):
            status = self.regs.ISP_ASC_STATUS.val
            if (status & 0x3) == 0: # can't be 0x28, 0x2c
                    self.isp.log("ASC not in WFI; status: 0x%x" % status)
                    return False
            # normally 0x2a on first boot, 0x22 after
            self.isp.log("ASC in WFI; status: 0x%x" % status)
            return True

    def reset(self):
        self.regs.ISP_ASC_EDPRCR = 0x2  # I can't tell when this one's actually needed, so we'll do it every time

        self.regs.ISP_PMGR_0 = 0xff00ff
        self.regs.ISP_PMGR_1 = 0xff00ff
        self.regs.ISP_PMGR_2 = 0xff00ff
        self.regs.ISP_PMGR_3 = 0xff00ff

        self.regs.ISP_ASC_POWER_CYCLE_0 = 0xffffffff
        self.regs.ISP_ASC_POWER_CYCLE_1 = 0xffffffff
        self.regs.ISP_ASC_POWER_CYCLE_2 = 0xffffffff
        self.regs.ISP_ASC_POWER_CYCLE_3 = 0xffffffff
        self.regs.ISP_ASC_POWER_CYCLE_4 = 0xffffffff
        self.regs.ISP_ASC_POWER_CYCLE_5 = 0xffffffff

class ISP:
    def __init__(self, u):
        self.u = u
        self.p = u.proxy
        self.PAGE_SIZE = 0x4000
        self.page_size = self.PAGE_SIZE

        self.p.pmgr_adt_clocks_enable("/arm-io/isp")
        self.p.pmgr_adt_clocks_enable("/arm-io/dart-isp")
        self.dart = DART.from_adt(self.u, "/arm-io/dart-isp",
                iova_range=(0x3a28000, 0x20000000))  # +0x4000 extra heap
        self.dart.initialize()

        self.isp_base = u.adt["/arm-io/isp"].get_reg(0)[0]  # 0x22a000000
        self.pwr_base = u.adt["/arm-io/isp"].get_reg(1)[0]  # 0x23b700000
        self.isp_dart0_base = u.adt["/arm-io/dart-isp"].get_reg(0)[0]  # 0x22c0e8000
        self.isp_dart1_base = u.adt["/arm-io/dart-isp"].get_reg(1)[0]  # 0x22c0f4000
        self.isp_dart2_base = u.adt["/arm-io/dart-isp"].get_reg(2)[0]  # 0x22c0fc000

        self.regs = ISPRegs(backend=self.u, base=self.isp_base)
        self.ps = ISPPSRegs(backend=self.u, base=self.pwr_base)

        self.asc = ISPASC(self)
        self.mmger = ISPMemoryManager(self)
        self.table = None
        self.cmd_iova = 0x0
        self.frames = []
        self._stfu = False

    @property
    def stfu(self): self._stfu = True

    def log(self, *args):
        if (not self._stfu):
            if (args): print("ISP:", *args)
            else: print()

    def ioread(self, iova, size):
        data = self.dart.ioread(0, iova & 0xFFFFFFFFFF, size)
        return data

    def iowrite(self, iova, data):
        self.dart.iowrite(0, iova & 0xFFFFFFFFFF, data)

    def iomap(self, phys, size):
        iova = self.dart.iomap(phys, size)
        return iova

    def iomap_at(self, iova, phys, size):
        self.dart.iomap_at(0, iova & 0xFFFFFFFFFF, phys, size)

    def write_tunables(self):
            self.write_fabric_tunables()
            self.write_unk_power_tunables()
            self.write_dapf_tunables()
            self.write_dart_tunables()

    def write_fabric_tunables(self):
        p = self.p
        # Fabric tunables. Should go under tunables_static.c
        p.mask32(self.isp_base + 0x00, 0x10, 0x10)
        p.mask32(self.isp_base + 0x40, 0xffff, 0x50030)
        p.mask32(self.isp_base + 0x44, 0xffff, 0xa0040)
        p.mask32(self.isp_base + 0x400, 0x4, 0x40000001)
        p.mask32(self.isp_base + 0x600, 0x0, 0x1ffffff)
        p.mask32(self.isp_base + 0x738, 0x1ff01ff, 0x2)  # these 4 are used in power reset
        p.mask32(self.isp_base + 0x798, 0x1ff01ff, 0x300008)
        p.mask32(self.isp_base + 0x7f8, 0x1ff01ff, 0x880020)
        p.mask32(self.isp_base + 0x858, 0x1ff01ff, 0x200080)
        p.mask32(self.isp_base + 0x900, 0x1, 0x101)
        p.mask32(self.isp_base + 0x410, 0x100, 0x1100)
        p.mask32(self.isp_base + 0x420, 0x100, 0x1100)
        p.mask32(self.isp_base + 0x430, 0x100, 0x1100)
        p.mask32(self.isp_base + 0x8000, 0x0, 0x9)
        p.mask32(self.isp_base + 0x920, 0x0, 0x80)

    def write_unk_power_tunables(self):
        self.regs.ISP_POWER_UNK_0 = 0x1
        self.regs.ISP_POWER_UNK_1 = 0x80000000
        self.regs.ISP_POWER_UNK_2 = 0x80000000

    def write_dapf_tunables(self):
        p = self.p
        u = self.u
        dapf_cfg = getattr(u.adt['/arm-io/dart-isp'], 'filter-data-instance-0')
        dapf_base = u.adt['/arm-io/dart-isp'].reg[5].addr | 0x200000000
        offset = 0
        while offset < len(dapf_cfg):
                (start, end, _, r0h, r0l, _, r4) = struct.unpack_from('QQBBBBI', buffer=dapf_cfg, offset=offset)
                offset += 24
                p.write32(dapf_base + 0x4, r4)
                p.write32(dapf_base + 0x8, start & 0xFFFFFFFF)
                p.write32(dapf_base + 0xc, start >> 32) # macos does 32 bit writes, can we do 64?
                p.write32(dapf_base + 0x10, end & 0xFFFFFFFF)
                p.write32(dapf_base + 0x14, end >> 32)
                p.write32(dapf_base, (r0h << 4) | r0l)
                dapf_base += 0x40

    def write_dart_tunables(self):
        p = self.p
        isp_dart0_base = self.isp_dart0_base
        isp_dart1_base = self.isp_dart1_base
        isp_dart2_base = self.isp_dart2_base

        p.write32(isp_dart0_base + 0x100, 0x80)
        p.write32(isp_dart0_base + 0x13c, 0x100)

        p.write32(isp_dart1_base + 0xfc, 0x1)
        p.write32(isp_dart1_base + 0x200, self.dart.dart.regs.TTBR[0, 0].val)
        p.write32(isp_dart1_base + 0x2f0, 0x0)
        p.write32(isp_dart1_base + 0x34, 0xffffffff)
        p.write32(isp_dart1_base + 0x20, 0x100000)
        p.mask32(isp_dart1_base + 0x60, 0x10000, 0x80016100)
        p.mask32(isp_dart1_base + 0x68, 0x20202, 0xf0f0f)
        p.mask32(isp_dart1_base + 0x6c, 0x0, 0x80808)
        p.write32(isp_dart1_base + 0x100, 0x80)
        p.write32(isp_dart1_base + 0x13c, 0x20000)

        p.write32(isp_dart2_base + 0xfc, 0x1)
        p.write32(isp_dart2_base + 0x200, self.dart.dart.regs.TTBR[0, 0].val)
        p.write32(isp_dart2_base + 0x2f0, 0x0)
        p.write32(isp_dart2_base + 0x34, 0xffffffff)
        p.write32(isp_dart2_base + 0x20, 0x100000)
        p.mask32(isp_dart2_base + 0x60, 0x10000, 0x80016100)
        p.mask32(isp_dart2_base + 0x68, 0x20202, 0xf0f0f)
        p.mask32(isp_dart2_base + 0x6c, 0x0, 0x80808)
        p.write32(isp_dart2_base + 0x100, 0x80)
        p.write32(isp_dart2_base + 0x13c, 0x20000)

    def sync_ttbr(self):
        # Base ttbr is initialized after first iomap_at(), so copy it now
        self.p.write32(self.isp_dart1_base + 0x200, self.dart.dart.regs.TTBR[0, 0].val)
        self.p.write32(self.isp_dart2_base + 0x200, self.dart.dart.regs.TTBR[0, 0].val)

    def power_on(self):
        self.p.pmgr_adt_clocks_enable("/arm-io/isp")
        self.p.pmgr_adt_clocks_enable("/arm-io/dart-isp")

        # power domains, low -> high
        self.ps.ISP_PS_00 = 0xf
        self.ps.ISP_PS_08 = 0xf
        self.ps.ISP_PS_10 = 0xf
        self.ps.ISP_PS_18 = 0xf
        self.ps.ISP_PS_20 = 0xf
        self.ps.ISP_PS_28 = 0xf
        self.ps.ISP_PS_30 = 0xf
        self.ps.ISP_PS_38 = 0xf
        self.ps.ISP_PS_40 = 0xf
        self.ps.ISP_PS_48 = 0xf
        self.ps.ISP_PS_50 = 0xf
        self.ps.ISP_PS_58 = 0xf
        self.ps.ISP_PS_60 = 0xf

    def power_off(self):
        # power domains, high -> low
        self.ps.ISP_PS_60 = 0x0
        self.ps.ISP_PS_58 = 0x0
        self.ps.ISP_PS_50 = 0x0
        self.ps.ISP_PS_48 = 0x0
        self.ps.ISP_PS_40 = 0x0
        self.ps.ISP_PS_38 = 0x0
        self.ps.ISP_PS_30 = 0x0
        self.ps.ISP_PS_28 = 0x0
        self.ps.ISP_PS_20 = 0x0
        self.ps.ISP_PS_18 = 0x0
        self.ps.ISP_PS_10 = 0xf0017ff # intermediate state for the first three
        self.ps.ISP_PS_08 = 0xf0017ff
        self.ps.ISP_PS_00 = 0x7ff
        self.ps.ISP_PS_10 = 0x0 # now turn them off
        self.ps.ISP_PS_08 = 0x0
        self.ps.ISP_PS_00 = 0x0

        self.regs.ISP_DPE_UNK_1 = 0x103
        self.regs.ISP_DPE_UNK_0 = 0xc03  # self.p.mask32(0x22c504000, 0xc01, 0xc03)

    def initialize_firmware(self):

        # Stage0
        # =============================================================================
        """
        iova memory map

        0x0000000 - 0x09b4000; 0x09b4000: fw __TEXT
        0x09b4000 - 0x0dd0000; 0x041c000: fw __DATA
        0x0dd0000 - 0x1800000; 0x0a30000: internal heap fw uses for (fw) code execution
        0x1800000 - 0x1804000; 0x0004000: not mapped
        0x1804000 - 0x1820000; 0x001c000: ipc channels; see stage3()
        0x1820000 - 0x1824000; 0x0004000: not mapped
        0x1824000 - 0x3a24000; 0x2200000: extra heap requested by fw at boot
        """

        # text_phys = 0x8009e8000; text_iova = 0x000000; text_size = 0x9b4000;
        # data_phys = 0x8019b8000; data_iova = 0x9b4000; data_size = 0x41c000;
        (text_phys, text_iova, _, text_size, data_phys, data_iova, _, data_size) = struct.unpack('<QQQI4xQQQI4x', getattr(self.u.adt['/arm-io/isp'], 'segment-ranges'))
        self.iomap_at(text_iova, text_phys, text_size)
        self.iomap_at(data_iova, data_phys, data_size)

        heap_iova = data_iova + data_size # 0xdd0000
        heap_size = 0xa30000  # TODO I dont know if this is set
        heap_phys = self.u.heap.memalign(self.PAGE_SIZE, heap_size)
        self.p.memset32(heap_phys, 0, heap_size)
        self.iomap_at(heap_iova, heap_phys, heap_size)
        self.sync_ttbr()


        # Stage1
        # =============================================================================
        self.regs.ISP_SENSOR_CLOCK_0_EN = 0x1
        self.regs.ISP_GPIO_0 = 0x0
        self.regs.ISP_GPIO_1 = 0x0
        self.regs.ISP_GPIO_2 = 0x0
        self.regs.ISP_GPIO_3 = 0x0
        self.regs.ISP_GPIO_4 = 0x0
        self.regs.ISP_GPIO_5 = 0x0
        self.regs.ISP_GPIO_6 = 0x0
        self.regs.ISP_GPIO_7 = 0x0

        self.asc.boot()

        # Await ISP_GPIO_7 to 0x0 -> 0x8042006
        self.regs.ISP_GPIO_7 = 0x0  # Signal to fw
        for n in range(100):
                if (self.regs.ISP_GPIO_7.val == 0x8042006):
                        self.log('Got first magic number from firmware')
                        break
                time.sleep(0.01)
        assert((self.regs.ISP_GPIO_7.val == 0x8042006))

        ipc_chan_count = self.regs.ISP_GPIO_0.val  # 0x7
        ipc_args_offset = self.regs.ISP_GPIO_1.val  # 0xef40
        unk_2 = self.regs.ISP_GPIO_2.val  # 0x1
        extra_size = self.regs.ISP_GPIO_3.val  # 0x2200000; fw requested extra heap
        unk_4 = self.regs.ISP_GPIO_4.val  # 0x0
        assert((ipc_chan_count == 0x7))


        # Stage2
        # =============================================================================

        # Allocate IPC region
        ipc_iova = (heap_iova + heap_size) + 0x4000  # 0x1804000
        ipc_size = 0x1c000
        ipc_phys = self.u.heap.memalign(self.PAGE_SIZE, ipc_size)
        self.p.memset32(ipc_phys, 0, ipc_size)
        self.iomap_at(ipc_iova, ipc_phys, ipc_size)

        # Allocate extra heap requested by fw
        extra_iova = (ipc_iova + ipc_size) + 0x4000  # 0x1824000
        extra_phys = self.u.heap.memalign(self.PAGE_SIZE, extra_size)
        self.p.memset32(extra_phys, 0, extra_size)
        self.iomap_at(extra_iova, extra_phys, extra_size)

        bootargs_iova = (ipc_iova + ipc_args_offset) + 0x40  # (0x1824000 + 0xef40) + 0x40; 0x1812f80
        cmd_iova = (bootargs_iova + ISPIPCBootArgs.sizeof()) + 0x40  # (0x1812f80 + 0x180) + 0x40; 0x1813140
        self.cmd_iova = cmd_iova

        bootargs = ISPIPCBootArgs.build(dict(
                ipc_iova=ipc_iova,
                unk0=0x1800000,
                unk1=0xe800000,
                extra_iova=extra_iova,
                extra_size=extra_size,
                unk4=0x1,
                ipc_size=ipc_size,
                unk5=0x40,
                unk6=0x0,
                unk7=0x1,
                unk_iova=bootargs_iova+0x174,  # 0x18130f4; 0x180?
                unk9=0x3,
        ))
        self.iowrite(bootargs_iova, bootargs)

        self.regs.ISP_GPIO_0 = bootargs_iova
        self.regs.ISP_GPIO_1 = 0x0

        # Await ISP_GPIO_7 to 0xf7fbdff9 -> 0x8042006
        self.regs.ISP_GPIO_7 = 0xf7fbdff9  # Signal to fw
        for n in range(100):
                if (self.regs.ISP_GPIO_7.val == 0x8042006):
                        self.log('Got second magic number from firmware')
                        break
                time.sleep(0.01)
        assert((self.regs.ISP_GPIO_7.val == 0x8042006))


        # Stage3
        # =============================================================================

        table_iova = self.regs.ISP_GPIO_0.val  # 0x1804000
        unk_1 = self.regs.ISP_GPIO_1.val  # 0x0
        self.log("IPC channel description table at iova 0x%x" % table_iova)

        ipc_width = ISPIPCChanTableDescEntry.sizeof()  # 0x100
        table_data = self.ioread(table_iova, ipc_chan_count*ipc_width)
        description = []
        for n in range(ipc_chan_count):
                chan_data = table_data[n*ipc_width:(n+1)*ipc_width]
                desc = ISPIPCChanTableDescEntry.parse(chan_data)
                description.append(desc)
        self.table = ISPChannelTable(self, description)

        for chan in self.table.channels:
            if (chan.type == 0):  # IO, DEBUG, BUF_H2T
                for n in range(chan.num):
                    iova = chan.iova + (n * 0x40)
                    patch = struct.pack("<q", 0x1) + (struct.pack("<q", 0x0)*7)
                    self.iowrite(iova, patch)

        # Await ISP_GPIO_3 to 0x8042006 -> 0x0
        self.regs.ISP_GPIO_3 = 0x8042006  # Signal to fw
        for n in range(100):
                if (self.regs.ISP_GPIO_3.val == 0x0):
                        self.log('Got third magic number from firmware')
                        break
                time.sleep(0.01)
        assert((self.regs.ISP_GPIO_3.val == 0x0))

    def boot(self):
        self.power_on()
        self.write_tunables()

        self.asc.reset()
        assert(self.asc.is_ready())

        self.initialize_firmware()
        self.asc.enable_interrupts()
        atexit.register(self.shutdown)
        self.log("Firmware booted!")

        self.table.io.stfu
        self.table.bufh2t.stfu
        self.table.sharedmalloc.stfu
        self.table.sharedmalloc.handler()  # TODO don't hardcode this here
        self.log("Ready!")

    def shutdown(self):
        self.asc.disable_interrupts()
        self.asc.shutdown()
        self.power_off()

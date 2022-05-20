# SPDX-License-Identifier: MIT
from ..fw.agx.initdata import *
from ..fw.agx.channels import channelNames, ChannelInfo, Channel
from ..hw.uat import MemoryAttr

def build_iomappings(agx):
    def iomap(phys, size, range_size, rw):
        off = phys & 0x3fff
        virt = agx.io_allocator.malloc(size + 0x4000 + off)
        agx.uat.iomap_at(0, virt, phys - off, size + off, AttrIndex=MemoryAttr.Device)
        return IOMapping(phys, virt + off, size, range_size, rw)

    # for t8103
    return [
        iomap(0x204d00000, 0x1c000, 0x1c000, 1),
        iomap(0x20e100000, 0x4000, 0x4000, 0),
        iomap(0x23b104000, 0x4000, 0x4000, 1),
        iomap(0x204000000, 0x20000, 0x20000, 1),
        IOMapping(),
        IOMapping(),
        IOMapping(),
        iomap(0x23b2e8000, 0x1000, 0x1000, 0),
        iomap(0x23bc00000, 0x1000, 0x1000, 1),
        iomap(0x204d80000, 0x5000, 0x5000, 1),
        iomap(0x204d61000, 0x1000, 0x1000, 1),
        iomap(0x200000000, 0xd6400, 0xd6400, 1),
        IOMapping(),
        iomap(0x23b738000, 0x1000, 0x1000, 1),
        IOMapping(),
        IOMapping(),
        IOMapping(),
        IOMapping(),
        IOMapping(),
        IOMapping(),
    ]

def build_initdata(agx):
    initdata = agx.kobj.new(InitData)

    initdata.regionA = agx.kobj.new(Bytes(12), name="InitData_RegionA").push()

    regionB = agx.kobj.new(InitData_RegionB)

    regionB.channels = Channels()
    for name in channelNames:
        chan = ChannelInfo()
        chan.state_addr = 0xdeadbeef # kshared
        chan.ringbuffer_addr = 0xdeadbeef # kshared for gpu->gpu
        regionB.channels[name] = chan

    # size 0xc0, empty
    regionB.unkptr_170 = agx.kobj.buf(0x140, "RegionB.unkptr_170")

    # size: 0x1c0, has random negative 1s, Needed for login screen
    regionB.unkptr_178 = agx.kobj.buf(0x1c0, "RegionB.unkptr_178")

    # 0xffffffff -> +0x108
    # 0xffffffff -> +0x120

    # size: 0x140, Empty
    regionB.unkptr_180 = agx.kobj.buf(0x140, "RegionB.unkptr_180")

    # size: 0x3b80, few floats, few ints, needed for init
    regionB.unkptr_188 = agx.kobj.new(RegionB_unkprt_188).push()

    # size: 0x80, empty
    regionB.unkptr_190 = agx.kobj.buf(0x80, "RegionB.unkptr_190")

    # size: 0xc0, fw writes timestamps into this
    regionB.unkptr_198 = agx.kobj.new(Bytes(0xc0), name="RegionB.unkptr_198").push()

    # size: 0xb80, io stuff
    unk1a0 = agx.kobj.new(RegionB_unkprt_1a0)
    unk1a0.io_mappings = build_iomappings(agx)

    regionB.unkptr_1a0 = unk1a0.push()
    regionB.unkptr_1a8 = unk1a0._addr

    regionB.fwlog_ring2 = agx.kshared.buf(0x51000, "Firmware log rings")

    # Unallocated, Size 0x1000
    regionB.unkptr_1b8 = agx.kobj.buf(0x1000, "RegionB.unkptr_1b8")

    # Unallocated, size 0x300
    regionB.unkptr_1c0 = agx.kobj.buf(0x300, "RegionB.unkptr_1c0")

    # Unallocated, unknown size
    regionB.unkptr_1c8 = agx.kobj.buf(0x1000, "RegionB.unkptr_1c8")

    # Size: 0x4000
    regionB.unkptr_214 = agx.kobj.buf(0x4000, "Shared AP=0 region")
    regionB.unkptr_21c = regionB.unkptr_214

    initdata.regionB = regionB.push()

    initdata.regionC_addr = agx.kshared.buf(0x88000, "RegionC")

    #self.regionC_addr = agx.ksharedshared_heap.malloc(0x88000)

    initdata.unkptr_20 = agx.kobj.new(InitData_unkptr20)
    initdata.unkptr_20.unkptr_0 = agx.kobj.buf(0x40, "initdata.unkptr_20.unkptr_0")
    # totally guessing the size on this one
    initdata.unkptr_20.unkptr_8 = agx.kobj.buf(0x40, "initdata.unkptr_20.unkptr_8")
    initdata.unkptr_20.push()

    ## This section seems to be data that would be used by firmware side page allocation
    ## But the current firmware doesn't have this functionality enabled, so it's not used?
    initdata.uat_num_levels = 3
    initdata.uat_page_bits = 14
    initdata.uat_page_size = 0x4000

    initdata.uat_level_info = [
        UatLevelInfo(36, 8),
        UatLevelInfo(25, 2048),
        UatLevelInfo(14, 2048),
    ]

    # Host handles FW allocations for existing firmware versions
    initdata.host_mapped_fw_allocations = 1

    initdata.push()
    return initdata

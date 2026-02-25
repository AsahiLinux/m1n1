#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct
from construct import *
from copy import deepcopy
from m1n1.setup import *
from m1n1.shell import run_shell
from m1n1.fw.asc import StandardASC
from m1n1.fw.asc.base import ASCBaseEndpoint, msg_handler
from m1n1.utils import *
from m1n1.hw.dart import DART

def round_up(x, y): return ((x + (y - 1)) & (-y))
def round_down(x, y): return (x - (x % y))

AOPBootargsItem = Struct(
    "key" / PaddedString(4, "utf8"),
    "size" / Int32ul,
)

class AOPBootargs:
    def __init__(self, bytes_):
        self.blob = bytearray(bytes_)
        self.index = self.build_index(self.blob)

    def build_index(self, blob):
        off = 0
        fields = []
        while off < len(blob):
            item = AOPBootargsItem.parse(blob[off:off+AOPBootargsItem.sizeof()])
            off += AOPBootargsItem.sizeof()
            fields.append((item.key, (off, item.size)))
            off += item.size
        if off > len(blob):
            raise ValueError('blob overran during parsing')
        return dict(fields)

    def items(self):
        for key, span in self.index.items():
            off, length = span
            yield key, self.blob[off:off + length]

    def __getitem__(self, key):
        off, length = self.index[key]
        return bytes(self.blob[off:off + length])

    def __setitem__(self, key, value):
        off, length = self.index[key]
        if type(value) is int:
            value = int.to_bytes(value, length, byteorder='little')
        elif type(value) is str:
            value = value.encode('ascii')
        if len(value) > length:
            raise ValueError(f'field {key:s} overflown')
        self.blob[off:off + length] = value

    def update(self, keyvals):
        for key, val in keyvals.items():
            self[key] = val

    def keys(self):
        return self.index.keys()

    def dump(self, logger):
        for key, val in self.items():
            logger(f"{key:4s} = {val}")

    def dump_diff(self, other, logger):
        assert self.index == other.index
        for key in self.keys():
            if self[key] != other[key]:
                logger(f"\t{key:4s} = {self[key]} -> {other[key]}")

    def to_bytes(self):
        return bytes(self.blob)

class AOPBase:
    def __init__(self, u):
        self.u = u
        self.nub_base = u.adt["/arm-io/pmp/iop-pmp-nub"].region_base

    @property
    def _bootargs_span(self):
        """
        [cpu1] MMIO: R.4   0x24ac0022c (aop[2], offset 0x22c) = 0xaffd8 // offset
        [cpu1] MMIO: R.4   0x24ac00230 (aop[2], offset 0x230) = 0x2ae // size
        [cpu1] MMIO: R.4   0x24ac00234 (aop[2], offset 0x234) = 0x82000 // va? low
        [cpu1] MMIO: R.4   0x24ac00238 (aop[2], offset 0x238) = 0x0 // va? high
        [cpu1] MMIO: R.4   0x24ac0023c (aop[2], offset 0x23c) = 0x4ac82000 // phys low
        [cpu1] MMIO: R.4   0x24ac00240 (aop[2], offset 0x240) = 0x2 // phys high
        [cpu1] MMIO: W.4   0x24acaffd8 (aop[2], offset 0xaffd8) = 0x53544b47 // start of bootargs
        [cpu1] MMIO: W.4   0x24acaffdc (aop[2], offset 0xaffdc) = 0x8
        [cpu1] MMIO: W.4   0x24acaffe0 (aop[2], offset 0xaffe0) = 0x73eed2a3
        ...
        [cpu1] MMIO: W.4   0x24acb0280 (aop[2], offset 0xb0280) = 0x10000
        [cpu1] MMIO: W.4   0x24acb0284 (aop[2], offset 0xb0284) = 0x0 // end of bootargs
        """
        offset = self.u.proxy.read32(self.nub_base + 0x22c) # 0x224 in 12.3
        size = self.u.proxy.read32(self.nub_base + 0x230) # 0x228 in 12.3
        return (self.nub_base + offset, size)

    def read_bootargs(self):
        addr, size = self._bootargs_span
        blob = self.u.proxy.iface.readmem(addr, size)
        return AOPBootargs(blob)

    def write_bootargs(self, args):
        base, _ = self._bootargs_span
        self.u.proxy.iface.writemem(base, args.to_bytes())

    def update_bootargs(self, keyval, logger=print):
        args = self.read_bootargs()
        old = deepcopy(args)
        args.update(keyval)
        self.write_bootargs(args)
        old.dump_diff(args, logger)

class PMPMessage(Register64):
    TYPE = 56, 48

class PMPMessage_IOVATableAck(PMPMessage):
    TYPE = 56, 48, Constant(0x11)
    IOVA = 47, 0

class PMPMessage_Malloc(PMPMessage):
    TYPE = 56, 48, Constant(0x12)
    SIZE = 23, 0

class PMPMessage_MallocAck(PMPMessage):
    TYPE = 56, 48, Constant(0x13)
    IOVA = 47, 0

class PMPMessage_Free(PMPMessage):
    TYPE = 56, 48, Constant(0x14)
    IOVA = 47, 0

class PMPMessage_SetBuf(PMPMessage):
    TYPE = 56, 48, Constant(0x30)
    IOVA = 47, 0

class PMPMessage_Advertise(PMPMessage):
    TYPE = 56, 48, Constant(0x32)
    IOVA = 47, 0

class PMPMessage_AdvertiseAck(PMPMessage):
    TYPE = 56, 48, Constant(0x33)
    INDEX = 47, 32
    SIZE = 31, 0

class PMPMessage_SetVal(PMPMessage):
    TYPE = 56, 48, Constant(0x34)
    INDEX = 15, 0

class PMPMessage_SetValAck(PMPMessage):
    TYPE = 56, 48, Constant(0x35)
    SIZE = 31, 0

class PMPEp(ASCBaseEndpoint):
    BASE_MESSAGE = PMPMessage
    SHORT = "pmp"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allocs = {}
        self.ioregs = []

    @msg_handler(0x10, PMPMessage)
    def GetIOVATable(self, msg):
        self.log(f'IovaTable: {msg}')
        table, table_dva = self.asc.ioalloc(512)
        self.asc.iowrite(table_dva, b'\0' * 512)
        pio_base = u.adt["/arm-io/dart-pmp"].pio_vm_base
        granularity = u.adt["/arm-io/dart-pmp"].pio_granularity
        i = 0
        for j in range(4, len(u.adt["/arm-io/pmp"].reg)):
            host_addr, size = u.adt["/arm-io/pmp"].get_reg(j)
            self.asc.dart.iomap_at(0, pio_base, host_addr, size)
            self.asc.dart.invalidate_streams(1)
            self.asc.iowrite(table_dva + 24 * i, struct.pack("<QQQ", host_addr, pio_base, size))
            pio_base += granularity
            i += 1
        self.send(PMPMessage_IOVATableAck(IOVA=table_dva))
    @msg_handler(0x12, PMPMessage_Malloc)
    def Malloc(self, msg):
        self.log(f'Malloc: {msg}')
        addr, dva = self.asc.ioalloc(msg.SIZE)
        self.allocs[dva] = addr
        self.send(PMPMessage_MallocAck(IOVA=dva))
    @msg_handler(0x14, PMPMessage_Free)
    def Free(self, msg):
        self.log(f'Free: {msg}')
        #i dont think we can
        self.send(PMPMessage(TYPE=0x15))

    @msg_handler(0x30, PMPMessage_SetBuf)
    def SetBuf(self, msg):
        self.log(f'SetBuf: {msg}')
        self.buf_ptr, _ = struct.unpack("<QQ", self.asc.ioread(msg.IOVA, 16))
        self.send(PMPMessage(TYPE=0x31))
    @msg_handler(0x32, PMPMessage_Advertise)
    def Advertise(self, msg):
        self.log(f'Advertise: {msg}')
        data = self.asc.ioread(msg.IOVA, 0x50)
        name = data[:0x30] + b'\0'
        size = struct.unpack("<I", data[0x40:0x44])[0]
        if size == 0:
            i = 0
            print(name)
            while name[i] != 0:
                i += 1
            name = name[:i].decode()
            self.log(f"Reading prop {name}")
            data = getattr(u.adt["/arm-io/pmp/iop-pmp-nub"], name, None)
            if data is None:
                self.log("unknown property")
                size = 0
            else:
                if isinstance(data, int):
                    if data > 0xffffffff:
                        data = struct.pack("<Q", data)
                    else:
                        data = struct.pack("<I", data)
                self.asc.iowrite(self.buf_ptr, data)
                size = len(data)
        self.ioregs.append(size)
        index = len(self.ioregs)
        self.send(PMPMessage_AdvertiseAck(INDEX=index, SIZE=size))

    @msg_handler(0x34, PMPMessage_SetVal)
    def SetVal(self, msg):
        self.log(f'SetVal: {msg}')
        self.send(PMPMessage_SetValAck(SIZE=self.ioregs[msg.INDEX]))


class PMPClient(StandardASC, AOPBase):
    ENDPOINTS = {0x20: PMPEp}
    def __init__(self, u, dev_path, dart=None):
        node = u.adt[dev_path]
        asc_base = node.get_reg(0)[0]
        AOPBase.__init__(self, u)
        super().__init__(u, asc_base, dart)
        self.dart = dart

if u.adt['/arm-io'].compatible[0].startswith('arm-io,t8103'):
    print("you have a pmp v1, this script is for v2 only")
    exit(1)
elif u.adt['/arm-io'].compatible[0].startswith('arm-io,t600'):
    p.write64(0x28e3d07c0, 0x1000)
elif u.adt['/arm-io'].compatible[0].startswith('arm-io,t602'):
    p.write64(0x28e3d1000, 0x2000)
elif u.adt['/arm-io'].compatible[0].startswith('arm-io,t8112'):
    p.write64(0x23b3d0500, 0x80)
else:
    print("FIXME: put the correct SOC-DEV-PS-REQ offset for your machine here")
    exit(1)

dart = DART.from_adt(u, "/arm-io/dart-pmp")
dart.verbose = 1
dart.initialize()

pmp = PMPClient(u, "/arm-io/pmp", dart)
pmp.verbose = 4
pmp.update_bootargs({
     'BDID'[::-1]: u.adt['/chosen'].board_id,
     'DCAP'[::-1]: u.adt["/arm-io/pmp/iop-pmp-nub"].dram_capacity,
     'DVID'[::-1]: u.adt['/chosen'].dram_vendor_id,
})
p.dapf_init_all()

pmp.start()
pmp.start_ep(0x20)
pmp.work_for(10)

run_shell(locals(), poll_func=pmp.work)

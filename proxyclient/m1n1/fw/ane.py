# SPDX-License-Identifier: MIT

import struct

from m1n1.hw.dart import DART
from m1n1.hw.ane import ANERegs, ANEDARTRegs, ANETaskManager


class ANE:

	PAGE_SIZE = 0x4000
	TILE_SIZE = 0x4000

	def __init__(self, u):
		self.u = u
		self.p = u.proxy

		self.name = "ane"
		self.p.pmgr_adt_clocks_enable(f'/arm-io/{self.name}')
		self.p.pmgr_adt_clocks_enable(f'/arm-io/dart-{self.name}')

		self.base_addr = u.adt[f'arm-io/{self.name}'].get_reg(0)[0]
		self.regs = ANERegs(self.u, self.base_addr)
		self.apply_static_tunables()

		ps_map = {
			"ane":  0x023b70c000,
			"ane0": 0x028e08c000,
			"ane1": 0x028e684000,
			"ane2": 0x228e08c000,
			"ane3": 0x228e684000,
		}
		self.ps_base_addr = ps_map[self.name]

		# we need a slight patch to dart
		self.dart = DART.from_adt(u, path=f'/arm-io/dart-{self.name}',
					instance=0, iova_range=(0x4000, 0xe0000000))
		self.dart.initialize()
		dart_regs = []
		for prop in range(3):
			dart_addr = self.u.adt[f'/arm-io/dart-{self.name}'].get_reg(prop)[0]
			dart_regs.append(ANEDARTRegs(self.u, dart_addr))
		self.dart_regs = dart_regs

		# hack to initialize base ttbr
		phys = self.u.memalign(self.PAGE_SIZE, self.PAGE_SIZE)
		self.dart.iomap_at(0, 0x0, phys, self.PAGE_SIZE)
		self.ttbr0_addr = self.dart.regs.TTBR[0, 0].val
		self.dart_regs[1].TTBR[0, 0].val = self.ttbr0_addr  # DMA fails w/o
		self.dart_regs[2].TTBR[0, 0].val = self.ttbr0_addr  # DMA fails w/o

		self.allocator = ANEAllocator(self)
		self.fw = ANEFirmware(self)
		self.tm = ANETaskManager(self)

	def apply_static_tunables(self):  # this cost me a solid week
		static_tunables_map = [
			(0x0, 0x10), (0x38, 0x50020), (0x3c, 0xa0030),
			(0x400, 0x40010001), (0x600, 0x1ffffff),
			(0x738, 0x200020), (0x798, 0x100030),
			(0x7f8, 0x100000a), (0x900, 0x101), (0x410, 0x1100),
			(0x420, 0x1100), (0x430, 0x1100)]
		for (offset, value) in static_tunables_map:
			self.p.write32(self.base_addr + offset, value)

	def power_up(self):
		self.p.pmgr_adt_clocks_enable(f'/arm-io/{self.name}')
		self.p.pmgr_adt_clocks_enable(f'/arm-io/dart-{self.name}')
		self.power_down()
		for offset in range(0x0, 0x30+0x8, 0x8):
			self.p.write32(self.ps_base_addr + offset, 0xf)
		self.tm.reset()

	def power_down(self):
		for offset in reversed(range(0x0, 0x30+0x8, 0x8)):
			self.p.write32(self.ps_base_addr + offset, 0x300)

	def ioread(self, iova, size):
		return self.dart.ioread(0, iova & 0xffffffff, size)

	def iowrite(self, iova, buf):
		self.dart.iowrite(0, iova & 0xffffffff, buf)

	def round_up(self, x, y): return ((x+(y-1)) & (-y))


class ANEBuffer:
	def __init__(self, mapid, phys, iova, size):
		self.mapid = mapid
		self.phys = phys
		self.iova = iova
		self.size = size


class ANEAllocator:
	def __init__(self, ane):
		self.ane = ane
		self.mapid = 0
		self.map = {}

	def alloc_size(self, size):
		size = self.ane.round_up(size, self.ane.PAGE_SIZE)
		phys = self.ane.u.memalign(self.ane.PAGE_SIZE, size)
		self.ane.p.memset32(phys, 0, size)
		iova = self.ane.dart.iomap(0, phys, size)

		buf = ANEBuffer(self.mapid, phys, iova, size)
		self.map[self.mapid] = buf
		print("mapid %d: mapped phys 0x%x to iova 0x%06x for data w/ size 0x%06x"
			  % (buf.mapid, buf.phys, buf.iova, buf.size))
		self.mapid += 1
		return buf.iova

	def alloc_data(self, data):
		iova = self.alloc_size(len(data))
		self.ane.iowrite(iova, data)
		return iova

	def dump_map(self):
		for mapid in self.map:
			buf = self.map[mapid]
			print('mapid %d: phys 0x%x, iova 0x%x, size 0x%x'
				  % (buf.mapid, buf.phys, buf.iova, buf.size))


class ANEEngineReq:
	def __init__(self, anec):
		self.anec = anec
		self.td_size = 0
		self.td_count = 0
		self.fifo_iova = 0
		self.nid = 0
		self.qid = 0
		self.bar = [0x0] * 0x20


class ANEFirmware:

	FIFO_NID = 0x40
	FIFO_COUNT = 0x20
	FIFO_WIDTH = 0x400  # nextpow2(0x274)

	def __init__(self, ane):
		self.ane = ane

	def setup(self, anec):
		req = ANEEngineReq(anec)
		req.td_size = anec.td_size
		req.td_count = anec.td_count

		# setup immutable bar
		tsk_buf = anec.data[anec.tsk_start:anec.tsk_start+anec.tsk_size]
		req.bar[0] = self.ane.allocator.alloc_data(tsk_buf)
		krn_start = anec.tsk_start + self.ane.round_up(anec.tsk_size, 0x10)
		krn_buf = anec.data[krn_start:krn_start+anec.krn_size]
		req.bar[1] = self.ane.allocator.alloc_data(krn_buf)

		# setup mutable bar
		for bdx in range(0x20):
			if ((anec.tiles[bdx]) and (bdx >= 3)):
				size = anec.tiles[bdx] * self.ane.TILE_SIZE
				req.bar[bdx] = self.ane.allocator.alloc_size(size)

		self.make_fifo(req)
		return req

	def make_fifo(self, req):
		anec = req.anec
		pool_size = self.ane.round_up(self.FIFO_WIDTH * 2, self.ane.TILE_SIZE)
		fifo_iova = self.ane.allocator.alloc_size(pool_size)

		td_buf = anec.data[anec.tsk_start:anec.tsk_start+anec.td_size]
		fifo_head = self.set_nid(td_buf, self.FIFO_NID)
		fifo_tail = self.set_nid(td_buf, self.FIFO_NID + self.FIFO_COUNT)
		self.ane.iowrite(fifo_iova, fifo_head)
		self.ane.iowrite(fifo_iova + self.FIFO_WIDTH, fifo_tail)

		req.fifo_iova = fifo_iova
		req.nid = self.FIFO_NID
		req.qid = 4  # just the default queue

	def set_nid(self, td_buf, nid):
		hdr0 = struct.unpack('<L', td_buf[:4])[0]
		hdr0 = (hdr0 & 0xf00ffff) | ((nid & 0xff) << 16)
		return struct.pack('<L', hdr0) + td_buf[4:]

	def send_src(self, req, src_buf, idx):
		iova = req.bar[4 + req.anec.dst_count + idx]
		size = req.anec.src_sizes[idx]
		if (len(src_buf) < size):
			src_buf += b''*(size - len(src_buf))
		self.ane.iowrite(iova, src_buf[:size])

	def read_dst(self, req, idx):
		iova = req.bar[4 + idx]
		size = req.anec.dst_sizes[idx]
		return self.ane.ioread(iova, size)

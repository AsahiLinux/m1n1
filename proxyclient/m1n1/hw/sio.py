from enum import IntEnum
from construct import Struct, Default, Container, Int32ul

import traceback
from m1n1.setup import * # remove

from m1n1.utils import *
from m1n1.hw.dart import DART
from m1n1.fw.asc import StandardASC, ASCBaseEndpoint, ASCTimeout
from m1n1.fw.asc.base import msg_handler

class SIOMessage(Register64):
	DATA  = 63, 32
	PARAM = 31, 24
	TYPE  = 23, 16
	TAG   = 13, 8
	EP    = 7, 0

class SIOStart(SIOMessage):
	TYPE = 23, 16, Constant(2)

class SIOSetup(SIOMessage):
	TYPE = 23, 16, Constant(3)

class SIOReadyChannel(SIOMessage):
	TYPE = 23, 16, Constant(5)

class SIOIssueDescriptor(SIOMessage):
	TYPE = 23, 16, Constant(6)

class SIOTerminate(SIOMessage):
	TYPE = 23, 16, Constant(8)

class SIOAck(SIOMessage):
	TYPE = 23, 16, Constant(0x65)

class SIONack(SIOMessage):
	TYPE = 23, 16, Constant(0x66)

class SIOStarted(SIOMessage):
	TYPE = 23, 16, Constant(0x67)

class SIODescriptorDone(SIOMessage):
	TYPE = 23, 16, Constant(0x68)

class SIOShmem(IntEnum):
	MAIN = 0x1

	UNK_0b = 0xb  # macos size: 0x1b80
	UNK_0f = 0xf  # 0x1e000
	MAP_RANGE = 0x1a # 0x50
	DEVICE_TYPE = 0x1c # 0x40
	ASIO_TUNABLES = 0x1e # 0x30
	DMASHIM_DATA = 0x22 # 0xa0

	UNK_EP3_0d = 0x3_0d  # 0x4000

class SIOChannel:
	def __init__(self, parent, channo):
		self.p = parent
		self.ch = channo

SIOChannelConfig = Struct(
	"datashape" / Default(Int32ul, 0),
	"timeout" / Default(Int32ul, 0),
	"fifo" / Default(Int32ul, 0),
	"threshold" / Default(Int32ul, 0),
	"limit" / Default(Int32ul, 0),
)

def undump(text):
	return b"".join([int(v, 16).to_bytes(4, byteorder="little") for v in text.strip().split()])

class SIOEndpoint(ASCBaseEndpoint):
	BASE_MESSAGE = SIOMessage
	SHORT = "sioep"

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.tag = 0
		self.acked, self.nacked = set(), set()
		self.bufs = {}
		self.started = False

	@msg_handler(0x65, SIOAck)
	def Ack(self, msg):
		self.acked.add(msg.TAG)
		return True

	@msg_handler(0x66, SIONack)
	def Nack(self, msg):
		self.nacked.add(msg.TAG)
		return True

	@msg_handler(0x67, SIOStarted)
	def Started(self, msg):
		self.started = True
		return True

	def next_tag(self):
		self.tag = (self.tag + 1) % 0x10
		return self.tag

	def roundtrip(self, msg, timeout=0.1):
		msg.TAG = self.next_tag()
		self.send(msg)
		self.acked.discard(msg.TAG)
		self.nacked.discard(msg.TAG)
		deadline = time.time() + timeout
		while time.time() < deadline and msg.TAG not in self.acked:
			self.asc.work()
		if msg.TAG in self.nacked:
			raise Exception("ASC nacked a message")
		if msg.TAG not in self.acked:
			raise ASCTimeout("ASC reply timed out")

	def wait_for_started_msg(self, timeout=0.1):
		deadline = time.time() + timeout
		while time.time() < deadline and not self.started:
			self.asc.work()
		if not self.started:
			raise ASCTimeout("ASC reply timed out")

	def alloc_buf(self, param_id, size, data=b""):
		paddr, iova = self.asc.ioalloc(size)
		self.bufs[param_id] = (iova, size)
		self.write_shmem(param_id, 0, data)
		ep = param_id >> 8; param_id &= 0xff
		self.roundtrip(SIOSetup(EP=ep, PARAM=param_id, DATA=iova >> 12))
		self.roundtrip(SIOSetup(EP=ep, PARAM=param_id + 1, DATA=size))

	def start(self):
		self.send(SIOStart())
		self.wait_for_started_msg()
		self.alloc_buf(SIOShmem.UNK_0f, 0x1e000)
		self.alloc_buf(SIOShmem.MAP_RANGE, 0x50, # map-range=
			undump("""
				00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
				00000000 00000000 00000000 00000000 35000000 00000002 00004000 00000000
				00000000 00000000 00000000 00000000
		"""))
		self.alloc_buf(SIOShmem.ASIO_TUNABLES, 0x30, # asio-ascwrap-tunables=
			undump("""
				00000040 00000004 0000ff00 00000000 00000400 00000000 0000080c 00000004
				60000001 00000000 60000001 00000000
		"""))
		dmashim_data = b"".join([
				v.to_bytes(4, byteorder="little") \
				for data in self.asc.node.dmashim
				for v in data.unk
			])
		self.alloc_buf(SIOShmem.DMASHIM_DATA, 0xa0, dmashim_data)
		self.alloc_buf(SIOShmem.DEVICE_TYPE, 0x40, # device-type=
			undump("""
				00000005 00000000 00000009 00000000 00000000 00000000 00000002 0000000c
				00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
		"""))
		self.alloc_buf(SIOShmem.UNK_EP3_0d, 0x4000)
		self.alloc_buf(SIOShmem.MAIN, 0xaaa)
		self.alloc_buf(SIOShmem.UNK_0b, 0x1b80)

	def write_shmem(self, area, base, data):
		iova, shmem_size = self.bufs[area]
		assert base + len(data) <= shmem_size
		print(iova + base, chexdump(data))
		self.asc.iowrite(iova + base, data)

	def open_channel(self, channo, **config):
		self.write_shmem(
			SIOShmem.MAIN, 0,
			SIOChannelConfig.build(Container(**config))
		)
		self.roundtrip(SIOReadyChannel(EP=channo))
		return SIOChannel(self, channo)

class SIOClient(StandardASC):
	ENDPOINTS = {
		0x20: SIOEndpoint,
	}

	def __init__(self, u, adtpath, dart=None):
		node = u.adt[adtpath]
		self.node = node
		self.base = node.get_reg(0)[0]
		super().__init__(u, self.base, dart)

	def map_data(self):
		segments = struct.unpack("<8q", self.node.segment_ranges)
		self.dart.iomap_at(0, segments[6], segments[4], segments[7] & ~(-1 << 32))

p.pmgr_adt_clocks_enable("/arm-io/dart-sio")
p.pmgr_adt_clocks_enable("/arm-io/sio")
p.pmgr_adt_clocks_enable("/arm-io/dp-audio0")

dart = DART.from_adt(u, "/arm-io/dart-sio", iova_range=(0x30000, 0x10_000_000))

dart.initialize()
dart.regs.TCR[0].set(BYPASS_DAPF=0, BYPASS_DART=0, TRANSLATE_ENABLE=1)
dart.regs.TCR[15].set(BYPASS_DAPF=0, BYPASS_DART=1, TRANSLATE_ENABLE=0)

sio = SIOClient(u, "/arm-io/sio", dart)
sio.asc.CPU_CONTROL.val = 0x0
sio.verbose = 4
sio.map_data()
sio.boot()

try:
	sio.start_ep(0x20)
	dpaudio0 = sio.sioep.open_channel(0x64,
		datashape=0x2,
		fifo=0x800,
		threshold=0x800,
		limit=0x800,
	)
except:
	traceback.print_exc()
	p.reboot()

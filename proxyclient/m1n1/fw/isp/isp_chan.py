# SPDX-License-Identifier: MIT

from construct import *
import cv2
import struct
from termcolor import colored
import time

from .isp_msg import ISPChannelMessage
from .isp_vid import ISPFrame


class ISPChannel:
	"""
	Ring buffers used for CPU <-> ASC communication.

	TM: TERMINAL     | src = 0, type = 2, num = 768, size = 0xc000, iova = 0x1804700
	IO: IO           | src = 1, type = 0, num =   8, size = 0x0200, iova = 0x1810700
	DG: DEBUG        | src = 1, type = 0, num =   8, size = 0x0200, iova = 0x1810900
	BR: BUF_H2T      | src = 2, type = 0, num =  64, size = 0x1000, iova = 0x1810b00
	BT: BUF_T2H      | src = 3, type = 1, num =  64, size = 0x1000, iova = 0x1811b00
	SM: SHAREDMALLOC | src = 3, type = 1, num =   8, size = 0x0200, iova = 0x1812b00
	IT: IO_T2H       | src = 3, type = 1, num =   8, size = 0x0200, iova = 0x1812d00

	There's a sticky note on my machine that says, "Host is Me, Target is Firmware".

	TM: Logs from firmware. arg0 is pointer & arg1 is the message size of log line.
	IO: To dispatch CISP_CMD_* ioctls to the firmware.
	DG: Unused.
	BR: New RX buffer pushed.
	BT: New TX buffer pushed.
	SM: Firmware requests to allocate OR free a shared mem region.
	IT: Mcache stuff when RPC is enabled. Basically unused.
	"""

	def __init__(self, isp, name, _type, src, num, iova, abbrev=""):
		self.isp = isp
		self.name = name
		self.src = src
		self.type = _type
		self.num = num
		self.entry_size = 64
		self.size = self.num * self.entry_size
		self.iova = iova
		self.doorbell = 1 << self.src

		self.cursor = 0
		self.abbrev = abbrev if abbrev else self.name
		self._stfu = False

	@property
	def stfu(self): self._stfu = True

	def log(self, *args):
		if (not self._stfu):
			if (args): print("ISP: %s:" % (self.abbrev.upper()), *args)
			else: print()

	def get_iova(self, index):
	        assert((index < self.num))
	        return self.iova + (index * self.entry_size)

	def read_msg(self, index):
	        assert((index < self.num))
	        return ISPChannelMessage.parse(self.isp.ioread(self.get_iova(index), self.entry_size))

	def write_msg(self, msg, index):
	        assert((index < self.num))
	        self.isp.iowrite(self.get_iova(index), msg.encode())

	def read_all_msgs(self):
		ring = self.isp.ioread(self.iova, self.size)
		return [ISPChannelMessage.parse(ring[n*self.entry_size:(n+1)*self.entry_size]) for n in range(self.num)]

	def update_cursor(self):
		if (self.cursor >= (self.num - 1)):
			self.cursor = 0
		else:
			self.cursor += 1

	def dump(self):
		self.log(f'---------------- START OF {self.name} TABLE ----------------')
		for n, msg in enumerate(self.read_all_msgs()):
			if (msg.valid()):
				self.log(f'{n}: {msg}')
		self.log(f'---------------- END OF {self.name} TABLE ----------------')

	def _irq_wrap(f):
		def wrap(self, **kwargs):
			self.log()
			self.log(f'---------------- START OF {self.name} IRQ ----------------')
			x = f(self, **kwargs)
			self.log(f'---------------- END OF {self.name} IRQ ------------------')
			self.log()
			return x
		return wrap

	@_irq_wrap
	def handle_once(self, req):
		rsp = self._handle(req=req)
		if (rsp == None): return None
		self.write_msg(rsp, self.cursor)
		self.isp.regs.ISP_IRQ_ACK.val = self.isp.regs.ISP_IRQ_INTERRUPT.val
		self.isp.regs.ISP_IRQ_DOORBELL.val = self.doorbell
		time.sleep(0.05)  # TODO Why does it die without this? Why 0.05-0.10??
		self.update_cursor()
		return rsp

	def handler(self):
		while True:
			req = self.read_msg(self.cursor)
			if ((req.arg0 & 0xf) == 0x1): break  # ack flag
			rsp = self.handle_once(req=req)
			if (rsp == None): raise RuntimeError("IRQ stuck")

	@_irq_wrap
	def send_once(self, req):
		self.log(f'TX: REQ: {req}')
		self.write_msg(req, self.cursor)

		rsp = None
		self.isp.regs.ISP_IRQ_DOORBELL.val = self.doorbell
		while True:
			rsp = self.read_msg(self.cursor)
			if (rsp.arg0 == (req.arg0 | 0x1)): break  # ack flag
			self.isp.table.sharedmalloc.handler()
		if (rsp == None): return None

		self.log(f'RX: RSP: {rsp}')
		self.isp.regs.ISP_IRQ_ACK.val = self.isp.regs.ISP_IRQ_INTERRUPT.val
		self.update_cursor()
		return rsp

	def send(self, req):
		rsp = self.send_once(req=req)
		if (rsp == None): raise RuntimeError("ASC never acked. IRQ stuck.")
		return rsp


class ISPTerminalChannel(ISPChannel):
	def __init__(self, isp, x, **kwargs):
	        super().__init__(isp, x.name, x.type, x.src, x.num, x.iova, **kwargs)

	def dump(self):
		msgs = self.read_all_msgs()
		for n, msg in enumerate(msgs):
			if (msg.valid()):
				data = self.isp.ioread(msg.arg0 & ~3, msg.arg1) # iova, size
				s = data.decode().strip().replace('\n', '').replace('\r', '')
				if (s):
					print("(%d): ISPASC: " % (n) + s)


class ISPIOChannel(ISPChannel):
	def __init__(self, isp, x, **kwargs):
	        super().__init__(isp, x.name, x.type, x.src, x.num, x.iova, **kwargs)


class ISPDebugChannel(ISPChannel):
	def __init__(self, isp, x, **kwargs):
	        super().__init__(isp, x.name, x.type, x.src, x.num, x.iova, **kwargs)


class ISPBufH2TChannel(ISPChannel):
	def __init__(self, isp, x, **kwargs):
	        super().__init__(isp, x.name, x.type, x.src, x.num, x.iova, **kwargs)


class ISPBufT2HChannel(ISPChannel):
	def __init__(self, isp, x, **kwargs):
	        super().__init__(isp, x.name, x.type, x.src, x.num, x.iova, **kwargs)

	def _handle(self, req):
		assert((req.arg1 > 0x0))
		self.log("RX: REQ: [iova: 0x%x, size: 0x%x, flag: 0x%x]" % (req.arg0, req.arg1, req.arg2))

		if (req.arg2 == 0x10000000):
			self.push_frame(req)
		else:
			self.log(colored("Warning: frame dropped", "red"))

		# RX: REQ: [0x3a54000, 0x280, 0x10000000]  # iova, size, flag
		# TX: RSP: [0x3a54001, 0x000, 0x80000000]  # iova, zero, flag
		rsp = ISPChannelMessage.build(
			arg0 = req.arg0 | 0x1,  # iova
			arg1 = 0x0,  # zero out size
			arg2 = 0x80000000,  # done flag
		)
		self.log("TX: RSP: [iova: 0x%x, ack: 0x%x, flag: 0x%x]" % (rsp.arg0, rsp.arg1, rsp.arg2))
		return rsp

	def push_frame(self, req):
		frame = ISPFrame(self.isp, req)
		self.isp.frames.append(frame)
		self.log(colored("Pushing %s" % (str(frame)), "green"))
		cv2.imshow('frame', frame.process())
		cv2.waitKey(50)


class ISPSharedMallocChannel(ISPChannel):
	def __init__(self, isp, x, **kwargs):
	        super().__init__(isp, x.name, x.type, x.src, x.num, x.iova, **kwargs)

	def _handle(self, req):
		rsp = None

		# Two request types: malloc & free
		if (req.arg0 == 0):
			# On malloc request, arg0 (iova) is zeroed
			# alloc the requested size (arg1) & fill out the new iova
			# RX: REQ: [0x0, 0x18000, 0x4c4f47]  # zero, size, name
			# TX: RSP: [0x3a28001, 0x0, 0xc]  # iova, zero, index
			assert((req.arg1 > 0x0))  # needs size
			try:  # sometimes it sends garbage
				name = struct.pack(">q", req.arg2).decode()
			except UnicodeDecodeError as e:
				name = ("%04x" % (req.arg2 & 0xffff)).upper()
			self.log("SM: RX: Malloc REQ: [size: 0x%x, name: %s]" % (req.arg1, name))

			surf = self.isp.mmger.alloc_size(req.arg1, name=name)
			rsp = ISPChannelMessage.build(
			        arg0 = surf.iova | 0x1,  # fill with new iova
			        arg1 = 0x0, # zero out size as ack
			        arg2 = surf.index, # index for (my) reference
			)
			self.log("SM: TX: Malloc RSP: [iova: 0x%x, index: 0x%x]" % (rsp.arg0, rsp.arg2))

		else:   # On free request, arg0 is the iova to free (duh)
			# RX: REQ: [0x81664000, 0x0, 0x0]  # iova, zero, zero
			# TX: RSP: [0x81664001, 0x0, 0x0]  # iova, zero, zero
			assert((req.arg1 == 0x0) and (req.arg2 == 0x0))  # can't have size/index
			self.log("SM: RX: Free REQ: [iova: 0x%x]" % (req.arg0))

			surf = self.isp.mmger.index_iova(req.arg0)
			if not surf: raise ValueError("shit")
			self.isp.mmger.free_surf(surf)

			rsp = ISPChannelMessage.build(
			        arg0 = req.arg0 | 0x1,  # flag freed iova
			        arg1 = 0x0, # zero out size
			        arg2 = 0x0, # zero out index
			)
			self.log("SM: TX: Free RSP: [iova: 0x%x]" % (rsp.arg0))

		return rsp


class ISPIOT2HChannel(ISPChannel):
	def __init__(self, isp, x, **kwargs):
	        super().__init__(isp, x.name, x.type, x.src, x.num, x.iova, **kwargs)


class ISPChannelTable:
	def __init__(self, isp, description):
		self.isp = isp
		for desc in description:
			name = desc.name
			if (name == "TERMINAL"): self.terminal = ISPTerminalChannel(isp, desc, abbrev="TM")
			if (name == "IO"): self.io = ISPIOChannel(isp, desc, abbrev="IO")
			if (name == "DEBUG"): self.debug = ISPDebugChannel(isp, desc, abbrev="DG")
			if (name == "BUF_H2T"): self.bufh2t = ISPBufH2TChannel(isp, desc, abbrev="BR")
			if (name == "BUF_T2H"): self.buft2h = ISPBufT2HChannel(isp, desc, abbrev="BT")
			if (name == "SHAREDMALLOC"): self.sharedmalloc = ISPSharedMallocChannel(isp, desc, abbrev="SM")
			if (name == "IO_T2H"): self.iot2h = ISPIOT2HChannel(isp, desc, abbrev="IT")
		self.channels = [self.terminal, self.io, self.debug, self.bufh2t, self.buft2h, self.sharedmalloc, self.iot2h]
		assert(all(chan for chan in self.channels))

	def name2chan(self, name):
		if (name == "TERMINAL"): return self.terminal
		if (name == "IO"): return self.io
		if (name == "DEBUG"): return self.debug
		if (name == "BUF_H2T"): return self.bufh2t
		if (name == "BUF_T2H"): return self.buft2h
		if (name == "SHAREDMALLOC"): return self.sharedmalloc
		if (name == "IO_T2H"): return self.iot2h

	def dump(self):
		for chan in self.channels:
			if (chan.name != "TERMINAL"):
				chan.dump()

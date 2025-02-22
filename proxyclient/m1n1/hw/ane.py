# SPDX-License-Identifier: MIT
from ..utils import *
from .dart import DARTRegs
import time


class ANERegs(RegMap):
	PMGR1 = 0x738, Register32
	PMGR2 = 0x798, Register32
	PMGR3 = 0x7f8, Register32

	ASC_IO_RVBAR = 0x1050000, Register32
	ASC_EDPRCR   = 0x1010310, Register32

	# 24hz clocks, counter at +4
	CLK0 = 0x1160008, Register32
	CTR0 = 0x116000c, Register32
	CLK1 = 0x1168008, Register32
	CTR1 = 0x116800c, Register32
	CLK2 = 0x1170000, Register32
	CTR2 = 0x1170004, Register32
	CLK3 = 0x1178000, Register32
	CTR3 = 0x1178004, Register32

	VERS = 0x1840000, Register32

	# for acks w/ rtkit
	GPIO0 = 0x1840048, Register32
	GPIO1 = 0x184004c, Register32
	GPIO2 = 0x1840050, Register32
	GPIO3 = 0x1840054, Register32
	GPIO4 = 0x1840058, Register32
	GPIO5 = 0x184005c, Register32
	GPIO6 = 0x1840060, Register32
	GPIO7 = 0x1840064, Register32


class ANEDARTRegs(DARTRegs):
	UNK_CONFIG_68 = 0x68, Register32
	UNK_CONFIG_6c = 0x6c, Register32


class R_TQINFO(Register32):
	UNK = 31, 16
	NID = 15, 0

class TaskQueue(RegMap):
	STATUS     = irange(0x00, 8, 0x148), Register32
	PRTY       = irange(0x10, 8, 0x148), Register32
	FREE_SPACE = irange(0x14, 8, 0x148), Register32
	TQINFO     = irange(0x1c, 8, 0x148), R_TQINFO

	BAR1 = (irange(0x20, 8, 0x148), irange(0x0, 0x20, 4)), Register32
	REQ_NID1  = irange(0xa0, 8, 0x148), Register32
	REQ_SIZE2 = irange(0xa4, 8, 0x148), Register32
	REQ_ADDR2 = irange(0xa8, 8, 0x148), Register32

	BAR2 = (irange(0xac, 8, 0x148), irange(0x0, 0x20, 4)), Register32
	REQ_NID2  = irange(0x12c, 8, 0x148), Register32
	REQ_SIZE1 = irange(0x130, 8, 0x148), Register32
	REQ_ADDR1 = irange(0x134, 8, 0x148), Register32


class R_REQINFO(Register32):
	TDSIZE  = 31, 16
	TDCOUNT = 15,  0

class R_IRQINFO(Register32):
	CNT  = 31, 24
	NID  = 23, 16
	UNK1 = 15, 8
	UNK2 = 7,  0

class TMRegs(RegMap):
	REQ_ADDR = 0x0, Register32
	REQ_INFO = 0x4, R_REQINFO
	REQ_PUSH = 0x8, Register32
	TQ_EN    = 0xc, Register32

	IRQ_EVT1_CNT      = 0x14, Register32
	IRQ_EVT1_DAT_INFO = 0x18, R_IRQINFO
	IRQ_EVT1_DAT_UNK1 = 0x1c, Register32
	IRQ_EVT1_DAT_TIME = 0x20, Register32
	IRQ_EVT1_DAT_UNK2 = 0x24, Register32

	IRQ_EVT2_CNT      = 0x28, Register32
	IRQ_EVT2_DAT_INFO = 0x2c, R_IRQINFO
	IRQ_EVT2_DAT_UNK1 = 0x30, Register32
	IRQ_EVT2_DAT_TIME = 0x34, Register32
	IRQ_EVT2_DAT_UNK2 = 0x38, Register32

	COMMIT_INFO = 0x44, Register32
	TM_STATUS   = 0x54, Register32

	UNK_IRQ_EN1 = 0x68, Register32
	UNK_IRQ_ACK = 0x6c, Register32
	UNK_IRQ_EN2 = 0x70, Register32


class ANETaskManager:

	TQ_COUNT = 8
	TQ_WIDTH = 0x148
	tq_prty = (0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0x1e, 0x1f)

	def __init__(self, ane):
		self.u = ane.u
		self.p = ane.p
		self.TM_BASE_ADDR = ane.base_addr + 0x1c00000 + 0x24000
		self.TQ_BASE_ADDR = ane.base_addr + 0x1c00000 + 0x25000
		self.regs = TMRegs(self.u, self.TM_BASE_ADDR)
		self.tq = TaskQueue(self.u, self.TQ_BASE_ADDR)

	def reset(self):  # these reset with ANE_SET pds
		self.regs.TQ_EN.val = 0x3000

		# set priority param for each queue
		for qid, prty in enumerate(self.tq_prty):
			self.tq.PRTY[qid].val = self.tq_prty[qid]

		self.regs.UNK_IRQ_EN1.val = 0x4000000  # enable irq
		self.regs.UNK_IRQ_EN2.val = 0x6  # enable irq

	def enqueue_tq(self, req):
		qid = req.qid
		if not ((qid >= 1) and (qid < self.TQ_COUNT)):
			raise ValueError('1 <= qid <= 7')
		if not (self.tq.PRTY[qid].val == self.tq_prty[qid]):
			raise ValueError('invalid priority setup for tq %d' % qid)

		print('enqueueing task w/ fifo 0x%x to tq %d' % (req.fifo_iova, qid))
		self.tq.STATUS[qid].val = 0x1  # in use

		for bdx, iova in enumerate(req.bar):
			if (iova):
				print("bar %d: 0x%x" % (bdx, iova))
			self.tq.BAR1[qid, bdx].val = iova

		self.tq.REQ_SIZE1[qid].val = ((req.td_size << 0xe) + 0x1ff0000) & 0x1ff0000
		self.tq.REQ_ADDR1[qid].val = req.fifo_iova & 0xffffffff
		self.tq.REQ_NID1[qid].val = (req.nid & 0xff) << 8 | 1

	def execute_tq(self, req):
		qid = req.qid
		print('arbitered tq %d; pushing to execution queue...' % qid)

		# transfer to main queue (now in in TM range)
		self.regs.REQ_ADDR.val = self.tq.REQ_ADDR1[qid].val
		# doesn't go through if 0
		self.regs.REQ_INFO.val = self.tq.REQ_SIZE1[qid].val | req.td_count
		# let's do magic
		self.regs.REQ_PUSH.val = self.tq_prty[qid] | (qid & 7) << 8

		self.get_tm_status()
		self.get_committed_info()
		self.irq_handler()
		self.tq.STATUS[qid].val = 0x0  # done

	def get_tm_status(self, max_timeouts=100, interval=0.01):
		for n in range(max_timeouts):
			status = self.regs.TM_STATUS.val
			success = (status & 1) != 0
			print('tm status: 0x%x, success: %r' % (status, success))
			if (success):
				return success
			time.sleep(interval)
		print('timeout, tm is non-idle! status: 0x%x' % status)
		return success

	def get_committed_info(self):
		committed_nid = self.regs.COMMIT_INFO.val >> 0x10 & 0xff
		print('pushed td w/ nid 0x%x to execution' % committed_nid)

	def irq_handler(self):
		line = 0
		evtcnt = self.regs.IRQ_EVT1_CNT.val
		print('irq handler: LINE %d EVTCNT: %d' % (line, evtcnt))
		for evt_n in range(evtcnt):  # needs to be cleared
			info = self.regs.IRQ_EVT1_DAT_INFO.val
			unk1 = self.regs.IRQ_EVT1_DAT_UNK1.val
			tmstmp = self.regs.IRQ_EVT1_DAT_TIME.val
			unk2 = self.regs.IRQ_EVT1_DAT_UNK2.val
			print('irq handler: LINE %d EVT %d: executed info 0x%x @ 0x%x'
				  % (line, evt_n, info, tmstmp))

		self.regs.UNK_IRQ_ACK.val = self.regs.UNK_IRQ_ACK.val | 2

		line = 1
		evtcnt = self.regs.IRQ_EVT2_CNT.val
		print('irq handler: LINE %d EVTCNT: %d' % (line, evtcnt))
		for evt_n in range(evtcnt):  # needs to be cleared
			info = self.regs.IRQ_EVT2_DAT_INFO.val
			unk1 = self.regs.IRQ_EVT2_DAT_UNK1.val
			tmstmp = self.regs.IRQ_EVT2_DAT_TIME.val
			unk2 = self.regs.IRQ_EVT2_DAT_UNK2.val
			print('irq handler: LINE %d EVT %d: executed info 0x%x @ 0x%x'
				  % (line, evt_n, info, tmstmp))

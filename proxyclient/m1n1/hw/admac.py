# SPDX-License-Identifier: MIT
from ..utils import *

__all__ = ["ADMACRegs", "ADMAC"]


class R_RING(Register32):
    # overflow/underflow counter
    OF_UF = 31, 16

    # goes through 0, 1, 2, 3 as the pieces of a report/descriptor
    # are being read/written through REPORT_READ/DESC_WRITE
    READOUT_PROGRESS = 13, 12

    # when READ_SLOT==WRITE_SLOT one of the two is set
    EMPTY = 8
    FULL = 9

    ERR = 10

    # next slot to read
    READ_SLOT = 5, 4

    # next slot to be written to
    WRITE_SLOT = 1, 0

class R_CHAN_STATUS(Register32):
    # only raised if the descriptor had NOTIFY set
    DESC_DONE = 0

    DESC_RING_EMPTY = 4
    REPORT_RING_FULL = 5

    # cleared by writing ERR=1 either to TX_DESC_RING or TX_REPORT_RING
    RING_ERR = 6

    UNK0 = 1
    UNK3 = 8
    UNK4 = 9
    UNK5 = 10

class R_CHAN_CONTROL(Register32):
    RESET_RINGS = 0
    CLEAR_OF_UF_COUNTERS = 1
    UNK1 = 3

class ADMACRegs(RegMap):
    TX_EN     = 0x0, Register32 # one bit per channel
    TX_EN_CLR = 0x4, Register32

    RX_EN     = 0x8, Register32
    RX_EN_CLR = 0xc, Register32

    UNK_CTL = 0x10, Register32

    # each of the four registers represents an internal interrupt line,
    # bits represent DMA channels which at the moment raise that particular line
    #
    # the irq-destination-index prop in ADT maybe selects the line which
    # is actually wired out
    #
    TX_INTSTATE = irange(0x30, 4, 0x4), Register32

    # a 24 MHz always-running counter, top bit is always set
    COUNTER = 0x70, Register64

    # -- per-channel registers --

    TX_CTL = (irange(0x8000, 16, 0x400)), R_CHAN_CONTROL

    TX_UNK1 = (irange(0x8040, 16, 0x400)), Register32
    TX_UNK2 = (irange(0x8054, 16, 0x400)), Register32

    TX_RESIDUE = irange(0x8064, 16, 0x400), Register32

    TX_DESC_RING   = irange(0x8070, 16, 0x400), R_RING
    TX_REPORT_RING = irange(0x8074, 16, 0x400), R_RING

    TX_DESC_WRITE  = irange(0x10000, 16, 4), Register32
    TX_REPORT_READ = irange(0x10100, 16, 4), Register32

    # per-channel, per-internal-line
    TX_STATUS  = (irange(0x8010, 16, 0x400), irange(0x0, 4, 0x4)), R_CHAN_STATUS
    TX_INTMASK = (irange(0x8020, 16, 0x400), irange(0x0, 4, 0x4)), R_CHAN_STATUS

    # missing: RX variety of registers shifted by +0x200


class ADMACDescriptorFlags(Register32):
    # whether to raise DESC_DONE in TX_STATUS
    NOTIFY = 16

    # whether to repeat this descriptor ad infinitum
    #
    # once a descriptor with this flag is loaded, any descriptors loaded
    # afterwards are also repeated and nothing short of full power domain reset
    # seems to revoke that behaviour. this looks like a HW bug.
    REPEAT = 17

    # arbitrary ID propagated into reports
    DESC_ID = 7, 0

class ADMACDescriptor(Reloadable):
    def __init__(self, addr, length, **flags):
        self.addr = addr
        self.length = length
        self.flags = ADMACDescriptorFlags(**flags)

    def __repr__(self):
        return f"<descriptor: addr=0x{self.addr:x} len=0x{self.length:x} flags={self.flags}>"

    def ser(self):
        return [
            self.addr & (1<<32)-1,
            self.addr>>32 & (1<<32)-1,
            self.length & (1<<32)-1,
            int(self.flags)
        ]

    @classmethod
    def deser(self, seq):
        if not len(seq) == 4:
            raise ValueError
        return ADMACDescriptor(
            seq[0] | seq[1] << 32, # addr
            seq[2], # length (in bytes)
            **ADMACDescriptorFlags(seq[3]).fields
        )


class ADMACReportFlags(Register32):
    UNK1 = 24
    UNK2 = 25
    UNK3 = 27
    DESC_ID = 7, 0

class ADMACReport(Reloadable):
    def __init__(self, countval, unk1, flags):
        self.countval, self.unk1, self.flags = countval, unk1, ADMACReportFlags(flags)

    def __repr__(self):
        return f"<report: countval=0x{self.countval:x} unk1=0x{self.unk1:x} flags={self.flags}>"

    def ser(self):
        return [
            self.countval & (1<<32)-1,
            self.countval>>32 & (1<<32)-1,
            self.unk1 & (1<<32)-1,
            int(self.flags)
        ]

    @classmethod
    def deser(self, seq):
        if not len(seq) == 4:
            raise ValueError
        return ADMACReport(
            seq[0] | seq[1] << 32, # countval
            seq[2], # unk1
            seq[3] # flags
        )


class ADMACTXChannel(Reloadable):
    def __init__(self, parent, channo):
        self.p = parent
        self.iface = parent.p.iface
        self.dart = parent.dart
        self.regs = parent.regs
        self.ch = channo

        self._desc_id = 0
        self._submitted = {}
        self._last_report = None

    def reset(self):
        self.regs.TX_CTL[self.ch].set(RESET_RINGS=1, CLEAR_OF_UF_COUNTERS=1)
        self.regs.TX_CTL[self.ch].set(RESET_RINGS=0, CLEAR_OF_UF_COUNTERS=0)

    def enable(self):
        self.regs.TX_EN.val = 1 << self.ch

    def disable(self):
        self.regs.TX_EN_CLR.val = 1 << self.ch

    def can_submit(self):
        return not self.regs.TX_DESC_RING[self.ch].reg.FULL

    def submit_desc(self, desc):
        if self.regs.TX_DESC_RING[self.ch].reg.FULL:
            raise Exception(f"ch{self.ch} descriptor ring full")

        if self.p.debug:
            print(f"admac: submitting (ch{self.ch}): {desc}")

        for piece in desc.ser():
            self.regs.TX_DESC_WRITE[self.ch].val = piece

        self._submitted[desc.flags.DESC_ID] = desc

    def submit(self, data, **kwargs):
        assert self.dart is not None

        self.poll()

        buf, iova = self.p._get_buffer(len(data))
        self.iface.writemem(buf, data)
        self.submit_desc(ADMACDescriptor(
            iova, len(data), DESC_ID=self._desc_id, NOTIFY=1, **kwargs
        ))
        self._desc_id = (self._desc_id + 1) % 256

    def poll(self):
        if self.regs.TX_STATUS[self.ch, 1].reg.RING_ERR:
            if self.p.debug:
                print(f"TX_STATUS={self.regs.TX_STATUS[self.ch,1].reg} " + \
                      f"REPORT_RING={self.regs.TX_DESC_RING[self.ch]} " + \
                      f"DESC_RING={self.regs.TX_REPORT_RING[self.ch]}")
            self.regs.TX_DESC_RING[self.ch].set(ERR=1)
            self.regs.TX_REPORT_RING[self.ch].set(ERR=1)

        while not self.regs.TX_REPORT_RING[self.ch].reg.EMPTY:
            pieces = []
            for _ in range(4):
                pieces.append(self.regs.TX_REPORT_READ[self.ch].val)
            report = ADMACReport.deser(pieces)

            if self.p.debug:
                if self._last_report is not None and report.flags.DESC_ID in self._submitted:
                    countval_delta = report.countval - self._last_report.countval
                    est_rate = 24e6*self._submitted[report.flags.DESC_ID].length/countval_delta/4
                    est = f"(estimated rate: {est_rate:.2f} dwords/s)"
                else:
                    est = ""

                print(f"admac: picked up (ch{self.ch}): {report} {est}")

            self._last_report = report


class ADMAC(Reloadable):
    def __init__(self, u, devpath, dart=None, dart_stream=2, nchans=12,
                 reserved_size=4*1024*1024, debug=False):
        self.u = u
        self.p = u.proxy
        self.debug = debug

        self.base, _ = u.adt[devpath].get_reg(0)
        self.regs = ADMACRegs(u, self.base)
        self.dart = dart

        if dart is not None:
            self.resmem_base = u.heap.memalign(128*1024, reserved_size)
            self.resmem_size = reserved_size
            self.resmem_pos = self.resmem_base
            self.iova_base = self.dart.iomap(dart_stream, self.resmem_base, self.resmem_size)
            self.dart.invalidate_streams(1 << dart_stream)

        self.tx = [ADMACTXChannel(self, no) for no in range(nchans)]

    def _get_buffer(self, size):
        assert size < self.resmem_size

        if self.resmem_pos + size > self.resmem_base + self.resmem_size:
            self.resmem_pos = self.resmem_base

        bufptr = self.resmem_pos
        self.resmem_pos += size
        return bufptr, bufptr - self.resmem_base + self.iova_base

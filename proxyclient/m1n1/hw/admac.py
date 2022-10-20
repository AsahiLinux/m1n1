# SPDX-License-Identifier: MIT
import sys, time
from enum import IntEnum
from ..utils import *

__all__ = ["ADMACRegs", "ADMAC", "E_BUSWIDTH", "E_FRAME"]


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

class E_BUSWIDTH(IntEnum):
    W_8BIT  = 0
    W_16BIT = 1
    W_32BIT = 2

class E_FRAME(IntEnum):
    F_1_WORD  = 0
    F_2_WORDS = 1
    F_4_WORDS = 2

class R_BUSWIDTH(Register32):
    WORD  = 2, 0, E_BUSWIDTH
    FRAME = 6, 4, E_FRAME

class R_CARVEOUT(Register32):
    SIZE = 31, 16
    BASE = 15, 0

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
    RX_INTSTATE = irange(0x40, 4, 0x4), Register32

    # a 24 MHz always-running counter, top bit is always set
    COUNTER = 0x70, Register64

    TX_SRAM_SIZE = 0x94, Register32
    RX_SRAM_SIZE = 0x98, Register32

    # -- per-channel registers --

    CHAN_CTL = (irange(0x8000, 32, 0x200)), R_CHAN_CONTROL

    CHAN_BUSWIDTH      = (irange(0x8040, 32, 0x200)), R_BUSWIDTH
    CHAN_SRAM_CARVEOUT = (irange(0x8050, 32, 0x200)), R_CARVEOUT
    CHAN_BURSTSIZE     = (irange(0x8054, 32, 0x200)), Register32

    CHAN_RESIDUE = irange(0x8064, 32, 0x200), Register32

    CHAN_DESC_RING   = irange(0x8070, 32, 0x200), R_RING
    CHAN_REPORT_RING = irange(0x8074, 32, 0x200), R_RING

    TX_DESC_WRITE  = irange(0x10000, 16, 4), Register32
    TX_REPORT_READ = irange(0x10100, 16, 4), Register32

    RX_DESC_WRITE  = irange(0x14000, 16, 4), Register32
    RX_REPORT_READ = irange(0x14100, 16, 4), Register32

    # per-channel, per-internal-line
    CHAN_STATUS  = (irange(0x8010, 32, 0x200), irange(0x0, 4, 0x4)), R_CHAN_STATUS
    CHAN_INTMASK = (irange(0x8020, 32, 0x200), irange(0x0, 4, 0x4)), R_CHAN_STATUS


class ADMACDescriptorFlags(Register32):
    # whether to raise DESC_DONE in CHAN_STATUS
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
    UNK4 = 26 # memory access fault?
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


class ADMACChannel(Reloadable):
    def __init__(self, parent, channo):
        self.p = parent
        self.iface = parent.p.iface
        self.dart = parent.dart
        self.regs = parent.regs
        self.tx = (channo % 2) == 0
        self.rx = not self.tx
        self.ch = channo

        self._desc_id = 0
        self._submitted = {}
        self._last_report = None
        self._est_byte_rate = None

    def reset(self):
        self.regs.CHAN_CTL[self.ch].set(RESET_RINGS=1, CLEAR_OF_UF_COUNTERS=1)
        self.regs.CHAN_CTL[self.ch].set(RESET_RINGS=0, CLEAR_OF_UF_COUNTERS=0)

        self.burstsize = 0xc0_0060
        self.buswidth = E_BUSWIDTH.W_32BIT
        self.framesize = E_FRAME.F_1_WORD

    def enable(self):
        self.regs.CHAN_INTMASK[self.ch, 0].reg = \
                R_CHAN_STATUS(DESC_DONE=1, DESC_RING_EMPTY=1,
                                REPORT_RING_FULL=1, RING_ERR=1)

        if self.tx:
            self.regs.TX_EN.val = 1 << (self.ch//2)
        else:
            self.regs.RX_EN.val = 1 << (self.ch//2)

    def disable(self):
        if self.tx:
            self.regs.TX_EN_CLR.val = 1 << (self.ch//2)
        else:
            self.regs.RX_EN_CLR.val = 1 << (self.ch//2)

    @property
    def buswidth(self):
        self.regs.CHAN_BUSWIDTH[self.ch].reg.WORD

    @buswidth.setter
    def buswidth(self, wordsize):
        return self.regs.CHAN_BUSWIDTH[self.ch].set(WORD=wordsize)

    @property
    def framesize(self):
        self.regs.CHAN_BUSWIDTH[self.ch].reg.FRAME

    @framesize.setter
    def framesize(self, framesize):
        return self.regs.CHAN_BUSWIDTH[self.ch].set(FRAME=framesize)

    @property
    def burstsize(self):
        return self.regs.CHAN_BURSTSIZE[self.ch].val

    @burstsize.setter
    def burstsize(self, size):
        self.regs.CHAN_BURSTSIZE[self.ch].val = size

    @property
    def sram_carveout(self):
        reg = self.regs.CHAN_SRAM_CARVEOUT[self.ch].reg
        return (reg.BASE, reg.SIZE)

    @sram_carveout.setter
    def sram_carveout(self, carveout):
        base, size = carveout
        self.regs.CHAN_SRAM_CARVEOUT[self.ch].reg = \
                    R_CARVEOUT(BASE=base, SIZE=size)

    @property
    def DESC_WRITE(self):
        if self.tx:
            return self.regs.TX_DESC_WRITE[self.ch//2]
        else:
            return self.regs.RX_DESC_WRITE[self.ch//2]

    @property
    def REPORT_READ(self):
        if self.tx:
            return self.regs.TX_REPORT_READ[self.ch//2]
        else:
            return self.regs.RX_REPORT_READ[self.ch//2]

    def can_submit(self):
        return not self.regs.CHAN_DESC_RING[self.ch].reg.FULL

    def submit_desc(self, desc):
        if self.regs.CHAN_DESC_RING[self.ch].reg.FULL:
            raise Exception(f"ch{self.ch} descriptor ring full")

        if self.p.debug:
            print(f"admac: submitting (ch{self.ch}): {desc}", file=sys.stderr)

        for piece in desc.ser():
            self.DESC_WRITE.val = piece

        self._submitted[desc.flags.DESC_ID] = desc

    def submit(self, data=None, buflen=None, **kwargs):
        if self.tx:
            assert data is not None
            buflen = len(data)
        else:
            assert buflen is not None

        iova = self.p.get_buffer(buflen)
        if self.tx:
            self.p.iowrite(iova, data)
        self.submit_desc(ADMACDescriptor(
            iova, buflen, DESC_ID=self._desc_id, NOTIFY=1, **kwargs
        ))
        self._desc_id = (self._desc_id + 1) % 256

    def read_reports(self):
        data = bytearray()

        while not self.regs.CHAN_REPORT_RING[self.ch].reg.EMPTY:
            pieces = []
            for _ in range(4):
                pieces.append(self.REPORT_READ.val)
            report = ADMACReport.deser(pieces)

            if report.flags.DESC_ID in self._submitted:
                desc = self._submitted[report.flags.DESC_ID]
            else:
                print(f"admac: stray report (ch{self.ch}): {report}", file=sys.stderr)
                desc = None

            if self.rx and desc and self.p.dart:
                data.extend(self.p.ioread(desc.addr, desc.length))

            if self.p.debug:
                if self._last_report and desc:
                    countval_delta = report.countval - self._last_report.countval
                    est_rate = 24e6*desc.length/countval_delta/4
                    est = f"(estimated rate: {est_rate:.2f} dwords/s)"
                else:
                    est = ""

                print(f"admac: picked up (ch{self.ch}): {report} {est}", file=sys.stderr)

            self._last_report = report

        return data if self.rx else None

    @property
    def status(self):
        return self.regs.CHAN_STATUS[self.ch, 0].reg

    def poll(self, wait=True):
        while not (self.status.DESC_DONE or self.status.RING_ERR):
            time.sleep(0.001)

            if not wait:
                break

        self.regs.CHAN_STATUS[self.ch,0].reg = R_CHAN_STATUS(DESC_DONE=1)

        if self.status.RING_ERR:
            if self.p.debug:
                print(f"STATUS={self.regs.CHAN_STATUS[self.ch,1].reg} " + \
                      f"REPORT_RING={self.regs.CHAN_DESC_RING[self.ch]} " + \
                      f"DESC_RING={self.regs.CHAN_REPORT_RING[self.ch]}",
                      file=sys.stderr)
            self.regs.CHAN_DESC_RING[self.ch].set(ERR=1)
            self.regs.CHAN_REPORT_RING[self.ch].set(ERR=1)

        return self.read_reports()


class ADMAC(Reloadable):
    def __init__(self, u, devpath, dart=None, dart_stream=2,
                 reserved_size=4*1024*1024, debug=False):
        self.u = u
        self.p = u.proxy
        self.debug = debug

        if type(devpath) is str:
            adt_node = u.adt[devpath]
            # ADT's #dma-channels counts pairs of RX/TX channel, so multiply by two
            self.nchans = adt_node._properties["#dma-channels"] * 2
            self.base, _ = adt_node.get_reg(0)
        else:
            self.base = devpath
            self.nchans = 26

        self.regs = ADMACRegs(u, self.base)
        self.dart, self.dart_stream = dart, dart_stream

        if dart is not None:
            resmem_phys = u.heap.memalign(128*1024, reserved_size)
            self.resmem_iova = self.dart.iomap(dart_stream, resmem_phys, reserved_size)
            self.resmem_size = reserved_size
            self.resmem_pos = 0
            self.dart.invalidate_streams(1 << dart_stream)

        self.chans = [ADMACChannel(self, no) for no in range(self.nchans)]

    def ioread(self, base, size):
        assert self.dart is not None
        return self.dart.ioread(self.dart_stream, base, size)

    def iowrite(self, base, data):
        assert self.dart is not None
        self.dart.iowrite(self.dart_stream, base, data)

    def fill_canary(self):
        ranges = self.dart.iotranslate(self.dart_stream, 
                                self.resmem_iova, self.resmem_size)
        assert len(ranges) == 1
        start, size = ranges[0]
        self.p.memset8(start, 0xba, size)

    def get_buffer(self, size):
        assert size < self.resmem_size

        if self.resmem_pos + size > self.resmem_size:
            self.resmem_pos = 0

        bufptr = self.resmem_iova + self.resmem_pos
        self.resmem_pos += size
        return bufptr

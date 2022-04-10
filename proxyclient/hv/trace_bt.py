from m1n1.trace import Tracer
from m1n1.trace.dart import DARTTracer
from m1n1.utils import *
import struct


class BTBAR0Regs(RegMap):
    IMG_DOORBELL = 0x140, Register32
    RTI_CONTROL = 0x144, Register32
    RTI_SLEEP_CONTROL = 0x150, Register32
    DOORBELL_6 = 0x154, Register32
    DOORBELL_05 = 0x174, Register32

    BTI_MSI_LO = 0x580, Register32
    BTI_MSI_HI = 0x584, Register32
    REG_24 = 0x588, Register32
    HOST_WINDOW_LO = 0x590, Register32
    HOST_WINDOW_HI = 0x594, Register32
    HOST_WINDOW_SZ = 0x598, Register32
    RTI_IMG_LO = 0x5a0, Register32
    RTI_IMG_HI = 0x5a4, Register32
    RTI_IMG_SZ = 0x5a8, Register32
    REG_21 = 0x610, Register32

    AXI2AHB_ERR_LOG_STATUS = 0x1908, Register32

    CHIPCOMMON_CHIP_STATUS = 0x302c, Register32

    APBBRIDGECB0_ERR_LOG_STATUS = 0x5908, Register32
    APBBRIDGECB0_ERR_ADDR_LO = 0x590c, Register32
    APBBRIDGECB0_ERR_ADDR_HI = 0x5910, Register32
    APBBRIDGECB0_ERR_MASTER_ID = 0x5914, Register32

    DOORBELL_UNK = irange(0x6620, 7, 4), Register32


class BTBAR1Regs(RegMap):
    REG_0 = 0x20044c, Register32
    RTI_GET_CAPABILITY = 0x200450, Register32
    BOOTSTAGE = 0x200454, Register32
    RTI_GET_STATUS = 0x20045c, Register32

    REG_7 = 0x200464, Register32

    IMG_ADDR_LO = 0x200478, Register32
    IMG_ADDR_HI = 0x20047c, Register32
    IMG_ADDR_SZ = 0x200480, Register32
    BTI_EXITCODE_RTI_IMG_RESPONSE = 0x200488, Register32
    RTI_CONTEXT_LO = 0x20048c, Register32
    RTI_CONTEXT_HI = 0x200490, Register32
    RTI_WINDOW_LO = 0x200494, Register32
    RTI_WINDOW_HI = 0x200498, Register32
    RTI_WINDOW_SZ = 0x20049c, Register32

    RTI_MSI_LO = 0x2004f8, Register32
    RTI_MSI_HI = 0x2004fc, Register32
    RTI_MSI_DATA = 0x200500, Register32

    REG_14 = 0x20054c, Register32


class MemRangeTracer(Tracer):
    REGMAPS = []
    REGRANGES = []
    NAMES = []
    PREFIXES = []

    def __init__(self, hv, verbose=False):
        super().__init__(hv, verbose=verbose, ident=type(self).__name__)

    @classmethod
    def _reloadcls(cls):
        cls.REGMAPS = [i._reloadcls() if i else None for i in cls.REGMAPS]
        return super()._reloadcls()

    def start(self):
        for i in range(len(self.REGRANGES)):
            if i >= len(self.REGMAPS) or (regmap := self.REGMAPS[i]) is None:
                continue
            prefix = name = None
            if i < len(self.NAMES):
                name = self.NAMES[i]
            if i < len(self.PREFIXES):
                prefix = self.PREFIXES[i]

            start, size = self.REGRANGES[i]
            self.trace_regmap(start, size, regmap, name=name, prefix=prefix)


class BTTracer(MemRangeTracer):
    DEFAULT_MODE = TraceMode.SYNC
    REGMAPS = [BTBAR0Regs, BTBAR1Regs]
    # FIXME this is kinda a hack
    REGRANGES = [(0x5c2410000, 0x8000), (0x5c2000000, 0x400000)]
    NAMES = ['BAR0', 'BAR1']

    def __init__(self, hv, dart_tracer):
        super().__init__(hv, verbose=3)
        self.dart_tracer = dart_tracer
        self._dart_tracer_started = False
        self._dumped_host_window = False
        self._dump_idx = 0
        self._host_window_lo = 0
        self._host_window_hi = 0
        self._host_window_sz = 0
        self._rti_window_lo = 0
        self._rti_window_hi = 0
        self._rti_window_sz = 0
        self._rti_context_lo = 0
        self._rti_context_hi = 0

    def w_DOORBELL_6(self, val):
        # this is the first access macos does
        if not self._dart_tracer_started:
            self.dart_tracer.start()
            self._dart_tracer_started = True
            print("starting DART tracer")

    def w_HOST_WINDOW_LO(self, val):
        self._host_window_lo = val

    def w_HOST_WINDOW_HI(self, val):
        self._host_window_hi = val

    def w_HOST_WINDOW_SZ(self, val):
        self._host_window_sz = val

    def w_IMG_DOORBELL(self, val):
        print("Image doorbell was rung")
        host_window_iova = int(self._host_window_hi) << 32 | int(self._host_window_lo)
        host_window_sz = int(self._host_window_sz)
        print(f"Host window @ {host_window_iova:016X} sz {host_window_sz:08X}")

        self.dart_tracer.dart.dump_all()

        # FIXME how do we get stream IDs without hardcoding?
        try:
            data = self.dart_tracer.dart.ioread(2, host_window_iova, host_window_sz)
            with open(f'bt_dump_{self._dump_idx}.bin', 'wb') as f:
                f.write(data)
            chexdump(data[:0x400])
            self._dump_idx += 1
        except Exception as e:
            print(e)


    def w_RTI_WINDOW_LO(self, val):
        self._rti_window_lo = val

    def w_RTI_WINDOW_HI(self, val):
        self._rti_window_hi = val

    def w_RTI_WINDOW_SZ(self, val):
        self._rti_window_sz = val

    def w_RTI_CONTEXT_LO(self, val):
        self._rti_context_lo = val

    def w_RTI_CONTEXT_HI(self, val):
        self._rti_context_hi = val

    def w_RTI_CONTROL(self, val):
        print("RTI control was set")
        host_window_iova = int(self._host_window_hi) << 32 | int(self._host_window_lo)
        host_window_sz = int(self._host_window_sz)
        print(f"Host window @ {host_window_iova:016X} sz {host_window_sz:08X}")
        rti_window_iova = int(self._rti_window_hi) << 32 | int(self._rti_window_lo)
        rti_window_sz = int(self._rti_window_sz)
        print(f"RTI window @ {rti_window_iova:016X} sz {rti_window_sz:08X}")
        rti_context_iova = int(self._rti_context_hi) << 32 | int(self._rti_context_lo)
        print(f"RTI context @ {rti_context_iova:016X}")

        self.dart_tracer.dart.dump_all()

        # FIXME how do we get stream IDs without hardcoding?
        try:
            data = self.dart_tracer.dart.ioread(2, host_window_iova, host_window_sz)
            with open(f'bt_dump_{self._dump_idx}.bin', 'wb') as f:
                f.write(data)
            chexdump(data[:0x400])
            self._dump_idx += 1
        except Exception as e:
            print(e)

        try:
            data = self.dart_tracer.dart.ioread(2, rti_context_iova, 0x100)
            with open(f'bt_dump_{self._dump_idx}.bin', 'wb') as f:
                f.write(data)
            chexdump(data)
            self._dump_idx += 1
        except Exception as e:
            print(e)


BTTracer = BTTracer._reloadcls()

dart_tracer = DARTTracer(hv, "/arm-io/dart-apcie0", verbose=1)
dart_tracer.DEFAULT_MODE = TraceMode.SYNC
# do not start, clock gates aren't enabled yet
print(dart_tracer)

bt_tracer = BTTracer(hv, dart_tracer)
bt_tracer.start()
print(bt_tracer)

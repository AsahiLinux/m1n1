from . import ADTDevTracer
from .dart import DARTTracer
from ..hv import TraceMode
from ..hw.dart import DART, DARTRegs
from ..hw.isp import * 

class ISPTracer(ADTDevTracer):
    
    DEFAULT_MODE = TraceMode.SYNC

    REGMAPS = [ISPRegs, PSReg, SPMIReg, SPMIReg, SPMIReg]
    NAMES = ["isp", "ps", "spmi0", "spmi1", "spmi2"]

    ALLOWLISTED_CHANNELS = ["TERMINAL", "IO", "BUF_H2T", "BUF_T2H", "SHAREDMALLOC", "IO_T2H"]

    def __init__(self, hv, dev_path, dart_dev_path, verbose):
        super().__init__(hv, dev_path, verbose)

        hv.p.pmgr_adt_clocks_enable("/arm-io/dart-isp")

        self.dart_tracer = DARTTracer(hv, "/arm-io/dart-isp")
        self.dart_tracer.start()
        self.dart = self.dart_tracer.dart

        self.ignored_ranges = [
            # -----------------------------------------------------------------
            # ## System clock counter (24 mhz)
            (0x23b734004, 4), 
            (0x23b734008, 4), 
            # ## Noisy memory addresses that are always zero
            (0x23b734868, 4), 
            (0x23b73486c, 4), 
            (0x23b734b38, 4), 
            (0x23b734b3c, 4), 
            (0x23b734b58, 4), 
            (0x23b734b5c, 4), 
            (0x23b734bd8, 4),
            (0x23b734bdc, 4),
            (0x23b734c18, 4),
            (0x23b734c1c, 4),
            (0x23b778128, 4), 
            (0x23b77812c, 4),
            (0x23b77c128, 4),
            (0x23b77c12c, 4),
            # # Noisy memory addresses that change value
            (0x23b700248, 4), 
            (0x23b700258, 4), 
            (0x23b7003f8, 4), 
            (0x23b700470, 4),
            # # ECPU/PCPU state report
            (0x23b738004, 4), # ecpu state report
            (0x23b738008, 4), # pcpu state report
            # -----------------------------------------------------------------
        ]

    def r_ISP_GPR0(self, val):
        # I have no idea how many channels may be available in other platforms
        # but, at least for M1 I know they are seven (7), so using 64 as safe value here
        if val.value == 0x8042006:
            self.log(f"ISP_GPR0 = ACK")
        elif val.value < 64: 
            self.log(f"ISP_IPC_CHANNELS = {val!s}")
            self.number_of_channels = val.value
        elif val.value > 0:
            self.log(f"ISP_IPC_CHANNEL_TABLE_IOVA = {val!s}")
            self.channel_table = ISPChannelTable(self, self.number_of_channels, val.value)
            self.log(f"{str(self.channel_table)}")

    def r_ISP_IRQ_INTERRUPT(self, val):
        pending_irq = int(val.value)
        self.log(f"======== BEGIN IRQ ========")
        #self.channel_table.dump()
        self.channel_table.get_last_read_command(pending_irq)
        self.log(f"========  END IRQ  ========")

    def w_ISP_DOORBELL_RING0(self, val):
        doorbell_value = int(val.value)
        self.log(f"======== BEGIN DOORBELL ========")
        #self.channel_table.dump()
        self.channel_table.get_last_write_command(doorbell_value)
        self.log(f"========  END DOORBELL  ========")

    def w_ISP_GPR0(self, val):
        self.log(f"ISP_GPR0 = ({val!s})")
        if val.value == 0x1812f80:
            if self.dart:
                self.init_struct = self.dart.ioread(0, val.value & 0xFFFFFFFF, 0x190)

    def w_ISP_IRQ_INTERRUPT(self, val):
        self.log(f"IRQ_INTERRUPT = ({val!s}).")
        if val.value == 0xf:
            self.log(f"ISP Interrupts enabled")

    def ioread(self, dva, size):
        if self.dart:
            return self.dart.ioread(0, dva & 0xFFFFFFFF, size)
        else:
            return self.hv.iface.readmem(dva, size)

    def iowrite(self, dva, data):
        if self.dart:
            return self.dart.iowrite(0, dva & 0xFFFFFFFF, data)
        else:
            return self.hv.iface.writemem(dva, data)

    def start(self):
        super().start()

        self.msgmap = {}
        for name in dir(self):
            arg = getattr(self, name)
            if not callable(arg) or not getattr(arg, "is_message", False):
                continue
            self.msgmap[arg.direction, arg.endpoint, arg.message] = getattr(self, name), name, arg.regtype
        
        # Disable trace of memory regions 
        for addr, size in self.ignored_ranges:
            self.trace(addr, size, TraceMode.OFF)
from m1n1.trace import Tracer
from m1n1.trace.dart import DARTTracer
from m1n1.trace.asc import ASCTracer, EP, EPState, msg, msg_log, DIR, EPContainer
from m1n1.utils import *
from m1n1.constructutils import *
from m1n1.proxyutils import RegMonitor
from m1n1.fw.pmp import *

iomon = RegMonitor(hv.u, ascii=True)

def readmem_phys(addr, size, readfn=None):
    return hv.iface.readmem(addr, size)

dart_pmp_tracer = DARTTracer(hv, "/arm-io/dart-pmp", verbose=4)
dart_pmp_tracer.start()

def readmem_iova(addr, size, readfn=None):
    try:
        return dart_pmp_tracer.dart.ioread(0, addr, size)
    except Exception as e:
        print(e)
        return None

iomon.readmem = readmem_iova

class PMPEp(EP):
    BASE_MESSAGE = PMPMessage

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)
        self.state.shmem_iova = None
        self.state.verbose = 1
        self.status_devpwr = {}

    def add_mon(self):
        if self.state.shmem_iova:
            iomon.add(self.state.shmem_iova, 0x10000,
                      name=f"{self.name}.shmem@{self.state.shmem_iova:08x}",
                      offset=0)

    @msg(0x0, DIR.RX, PMP_Startup)
    def Startup(self, msg):
        self.log("PMP starting up")

        self.add_mon()

    @msg(0x10, DIR.TX, PMP_Configure)
    def Configure(self, msg):
        self.state.shmem_iova = msg.DVA
        self.add_mon()

    @msg(0x20e, DIR.TX, PMP_DevPwr)
    def DevPwr(self, msg):
        dev = ""
        if msg.DEV == 0x54:
            dev = "DISP0_FE"
        elif msg.DEV == 0x68:
            dev = "ANE_SYS"
        elif msg.DEV == 0x5d:
            dev = "MSR"
        elif msg.DEV == 0x64:
            dev = "ISP_SYS"
        elif msg.DEV == 0x66:
            dev = "AVD_SYS"
        elif msg.DEV == 0x5c:
            dev = "JPG"
        elif msg.DEV == 0x3e:
            dev = "ATC1_PCIE"
        elif msg.DEV == 0x15c:
            dev = "ATC1_PCIE-V"
        elif msg.DEV == 0x55:
            dev = "DISPEXT_FE"
        elif msg.DEV == 0x63:
            dev = "GFX"

        state = "on" if msg.STATE == 1 else "off"
        self.log(f"Powering {state}: {dev}")

        self.status_devpwr[dev] = state


    Configure_Ack = msg_log(0x20, DIR.RX, PMP_Configure_Ack)
    Init1 = msg_log(0x200, DIR.TX, PMP_Init1)
    Init1_Ack = msg_log(0x201, DIR.RX, PMP_Init1_Ack)
    Init2 = msg_log(0x202, DIR.TX, PMP_Init2)
    Init2_Ack = msg_log(0x203, DIR.RX, PMP_Init2_Ack)
    DevPwr_Sync = msg_log(0x208, DIR.TX, PMP_DevPwr_Sync)
    DevPwr_Ack = msg_log(0x209, DIR.RX, PMP_DevPwr_Ack)

    ChangeState1 = msg_log(0x20c, DIR.TX, PMP_ChangeState1)
    ChangeState1_Ack = msg_log(0x20d, DIR.RX, PMP_ChangeState1_Ack)
    ChangeState2 = msg_log(0x20a, DIR.TX, PMP_ChangeState2)
    ChangeState2_Ack = msg_log(0x20b, DIR.RX, PMP_ChangeState2_Ack)

class PMPTracer(ASCTracer):
    ENDPOINTS = {0x20: PMPEp}

    def handle_msg(self, direction, r0, r1):
        super().handle_msg(direction, r0, r1)
        iomon.poll()

    def start(self, dart=None):
        super().start(dart=dart_pmp_tracer.dart)
        # noisy doorbell
        self.trace(0x23bc34000, 4, TraceMode.OFF)


pmp_tracer = PMPTracer(hv, "/arm-io/pmp", verbose=1)
pmp_tracer.start(dart_pmp_tracer.dart)

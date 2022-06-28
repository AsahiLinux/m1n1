# SPDX-License-Identifier: MIT
"""
Things to note:
    The command buffer is encrypted after the poweron sequence, and I
    can't find the key in the SEP using sven's old SEP tracer.
"""
import struct
from construct import *

from m1n1.hv import TraceMode
from m1n1.proxyutils import RegMonitor
from m1n1.utils import *

from m1n1.trace import ADTDevTracer
from m1n1.trace.asc import ASCTracer, ASCRegs, EP, EPState, msg, msg_log, DIR
from m1n1.trace.dart import DARTTracer
from m1n1.trace.gpio import GPIOTracer
from m1n1.trace.spi import SPITracer

DARTTracer = DARTTracer._reloadcls()
ASCTracer = ASCTracer._reloadcls()
GPIOTracer = GPIOTracer._reloadcls()
SPITracer = SPITracer._reloadcls()

mesa_node = None
for node in hv.adt.walk_tree():
    try:
        if node.compatible[0] == "spi-1,spimc":
            for c in node:
                try:
                    if c.compatible[0] == "biosensor,mesa":
                        mesa_node = c
                        break
                except AttributeError:
                    continue
    except AttributeError:
        continue
    if mesa_node is not None:
        break

# trace interrupts
aic_phandle = getattr(hv.adt["/arm-io/aic"], "AAPL,phandle")
spi_node = mesa_node._parent

if getattr(spi_node, "interrupt-parent") == aic_phandle:
    for irq in getattr(spi_node, "interrupts"):
        hv.trace_irq("/arm-io/" + spi_node.name, irq, 1, hv.IRQTRACE_IRQ)

if getattr(mesa_node, "interrupt-parent") == aic_phandle:
    for irq in getattr(mesa_node, "interrupts"):
        hv.trace_irq("/arm-io/" + mesa_node.name, irq, 1, hv.IRQTRACE_IRQ)

mesa_pins = {
    0xc4: "mesa_pwr",

}


gpio_tracer = GPIOTracer(hv, "/arm-io/gpio0", mesa_pins, verbose=1)
gpio_tracer.start()

dart_sio_tracer = DARTTracer(hv, "/arm-io/dart-sio", verbose=1)
dart_sio_tracer.start()

iomon = RegMonitor(hv.u, ascii=True)

def readmem_iova(addr, size, readfn=None):
    try:
        return dart_sio_tracer.dart.ioread(0, addr, size)
    except Exception as e:
        print(e)
        return None

iomon.readmem = readmem_iova



class SIOMessage(Register64):
    EP    = 7, 0 # SPI2 DMA channels 0x18, 0x19
    TAG   = 13, 8 # counts up, message ID?
    TYPE  = 23, 16 # SIO message type
    PARAM = 31, 24
    DATA  = 63, 32

class SIOStart(SIOMessage):
    TYPE = 23, 16, Constant(2)

class SIOSetup(SIOMessage):
    TYPE = 23, 16, Constant(3)

class SIOConfig(SIOMessage): #???
    TYPE = 23, 16, Constant(5)

class SIOAck(SIOMessage):
    TYPE = 23, 16, Constant(0x65)

class SIOSetupIO(SIOMessage):
    TYPE = 23, 16, Constant(6)

class SIOCompleteIO(SIOMessage):
    TYPE = 23, 16, Constant(0x68)

class SIOEp(EP):
    BASE_MESSAGE = SIOMessage
    SHORT = "sioep"

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)
        self.state.iova = None
        self.state.iova_cfg = None
        self.state.iova_unk = None
        self.state.dumpfile = None

    @msg(2, DIR.TX, SIOStart)
    def Start(self, msg):
        self.log("Start SIO")

    @msg(3, DIR.TX, SIOSetup)
    def m_Setup(self, msg):
        if msg.EP == 0 and msg.PARAM == 0x1:
            self.state.iova = msg.DATA << 12

        elif msg.EP == 0 and msg.PARAM == 0x2:
            # size for PARAM == 0x1?
            iomon.add(self.state.iova, msg.DATA * 8,
                      name=f"SIO IOVA region at 0x{self.state.iova:08x}",
                      offset=self.state.iova)

        #elif msg.EP == 0 and msg.PARAM == 0xb:
            ## second iova block, maybe config
            #self.state.iova_cfg = msg.DATA << 12

        #elif msg.EP == 0 and msg.PARAM == 0xc:
            ## size for PARAM == 0xb?
            #iomon.add(self.state.iova_cfg, msg.DATA * 8,
                      #name=f"SIO IOVA CFG region at 0x{self.state.iova_cfg:08x}",
                      #offset=self.state.iova_cfg)

        if msg.EP == 0 and msg.PARAM == 0xd:
            # possible fingerprint sensor IOVA region
            self.state.iova_unk = msg.DATA << 12

        elif msg.EP == 0 and msg.PARAM == 0xe:
            iomon.add(self.state.iova_unk, msg.DATA * 8,
                      name=f"SIO IOVA UNK region at {self.state.iova_unk:08x}",
                      offset=self.state.iova_unk)

    @msg(5, DIR.TX, SIOConfig)
    def m_Config(self, msg):
        return

    @msg(0x65, DIR.RX, SIOAck)
    def m_Ack(self, msg):
        return

    @msg(6, DIR.TX, SIOSetupIO)
    def m_SetupIO(self, msg):
        if msg.EP == 0x18 or 0x19:
            iomon.poll()
        return

    @msg(0x68, DIR.RX, SIOCompleteIO)
    def m_CompleteIO(self, msg):
        if msg.EP == 0x18:
            if self.state.iova is None:
                return

            buf = struct.unpack("<I", self.tracer.ioread(self.state.iova + 0xa8, 4))[0]
            size = struct.unpack("<I", self.tracer.ioread(self.state.iova + 0xb0, 4))[0]
            self.log(f"SetupIO 0x18: buf {buf:#x}, size {size:#x}")
            # XXX: Do not try to log messages going to 0x2
            if buf == 0x2:
                self.log("Mesa command interrupted!")
                return
            self.log_mesa("EP 0x18", self.tracer.ioread(buf, size))
            return
        if msg.EP == 0x19:
            if self.state.iova is None:
                return

            buf = struct.unpack("<I", self.tracer.ioread(self.state.iova + 0x48, 4))[0]
            size = struct.unpack("<I", self.tracer.ioread(self.state.iova + 0x50, 4))[0]
            self.log(f"CompleteIO 0x19: buf {buf:#x}, size {size:#x}")
            # XXX: Do not try to log messages going to 0x2
            if buf == 0x2:
                self.log("Mesa command interrupted!")
                return
            if size >= 0x7200:
                with open("large_message.bin", "wb") as fd:
                    fd.write(self.tracer.ioread(buf, size))
                print("Fingerprint record message dumped.")
                return
            self.log_mesa("EP 0x19", self.tracer.ioread(buf, size))
            return

    def log_mesa(self, label, data):
        self.log(f"{label}: {len(data):d} byte message: ")
        chexdump(data)
        print("\n")


class SIOTracer(ASCTracer):
    ENDPOINTS = {
        0x20: SIOEp
    }


sio_tracer = SIOTracer(hv, "/arm-io/sio", verbose=1)
sio_tracer.start(dart=dart_sio_tracer.dart)

spi_tracer = SPITracer(hv, "/arm-io/spi2", verbose=2)
spi_tracer.start()

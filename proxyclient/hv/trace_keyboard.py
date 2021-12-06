# SPDX-License-Identifier: MIT

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

# SPI HID transport tracer for 2021 macbook models

kbd_node = None
for node in hv.adt.walk_tree():
    try:
        if node.compatible[0] == "spi-1,spimc":
            for c in node:
                try:
                    if c.compatible[0] == "hid-transport,spi":
                        kbd_node = c
                        break
                except AttributeError:
                    continue
    except AttributeError:
        continue
    if kbd_node is not None:
        break

# trace interrupts
aic_phandle = getattr(hv.adt["/arm-io/aic"], "AAPL,phandle")
spi_node = kbd_node._parent

if getattr(spi_node, "interrupt-parent") == aic_phandle:
    for irq in getattr(spi_node, "interrupts"):
        hv.trace_irq(node.name, irq, 1, hv.IRQTRACE_IRQ)

spi_pins = {
    0x37: "spi3_cs",
    0xc2: "ipd_en",
}
spi_pins_nub = {
    0x6: "ipd_irq",
}

SPI_HID_PKT = Struct(
    "flags" / Int8ub,
    "dev"   / Int8ub,
    "offset"    / Int16ul,
    "remain"    / Int16ul,
    "length"    / Int16ul,
    "data"      / Bytes(246),
    "crc16"     / Int16ul
)

#gpio_tracer = GPIOTracer(hv, "/arm-io/gpio0", spi_pins, verbose=0)
#gpio_tracer.start()

#gpio_tracer_nub = GPIOTracer(hv, "/arm-io/nub-gpio0", spi_pins_nub, verbose=0)
#gpio_tracer_nub.start()

dart_sio_tracer = DARTTracer(hv, "/arm-io/dart-sio", verbose=1)
dart_sio_tracer.start()

iomon = RegMonitor(hv.u, ascii=True)

def readmem_iova(addr, size):
    try:
        return dart_sio_tracer.dart.ioread(0, addr, size)
    except Exception as e:
        print(e)
        return None

iomon.readmem = readmem_iova

class SIOMessage(Register64):
    EP    = 7, 0 # matches device's ADT dma-channels, j314c spi3 0x1a and 0x1b
    TAG   = 13, 8 # counts for ipd spi transfers from 0x02 to 0x20
    TYPE  = 23, 16 # OP
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
        self.state.dumpfile = None

    @msg(2, DIR.TX, SIOStart)
    def Start(self, msg):
        self.log("Start SIO")

    @msg(3, DIR.TX, SIOSetup)
    def m_Setup(self, msg):
        iomon.poll()
        if msg.EP == 0 and msg.PARAM == 0x1:
            self.state.iova = msg.DATA << 12
        elif msg.EP == 0 and msg.PARAM == 0x2:
            # size for PARAM == 0x1?
            if self.state.iova is not None and self.tracer.verbose > 1:
                iomon.add(self.state.iova, msg.DATA * 8, name=f"sio.shmem@{self.state.iova:08x}",
                          offset=self.state.iova)
        elif msg.EP == 0 and msg.PARAM == 0xb:
            # second iova block, maybe config
            self.state.iova_cfg = msg.DATA << 12
        elif msg.EP == 0 and msg.PARAM == 0xc:
            # size for PARAM == 0xb?
            if self.state.iova is not None and self.tracer.verbose > 1:
                iomon.add(self.state.iova_cfg, msg.DATA * 8,
                          name=f"sio.shmem@{self.state.iova_cfg:08x}", offset=self.state.iova_cfg)

    @msg(0x65, DIR.RX, SIOAck)
    def m_Ack(self, msg):
        iomon.poll()

    @msg(6, DIR.TX, SIOSetupIO)
    def m_SetupIO(self, msg):
        iomon.poll()
        if self.state.iova is None:
            return
        if msg.EP == 0x1a:
            buf = struct.unpack("<I", self.tracer.ioread(self.state.iova + 0xa8, 4))[0]
            size = struct.unpack("<I", self.tracer.ioread(self.state.iova + 0xb0, 4))[0]
            self.log_spihid_pkt("SPI3 TX", self.tracer.ioread(buf, size))

    @msg(0x68, DIR.RX, SIOCompleteIO)
    def m_CompleteIO(self, msg):
        iomon.poll()
        if self.state.iova is None:
            return
        if msg.EP == 0x1b:
            buf = struct.unpack("<I", self.tracer.ioread(self.state.iova + 0x48, 4))[0]
            size = struct.unpack("<I", self.tracer.ioread(self.state.iova + 0x50, 4))[0]
            self.log_spihid_pkt("SPI3 RX", self.tracer.ioread(buf, size))

    def log_spihid_pkt(self, label, data):
        if len(data) != 256:
            self.log(f"{label}: unexpected data length: {len(data):d}")
            chexdump(data)
            return

        crc16 = crc16USB(0, data[:254])
        pkt = SPI_HID_PKT.parse(data)
        #self.log(f"pkt.crc16:{pkt.crc16:#04x} crc16:{crc16:#04x}")
        if pkt.length == 0:
            return

        if pkt.flags == 0x80 and pkt.dev == 0x11 and pkt.length == 849 and pkt.offset == 256 and pkt.remain == 834 and crc16 == 0x1489:
            return
        if pkt.crc16 != crc16:
            self.log(f"{label}: CRC mismatch: pkt.crc16:{pkt.crc16:#04x} crc16:{crc16:#04x}")
            chexdump(data)
            return
        self.log(f"{label}: flags:{pkt.flags:#2x} dev:{pkt.dev:#2x} length:{pkt.length:4d} offset:{pkt.offset:3d} remain:{pkt.remain:3d}")
        chexdump(pkt.data[:min(246, pkt.length)])

        if self.state.dumpfile:
            dump = f"{label}: flags:{pkt.flags:#2x} dev:{pkt.dev:#2x} length:{pkt.length:4d}  {pkt.data[:min(246, pkt.length)].hex()}\n"
            self.state.dumpfile.write(dump)
            self.state.dumpfile.flush()


class SIOTracer(ASCTracer):
    ENDPOINTS = {
        0x20: SIOEp
    }


sio_tracer = SIOTracer(hv, "/arm-io/sio", verbose=False)
sio_tracer.start(dart_sio_tracer.dart)

sio_tracer.ep.sioep.state.dumpfile = open("spi_hid.log", "a")

spi_tracer = SPITracer(hv, "/arm-io/" + spi_node.name, verbose=1)
spi_tracer.start()

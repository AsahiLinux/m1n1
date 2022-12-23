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
SPITracer = SPITracer._reloadcls()

# SPI HID transport tracer for 2021 macbook models

kbd_node = None
for node in hv.adt.walk_tree():
    try:
        if node.compatible[0] == "spi-1,spimc":
            for c in node:
                try:
                    if c.compatible[0] == "hid-transport,k1":
                        kbd_node = c
                        break
                except AttributeError:
                    continue
    except AttributeError:
        continue
    if kbd_node is not None:
        break


class Z2Tracer(SPITracer):
    def start(self):
        super().start()
        self.txbuffer = []
        self.rxbuffer = []
        self.want_bytes = 0
        self.state = Z2Tracer.preboot
    def w_TXDATA(self, data):
        self.txbuffer.append(data.value)
        self.check_msg_finished()
    def r_RXDATA(self, data):
        self.rxbuffer.append(data.value)
        self.check_msg_finished()
    def check_msg_finished(self):
        if min(len(self.txbuffer), len(self.rxbuffer)) < self.want_bytes:
            return
        self.state(self)
    def bad_state(self):
        pass
    def error(self):
        self.log(f"RXBUF {' '.join(hex(x) for x in self.rxbuffer)}")
        self.log(f"TXBUF {' '.join(hex(x) for x in self.txbuffer)}")
        self.log(f"state: {self.state}")
        self.log("Tracer desynchronized, shutting down")
        self.state = Z2Tracer.bad_state
    def consume_bytes(self, n):
        self.txbuffer = self.txbuffer[n:]
        self.rxbuffer = self.rxbuffer[n:]
    def preboot(self):
        if self.txbuffer[0] == 0:
            self.want_bytes = 4
            self.state = Z2Tracer.init_zeros
        elif self.txbuffer[0] == 0x1e:
            self.want_bytes = 16
            self.state = Z2Tracer.processing_init_data
        else:
            self.error()
    def init_zeros(self):
        self.log("sent 4 zeroes")
        self.consume_bytes(4)
        self.state = Z2Tracer.preboot
    def processing_init_data(self):
        self.log("Sent init data")
        self.want_bytes = 2
        self.consume_bytes(16)
        self.state = Z2Tracer.main_hbpp
    def main_hbpp(self):
        if self.txbuffer[0] == 0x1a and self.txbuffer[1] == 0xa1:
            self.log("Sent int ack")
            self.consume_bytes(2)
        elif self.txbuffer[0] == 0x18 and self.txbuffer[1] == 0xe1:
            self.log("Sent nop")
            self.consume_bytes(2)
        elif self.txbuffer[0] == 0x1f and self.txbuffer[1] == 0x01:
            self.log("Sent request cal")
            self.consume_bytes(2)
        elif self.txbuffer[0] == 0x30 and self.txbuffer[1] == 0x01:
            self.state = Z2Tracer.send_blob_cmd
            self.want_bytes = 10
        elif self.txbuffer[0] == 0x1e and self.txbuffer[1] == 0x33:
            self.state = Z2Tracer.send_rmw_cmd
            self.want_bytes = 16
        elif self.txbuffer[0] == 0xee and self.txbuffer[1] == 0x00:
            self.state = Z2Tracer.main_z2
            self.want_bytes = 16
        else:
            self.error()
    def send_blob_cmd(self):
        length = (self.txbuffer[2] << 8 | self.txbuffer[3]) * 4
        self.consume_bytes(10)
        self.want_bytes = length + 4
        self.log(f"Sending blob of length {length}")
        self.state = Z2Tracer.send_blob_tail
    def send_blob_tail(self):
        self.log("Finished sendind blob")
        self.consume_bytes(self.want_bytes)
        self.want_bytes = 2
        self.state = Z2Tracer.main_hbpp
    def send_rmw_cmd(self):
        self.log('Sent RMW command')
        self.want_bytes = 2
        self.consume_bytes(16)
        self.state = Z2Tracer.main_hbpp
    def main_z2(self):
        if self.txbuffer[0] == 0xee:
            self.log("sent wake cmd")
            self.consume_bytes(16)
        elif self.txbuffer[0] == 0xe2:
            self.log("sent get device info cmd")
            self.consume_bytes(16)
            self.state = Z2Tracer.read_device_info_reply
        elif self.txbuffer[0] == 0xeb:
            length = (self.rxbuffer[1] | (self.rxbuffer[2] << 8)) + 5
            length = (length + 3) & (-4)
            self.consume_bytes(16)
            self.want_bytes = length
            self.state = Z2Tracer.read_interrupt_data
        elif self.txbuffer[0] == 0xe3:
            self.log(f"got report info for {self.txbuffer[1]}, len is {self.rxbuffer[3]}")
            self.consume_bytes(16)
        elif self.txbuffer[0] == 0xe7:
            self.want_bytes = self.txbuffer[3] + 5
            self.consume_bytes(16)
            self.state = Z2Tracer.reading_report_long
        elif self.txbuffer[0] == 0xe6:
            self.consume_bytes(16)
            self.state = Z2Tracer.read_report_reply
        else:
            self.error()
    def reading_report_long(self):
        self.log(f"got report {' '.join(hex(x) for x in self.rxbuffer)}")
        self.consume_bytes(self.want_bytes)
        self.want_bytes = 16
        self.state = Z2Tracer.main_z2
    def read_interrupt_data(self):
        data = self.rxbuffer[5:]
        tstamp2 = data[4] | (data[5] << 8) | (data[6] << 16)
        tx = [f"TS1 {hex(data[1])} TS2 {tstamp2} UNK1: {mxformat(data[7:16])} UNK2: {mxformat(data[17:24])}"]
        if len(data) >= 16:
            ntouch = data[16]
            for i in range(ntouch):
                ptr = 24 + 30 * i
                finger = data[ptr]
                state = data[ptr + 1]
                x = data[ptr + 4] | (data[ptr + 5] << 8) 
                y = data[ptr + 6] | (data[ptr + 7] << 8)
                wj = data[ptr + 12] | (data[ptr + 13] << 8)
                wn = data[ptr + 14] | (data[ptr + 15] << 8)
                dg = data[ptr + 16] | (data[ptr + 17] << 8)
                prs = data[ptr + 18] | (data[ptr + 19] << 8)
                tx.append(f"F: {hex(finger)} S: {hex(state)} X: {x} Y: {y} MAJ: {wj} MIN: {wn} ANG: {dg} PRS: {prs} UNK1: {mxformat(data[ptr + 2:ptr+4])} UNK2: {mxformat(data[ptr + 8:ptr+12])} UNK3: {mxformat(data[ptr + 20:ptr+30])}")
            self.log(';'.join(tx))
        else:
            self.log(f"??? {mxformat(data)}")
        self.consume_bytes(self.want_bytes)
        self.want_bytes = 16
        self.state = Z2Tracer.main_z2
    def read_device_info_reply(self):
        self.log(f"got device info {' '.join(hex(x) for x in self.rxbuffer[:16])}")
        self.consume_bytes(16)
        self.state = Z2Tracer.main_z2
    def read_report_reply(self):
        self.log(f"got report {' '.join(hex(x) for x in self.rxbuffer[:16])}")
        self.consume_bytes(16)
        self.state = Z2Tracer.main_z2

def mxformat(ls):
    return ''.join(xformat(x) for x in ls)
def xformat(x):
    x = hex(x)[2:]
    if len(x) == 1:
        x = '0' + x
    return x



# trace interrupts
aic_phandle = getattr(hv.adt["/arm-io/aic"], "AAPL,phandle")
spi_node = kbd_node._parent

#if getattr(spi_node, "interrupt-parent") == aic_phandle:
#    for irq in getattr(spi_node, "interrupts"):
#        hv.trace_irq(node.name, irq, 1, hv.IRQTRACE_IRQ)
#for irq in hv.adt['/arm-io/gpio'].interrupts:
#    hv.trace_irq('/arm-io/gpio', irq, 1, hv.IRQTRACE_IRQ)

spi_tracer = Z2Tracer(hv, "/arm-io/" + spi_node.name)
spi_tracer.start()

spi_pins_nub = {
    0x0: "clock32khz",
}

#gpio_tracer_nub = GPIOTracer(hv, "/arm-io/nub-gpio", spi_pins_nub, verbose=0)
#gpio_tracer_nub.start()

spi_pins = {
    0x6d: "enable_cs",
    0x8b: "reset"
}

#gpio_tracer = GPIOTracer(hv, "/arm-io/gpio", spi_pins, verbose=0)
#gpio_tracer.start()

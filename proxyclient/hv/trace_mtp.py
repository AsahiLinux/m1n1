# SPDX-License-Identifier: MIT
import struct

from construct import *
from m1n1.utils import *
from m1n1.proxyutils import *
from m1n1.constructutils import *
from m1n1.trace.asc import ASCTracer, EP, EPState, msg, msg_log, DIR
from m1n1.trace.dockchannel import DockChannelTracer
from m1n1.trace.dart import DARTTracer
from m1n1.fw.mtp import *

class MTPTracer(ASCTracer):
    def handle_msg(self, direction, r0, r1):
        super().handle_msg(direction, r0, r1)

mtp_tracer = MTPTracer(hv, "/arm-io/mtp", verbose=1)
mtp_tracer.start()

dart_tracer = DARTTracer(hv, "/arm-io/dart-mtp", verbose=1)
dart_tracer.start()

trace_device("/arm-io/dart-mtp", True)

DockChannelTracer = DockChannelTracer._reloadcls()

mon = RegMonitor(hv.u, ascii=True, bufsize=0x400000)

class StreamState:
    def __init__(self):
        self.buf = bytes()

class MTPStream:
    def __init__(self, tracer, name, state):
        self.tracer = tracer
        self.name = name
        self.state = state

    def put(self, d):
        buf = self.state.buf + d

        while buf:
            if len(buf) < 8:
                self.state.buf = buf
                return

            hlen, mtype, size, ctr, devid, pad = struct.unpack("<BBHBBH", buf[:8])
            assert pad == 0
            if hlen != 8:
                self.tracer.log(f"Bad hlen 0x{hlen:2x}, skipping a byte...")
                self.state.buf = buf[1:]
                return


            need = 8 + size + 4
            if len(buf) < need:
                self.state.buf = buf
                return

            payload = buf[8:8 + size]
            self.packet(mtype, devid, ctr, payload)
            buf = buf[need:]

        self.state.buf = buf

    def packet(self, mtype, devid, ctr, pkt):
        self.tracer.packet(mtype, devid, ctr, pkt, dir=self.name)

    def log(self, msg):
        self.tracer.log(f"{self.name} " + msg)

class MTPChannelTracer(DockChannelTracer):
    def init_state(self):
        self.state.rx = StreamState()
        self.state.tx = StreamState()
        self.state.rx_mem = StreamState()
        self.state.buf = None
        self.state.buf_size = None
        self.state.rptr = 0

    def start(self, dart=None):
        super().start()
        self.dart = dart
        self.rx_stream = MTPStream(self, "<", self.state.rx)
        self.tx_stream = MTPStream(self, ">", self.state.tx)
        self.rx_mem_stream = MTPStream(self, "<", self.state.rx_mem)
        self.init_mon()

    def tx(self, d):
        self.tx_stream.put(d)

    def rx(self, d):
        self.rx_stream.put(d)

    def init_mon(self):
        pass
        #if self.state.buf is not None:
            #addr, size = self.dart.iotranslate(1, self.state.buf, self.state.buf_size)[0]
            #size = align_up(size, 4)
            #mon.add(addr, size)

    def poll_ring(self):
        wptr = struct.unpack("<I", self.dart.ioread(1, self.state.buf, 4))[0]
        rptr = self.state.rptr
        if wptr < rptr:
            size = self.state.buf_size - 8 - rptr
            d = self.dart.ioread(1, self.state.buf + 8 + rptr, size)
            self.rx_mem_stream.put(d)
            self.state.rptr = rptr = 0

        size = wptr - rptr
        d = self.dart.ioread(1, self.state.buf + 8 + rptr, size)
        self.rx_mem_stream.put(d)
        self.state.rptr = rptr + size

    def packet(self, mcode, devid, ctr, data, dir):
        #mon.poll()
        chexdump(data, print_fn=self.log)

        if data == b"":
            self.poll_ring()
            msg = "<null>"
        elif dir == ">":
            msg = TXMessage.parse(data)
        elif dir == "<":
            msg = RXMessage.parse(data)
            if devid == 0:
                if (msg.hdr.flags & 0xc0) == 0x00:
                    msg.msg = NotificationMsg.parse(msg.msg)
                elif (msg.hdr.flags & 0xc0) == 0x80:
                    msg.msg = DeviceControlAck.parse(msg.msg)
        else:
            assert False

        try:
            mtype = msg.msg.name
        except:
            mtype = None

        if mtype == "InitAFEMsg":
            afe = self.dart.ioread(1, msg.msg.buf_addr, msg.msg.buf_size)
            chexdump(afe, print_fn=self.log)
            open("afe.bin", "wb").write(afe)
        elif mtype == "InitBufMsg":
            self.state.buf = msg.msg.buf_addr
            self.state.buf_size = msg.msg.buf_size
            self.init_mon()

        self.log(f"{dir} Type {mcode:02x} Dev {devid} #{ctr} {msg!s}")

hid_tracer = MTPChannelTracer(hv, "/arm-io/dockchannel-mtp", verbose=3)
hid_tracer.start(dart_tracer.dart)

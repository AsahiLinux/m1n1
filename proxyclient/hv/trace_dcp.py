# SPDX-License-Identifier: MIT

trace_device("/arm-io/dcp", True, ranges=[1])

from m1n1.proxyutils import RegMonitor
from m1n1.utils import Register64, chexdump
from m1n1.trace.dart import DARTTracer
from m1n1.trace.asc import ASCTracer, EP, msg, msg_log, DIR

DARTTracer = DARTTracer._reloadcls()
ASCTracer = ASCTracer._reloadcls()

# Sequence of commands sent to endpoint 0x37 to present a frame The new
# framebuffer becomes visible after sending PRESENT, confirmed by timing.
PRE_PRESENT  = 0x0000003c00000202
PRESENT      = 0x000008b400000202
POST_PRESENT = 0x0000000000000342

# Sent repeatedly when reconfiguring the display (clicking anything in the
# Displays section of System Preferences -- scaling, rotation, colour profile,
# all included). The actual command is in shared memory. Acked by the DCP with
# an OK. This command is _not_ sufficient for hardware resolution changes, only
# for software (perceived) changes.
RECONFIGURE  = 0x0000106c00000202

# Response to pre_present, present, reconfigure
DCP_OK =    0x0000000000000242

# Response to post_presnt
PRESENT_3_RESP = 0x0000062800000302

KNOWN_MSGS = {
    PRE_PRESENT: "Pre present",
    PRESENT: "Present",
    POST_PRESENT: "Post present",
    RECONFIGURE: "Reconfigure",
    DCP_OK: "DCP OK",
    PRESENT_3_RESP: "Frame presented",
}

iomon = RegMonitor(hv.u, ascii=True)

class IOEpMessage(Register64):
    TYPE = 63, 48

class IOEp_Generic(IOEpMessage):
    ARG3 = 47, 32
    ARG2 = 31, 16
    ARG1 = 15, 0

class IOEp_SetBuf_Ack(IOEpMessage):
    UNK1 = 47, 32
    IOVA = 31, 0

class IOEp_Cmd(IOEpMessage):
    SIZE = 31, 0

class IOEp(EP):
    BASE_MESSAGE = IOEp_Generic

    def add_mon(self):
        if self.state.shmem_iova:
            iomon.add(self.state.shmem_iova, 32768,
                      name=f"{self.name}.shmem@{self.state.shmem_iova:08x}", offset=0)

    Init =          msg_log(0x80, DIR.TX)
    Init_Ack =      msg_log(0xa0, DIR.RX)

    GetBuf =        msg_log(0x89, DIR.RX)

    @msg(0xa1, DIR.TX, IOEp_SetBuf_Ack)
    def GetBuf_Ack(self, msg):
        self.state.shmem_iova = msg.IOVA
        self.add_mon()

    Ack =           msg_log(0x85, DIR.RX)

    @msg(0xa2, DIR.TX, IOEp_SetBuf_Ack)
    def Cmd(self, msg):
        pass
        #mon.poll()

class DCPMessage(Register64):
    TYPE        = 7, 0

class DCPEp_SetShmem(DCPMessage):
    IOVA        = 47, 16

class DCPEp_Cmd(DCPMessage):
    LEN         = 63, 32
    UNK         = 31, 8

class DCPEp(EP):
    BASE_MESSAGE = DCPEp_Cmd

    def add_mon(self):
        iomon.add(self.state.shmem_iova, 16384*32,
                  name=f"{self.name}.shmem@{self.state.shmem_iova:08x}", offset=0)

    @msg(0x40, DIR.TX, DCPEp_SetShmem)
    def SetShmem(self, msg):
        self.log(f"Shared memory IOVA: {msg.IOVA:#x}")
        self.state.shmem_iova = msg.IOVA
        self.add_mon()

    @msg(None, DIR.TX, DCPEp_Cmd)
    def Cmd(self, msg):
        self.log(f"Cmd: {msg} ({KNOWN_MSGS.get(msg.value, 'unk')})")
        return True

    @msg(None, DIR.RX, DCPEp_Cmd)
    def Reply(self, msg):
        self.log(f"Reply: {msg} ({KNOWN_MSGS.get(msg.value, 'unk')})")
        return True

class DCPTracer(ASCTracer):
    ENDPOINTS = {
        0x20: IOEp,
        0x21: IOEp,
        0x22: IOEp,
        0x23: IOEp,
        0x24: IOEp,
        0x25: IOEp,
        0x26: IOEp,
        0x27: IOEp,
        0x28: IOEp,
        0x29: IOEp,
        0x2a: IOEp,
        0x2b: IOEp,
        0x2c: IOEp,
        0x2d: IOEp,
        0x37: DCPEp,
    }

    def handle_msg(self, direction, r0, r1):
        super().handle_msg(direction, r0, r1)
        iomon.poll()

dart_dcp_tracer = DARTTracer(hv, "/arm-io/dart-dcp")
dart_dcp_tracer.start()

def readmem_iova(addr, size):
    try:
        return dart_dcp_tracer.dart.ioread(0, addr, size)
    except Exception as e:
        print(e)
        return None

iomon.readmem = readmem_iova

dcp_tracer = DCPTracer(hv, "/arm-io/dcp", verbose=1)
dcp_tracer.start(dart_dcp_tracer.dart)

for i in dcp_tracer.epmap.values():
    try:
        i.add_mon()
    except:
        pass

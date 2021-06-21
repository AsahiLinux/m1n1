# SPDX-License-Identifier: MIT

trace_device("/arm-io/dcp", True, ranges=[1])

from m1n1.proxyutils import RegMonitor
from m1n1.utils import Register64, chexdump
from m1n1.trace.dart import DARTTracer
from m1n1.trace.asc import ASCTracer, R_MESSAGE, msg, msg_log, DIR

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

class MSG_DCP_CMD(R_MESSAGE):
    ARG        = 47, 16
    UNK        = 15, 8
    ID         = 7, 0

KNOWN_MSGS = {
    PRE_PRESENT: "Pre present",
    PRESENT: "Present",
    POST_PRESENT: "Post present",
    RECONFIGURE: "Reconfigure",
    DCP_OK: "DCP OK",
    PRESENT_3_RESP: "Frame presented",
}

mon = RegMonitor(hv.u)

class DCPTracer(ASCTracer):
    @msg(0x37, 0x0, DIR.TX, MSG_DCP_CMD)
    def DCP_CMD(self, r0, r1):
        self.log(f"DCP_CMD: {r0} ({KNOWN_MSGS.get(r0.value, 'unk')})")
        if r0.ID == 0x40:
            self.log(f"Shared memory IOVA: {r0.ARG:#x}")
            self.state.shmem_iova = r0.ARG
            self.state.shmem_phys = self.dart.iotranslate(0, self.state.shmem_iova, 16384)[0][0]
            mon.add(self.state.shmem_phys, 16384)
        #chexdump(self.dart.ioread(0, self.state.shmem_iova, 0x1000).rstrip(b"\x00"))
        mon.poll()
        #self.hv.run_shell()

    @msg(0x37, 0x0, DIR.RX, MSG_DCP_CMD)
    def DCP_REPLY(self, r0, r1):
        self.log(f"DCP_REPLY: {r0} ({KNOWN_MSGS.get(r0.value, 'unk')})")
        #self.hv.run_shell()
        #chexdump(self.dart.ioread(0, self.state.shmem_iova, 0x1000).rstrip(b"\x00"))
        mon.poll()
        return False

dart_dcp_tracer = DARTTracer(hv, "/arm-io/dart-dcp")
dart_dcp_tracer.start()

dcp_tracer = DCPTracer(hv, "/arm-io/dcp", verbose=1)
dcp_tracer.start(dart_dcp_tracer.dart)

try:
    dcp_tracer.state.shmem_phys = dcp_tracer.dart.iotranslate(0, dcp_tracer.state.shmem_iova, 16384)[0][0]
    mon.add(dcp_tracer.state.shmem_phys, 16384)
except:
    pass

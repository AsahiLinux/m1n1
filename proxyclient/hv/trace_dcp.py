# SPDX-License-Identifier: MIT

trace_device("/arm-io/dcp", True, ranges=[1])

from m1n1.trace.asc import ASCTracer, msg, msg_log, DIR

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

class DCPTracer(ASCTracer):
    @msg(0x37, 0x0, None)
    def main(self, r0, r1):
        v = r0.value

        if v == PRE_PRESENT:
            self.log(f"Pre present")
            return True
        elif v == PRESENT:
            self.log(f"Present")
            return True
        elif v == POST_PRESENT:
            self.log(f"Post present")
            return True
        elif v == RECONFIGURE:
            self.log(f"Reconfiguring")
            return True
        elif v == DCP_OK:
            # Just noise, don't bother printing
            return True
        elif v == PRESENT_3_RESP:
            self.log(f"Frame presented")
            return True
        else:
            return False

dcp_tracer = DCPTracer(hv, "/arm-io/dcp", verbose=1)
dcp_tracer.start()

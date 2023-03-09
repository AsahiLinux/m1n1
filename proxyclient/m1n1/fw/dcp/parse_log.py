# SPDX-License-Identifier: MIT

from m1n1.utils import *
from m1n1.constructutils import Ver
from m1n1.fw.dcp.ipc import *

class DCPAVPropHandler:
    def __init__(self):
        self.dcpav_prop = {}

    def setDCPAVPropStart(self, length):
        # print(f"setDCPAVPropStart({length:#x})")
        self.dcpav_prop_len = length - 1 # off by one?
        self.dcpav_prop_off = 0
        self.dcpav_prop_data = []
        return True

    def setDCPAVPropChunk(self, data, offset, length):
        # print(f"setDCPAVPropChunk(..., {offset:#x}, {length:#x})")
        assert offset == self.dcpav_prop_off
        self.dcpav_prop_data.append(data)
        self.dcpav_prop_off += len(data)
        return True

    def setDCPAVPropEnd(self, key):
        # print(f"setDCPAVPropEnd({key!r})")
        blob = b"".join(self.dcpav_prop_data)
        assert self.dcpav_prop_len == len(blob)
        self.dcpav_prop[key] = OSSerialize().parse(blob)
        self.dcpav_prop_data = self.dcpav_prop_len = self.dcpav_prop_off = None
        pprint.pprint(self.dcpav_prop[key])
        return True


def parse_log(fd):
    op_stack = {}
    for line in fd:
        optype, args = line.split(" ", 1)
        if optype == "CALL":
            d, msg, chan, off, msg, in_size, out_size, in_data = args.split(" ")
            op = Call(d, chan, int(off, 0), msg, int(in_size, 0), int(out_size, 0),
                      bytes.fromhex(in_data))
            op_stack.setdefault(chan, []).append(op)
        elif optype == "ACK":
            d, msg, chan, off, out_data = args.split(" ")
            op = op_stack[chan].pop()
            assert int(off, 0) == op.off
            op.ack(bytes.fromhex(out_data))
        elif optype == "VERSION":
            for arg in args.strip().split(" "):
                version = arg.split(":")
                if len(version) == 2:
                    Ver.set_version_key(version[0], version[1])
            continue
        else:
            raise Exception(f"Unknown log cmd {optype}")

        yield op

def dump_log(fd):
    nesting = {
        "": 0,
        "OOB": 0,
    }

    handler = DCPAVPropHandler()

    for op in parse_log(fd):
        ctx = ""
        if Ver.check("V < V13_5"):
            dcpavprop_cbs = ["D122", "D123", "D124"]
        else:
             dcpavprop_cbs = ["D126", "D127", "D128"]
        if not op.complete and op.msg in dcpavprop_cbs:
            method = op.get_method()
            if op.msg == dcpavprop_cbs[0]:
                method.callback(handler.setDCPAVPropStart, op.in_data)
            if op.msg == dcpavprop_cbs[1]:
                method.callback(handler.setDCPAVPropChunk, op.in_data)
            if op.msg == dcpavprop_cbs[2]:
                method.callback(handler.setDCPAVPropEnd, op.in_data)

        if "OOB" in op.chan:
            ctx = "[OOB] -----------> "
        if not op.complete:
            op.print_req(indent=ctx + "  " * nesting.setdefault(ctx, 0))
            nesting[ctx] += 1
        else:
            nesting[ctx] -= 1
            op.print_reply(indent=ctx + "  " * nesting.setdefault(ctx, 0))

if __name__ == "__main__":
    import sys
    dump_log(open(sys.argv[1]))

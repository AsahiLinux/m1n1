# SPDX-License-Identifier: MIT

from m1n1.utils import *
from m1n1.fw.dcp.ipc import *

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
        else:
            raise Exception(f"Unknown log cmd {optype}")

        yield op

def dump_log(fd):
    nesting = {
        "": 0,
        "OOB": 0,
    }
    for op in parse_log(fd):
        ctx = ""
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

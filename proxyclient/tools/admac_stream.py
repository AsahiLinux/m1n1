#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
import time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import argparse
from m1n1.hw.dart import DART
from m1n1.hw.admac import *

argparser = argparse.ArgumentParser()
argparser.add_argument("-b", "--bufsize", type=int, default=1024*32,
                       help="size of one DMA buffer (covered by one descriptor)")
argparser.add_argument("-n", "--node", type=str, default="admac-sio",
                       help="name of ADT node")
argparser.add_argument("-c", "--chan", "--channel", type=int, default=0,
                       help="channel no")
argparser.add_argument("-w", "--buswidth", type=E_BUSWIDTH, default=E_BUSWIDTH.W_32BIT,
                       help="DMA device-facing bus width")
argparser.add_argument("-v", "--verbose", action='store_true')
args = argparser.parse_args()

from m1n1.setup import p, u

# find full ADT path
path = None
for node in u.adt["/arm-io"]:
    if node.name == args.node:
        path = node._path.removeprefix("/device-tree")
        print(f"Found {path}", file=sys.stderr)
        if "clock-gates" in node._properties:
            print(f"Enabling {path}", file=sys.stderr)
            p.pmgr_adt_clocks_enable(path)
        break

if path is None:
    print(f"No instance named {args.node:r} found!", file=sys.stderr)
    sys.exit(1)

admac_node = u.adt[path]

iommu_mappers = dict()
for node in u.adt["/arm-io"].walk_tree():
    if "compatible" in node._properties and node.compatible == ["iommu-mapper"]:
        iommu_mappers[getattr(node, "AAPL,phandle")] = node

mapper = iommu_mappers[admac_node.iommu_parent]
dart_path = mapper._parent_path.removeprefix("/device-tree")[:-1]
dart_idx = mapper.reg

if "clock-gates" in u.adt[dart_path]._properties:
    print(f"Enabling {dart_path}", file=sys.stderr)
    p.pmgr_adt_clocks_enable(path)

dart = DART.from_adt(u, dart_path)
admac = ADMAC(u, admac_node.get_reg(0)[0], dart,
              dart_stream=dart_idx, debug=args.verbose)

chan = admac.chans[args.chan]
chan.disable()
chan.reset()
chan.read_reports()
chan.buswidth = args.buswidth
chan.framesize = E_FRAME.F_1_WORD
chan.sram_carveout = (0x0, 0x1000)

if chan.tx:
    chan.submit(bytearray(args.bufsize))
else:
    chan.submit(buflen=args.bufsize)
chan.enable()

try:
    if chan.tx:
        while (buf := sys.stdin.buffer.read(args.bufsize)):
            while not chan.can_submit():
                chan.poll()
            chan.submit(buf)
    else:
        while True:
            while chan.can_submit():
                chan.submit(buflen=args.bufsize)
            sys.stdout.buffer.write(chan.poll())
except KeyboardInterrupt:
    pass

chan.disable()

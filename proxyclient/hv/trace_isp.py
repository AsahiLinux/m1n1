#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
from m1n1.trace.isp import ISPTracer

# bootargs += camLogging=0xfffffffffffff
# all opcodes: https://pastebin.com/F8h7eDRB
dev_name = [node.name for node in u.adt["/arm-io"] if node.name.startswith("isp")][0]
dev_path = "/arm-io/%s" % (dev_name)
dart_dev_path = "/arm-io/dart-%s" % (dev_name)
print(dev_path, dart_dev_path)

# t8122 and t6030 have no power-gates in dart-isp, turn ISP_SYS on manually
if u.adt["/chosen"].chip_id == 0x8122:
    hv.p.pmgr_power_enable(45)
elif u.adt["/chosen"].chip_id == 0x6030:
    hv.p.pmgr_power_enable(104)

tracer = ISPTracer(hv, dev_path, dart_dev_path, verbose=4)
tracer.start()
dart = tracer.dart_tracer.dart

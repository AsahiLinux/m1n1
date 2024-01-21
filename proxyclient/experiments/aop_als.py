#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct
from construct import *

from m1n1.setup import *
from m1n1.hw.dart import DART
from m1n1.fw.aop.client import AOPClient
from m1n1.fw.aop.ipc import *

# aop nodes have no clocks described in adt for j293. it does it itself
p.pmgr_adt_clocks_enable("/arm-io/aop")
p.pmgr_adt_clocks_enable("/arm-io/dart-aop")

dart = DART.from_adt(u, "/arm-io/dart-aop",
                     iova_range=(u.adt["/arm-io/dart-aop"].vm_base, 0x1000000000))
dart.initialize()

aop = AOPClient(u, "/arm-io/aop", dart)
aop.update_bootargs({
    'p0CE': 0x20000,
    'laCn': 0x0,
    'tPOA': 0x1,
    "gila": 0x80,
})
aop.verbose = 4

p.dapf_init_all()
aop.asc.OUTBOX_CTRL.val = 0x20001 # (FIFOCNT=0x0, OVERFLOW=0, EMPTY=1, FULL=0, RPTR=0x0, WPTR=0x0, ENABLE=1)

aop.start()
for epno in [0x20, 0x21, 0x22, 0x24, 0x25, 0x26, 0x27, 0x28]:
    aop.start_ep(epno)
aop.work_for(0.3)
alsep = aop.als
alsep.VERBOSE = True

def start():
    #ret = alsep.roundtrip(GetProperty(key=AOPPropKey.MANUFACTURER))
    #print(ret.rets.value.decode("ascii")) # FireFish2
    ret = alsep.send_notify(GetProperty(key=AOPPropKey.MANUFACTURER))
    ret = alsep.send_notify(ALSSetPropertyVerbosity(level=0xffffffff)) # retcode: 0
    # [syslog] * [ALSAOPDriver.cpp:267]setProperty Setting log level = -1

    dump = """
00000000  09 00 00 10 00 00 00 00  02 24 00 00 00 00 00 00  |.........$......|
00000010  00 00 00 00 00 00 00 00  99 00 00 00 02 10 04 00  |................|
00000020  24 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |$...............|
00000030  00 00 00 00 0b 00 00 00  01 02 00 00 00 ad ab 0a  |................|
00000040  00 01 91 00 9a 59 fa 00  64 00 64 00 08 08 08 04  |.....Y..d.d.....|
00000050  09 63 eb ff ff d4 0e 00  00 c7 ce ff ff 23 2e 00  |.c...........#..|
00000060  00 a2 08 cd 14 d6 5f 77  05 00 00 00 00 00 02 00  |......_w........|
00000070  80 aa 7e 53 7f 10 84 d9  7e 68 7f 68 7f b3 7f f1  |..~S....~h.h....|
00000080  7d 00 00 00 00 00 03 5b  7e 56 7e 00 80 ca 83 e0  |}......[~V~.....|
00000090  7e 79 7f 00 80 8d 80 f1  7f 00 00 00 00 00 02 f3  |~y..............|
000000a0  7c 00 80 38 7f 88 83 0b  7f 05 7f b9 7f b9 7f 0f  ||..8............|
000000b0  7e 00 00 00 00 00 06 75  7e 38 7f 69 7f bf 83 f2  |~......u~8.i....|
000000c0  7e 16 7f 4e 7f 33 7f 1f  7d                       |~..N.3..}       |
    """
    ret = alsep.send_notify(ALSSetPropertyCalibration(value=chexundump(dump)[0x38:]))
    # [syslog] * [ALSCT720.cpp:1138]loadALSCalibrationData: ALS sensor is calibrated
    # retcode: 0xe00002bc

    ret = alsep.send_notify(ALSSetPropertyInterval(interval=200000))
    # [syslog] * [ALSCT720.cpp:690]configureSensor - Configure sensor with gain 8 and integration time 197380
    # [syslog] * [ALSCT720.cpp:708]setSensorEnabled - Enabling the sensor.

    if 0: # test that on/off works
        aop.work_for(0.5)
        ret = alsep.send_notify(ALSSetPropertyInterval(interval=0))
        # [syslog] * [ALSCT720.cpp:598]setProperty: set report interval 0, _wakeHintMode = 0
        # [syslog] * [ALSCT720.cpp:735]setSensorEnabled - Disabling the sensor.
        ret = alsep.send_notify(ALSSetPropertyInterval(interval=200000))

    while True:
        aop.work()

try:
    start()
except KeyboardInterrupt:
    pass

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct
from construct import *

from m1n1.setup import *
from m1n1.shell import run_shell
from m1n1.hw.dart import DART
from m1n1.fw.aop.client import AOPClient
from m1n1.fw.aop.ipc import *

# aop nodes have no clocks described in adt for j293. it does it itself
p.pmgr_adt_clocks_enable("/arm-io/aop")
p.pmgr_adt_clocks_enable("/arm-io/dart-aop")

p.usb_iodev_vuart_setup(p.iodev_whoami())
p.iodev_set_usage(IODEV.USB_VUART, USAGE.UARTPROXY)
pdm2 = u.adt["/arm-io/aop/iop-aop-nub/aop-audio/audio-pdm2"]
decm = u.adt["/arm-io/aop/iop-aop-nub/aop-audio/dc-2400000"]

dart = DART.from_adt(u, "/arm-io/dart-aop",
                     iova_range=(u.adt["/arm-io/dart-aop"].vm_base, 0x1000000000))
dart.initialize()

aop = AOPClient(u, "/arm-io/aop", dart)
aop.update_bootargs({
    'p0CE': 0x20000,
    'laCn': 0x0,
    'tPOA': 0x1,
    "gila": 0x80,
    'gbda': 0xffffffff,
})
aop.verbose = 4

p.dapf_init_all()
aop.asc.OUTBOX_CTRL.val = 0x20001 # (FIFOCNT=0x0, OVERFLOW=0, EMPTY=1, FULL=0, RPTR=0x0, WPTR=0x0, ENABLE=1)

pdm2 = u.adt["/arm-io/aop/iop-aop-nub/aop-audio/audio-pdm2"]
decm = u.adt["/arm-io/aop/iop-aop-nub/aop-audio/dc-2400000"]

pdm_config = Container(
    bytesPerSample=pdm2.bytesPerSample, # 2 ??
    clockSource=pdm2.clockSource, # 'pll '
    pdmFrequency=pdm2.pdmFrequency, # 2400000
    pdmcFrequency=pdm2.pdmcFrequency, # 24000000
    slowClockSpeed=pdm2.slowClockSpeed, # 24000000
    fastClockSpeed=pdm2.fastClockSpeed, # 24000000
    channelPolaritySelect=pdm2.channelPolaritySelect, # 256
    channelPhaseSelect=99, # traces say 99 but device tree says 0 pdm2.channelPhaseSelect
    unk8=0xf7600,
    unk9=0, # this should be latency (thus 15, see below) but traces say 0
    ratios=Container(
        r1=decm.ratios.r0,
        r2=decm.ratios.r1,
        r3=decm.ratios.r2,
    ),
    filterLengths=decm.filterLengths,
    coeff_bulk=120,
    coefficients=GreedyRange(Int32sl).parse(decm.coefficients),
    unk10=1,
    micTurnOnTimeMs=pdm2.micTurnOnTimeMs, # 20
    unk11=1,
    micSettleTimeMs=pdm2.micSettleTimeMs, # 50
)

decimator_config = Container(
    latency=decm.latency, # 15
    ratios=Container(
        r1=decm.ratios.r0, # 15
        r2=decm.ratios.r1, # 5
        r3=decm.ratios.r2, # 2
    ),
    filterLengths=decm.filterLengths,
    coeff_bulk=120,
    coefficients=GreedyRange(Int32sl).parse(decm.coefficients),
)

def main():
    aop.start()
    for epno in [0x20, 0x21, 0x22, 0x24, 0x25, 0x26, 0x27, 0x28]:
        aop.start_ep(epno)
    aop.work_for(0.3)
    audep = aop.audio
    vtep = aop.voicetrigger

    #ret = aop.spuapp.send_roundtrip("i2c", ALSSetPropertyUnkE4())
    #print(ret)

    audep.send_notify(AudioAttachDevice(devid='pdm0'))
    audep.send_notify(AudioAttachDevice(devid='hpai'))
    audep.send_notify(AudioAttachDevice(devid='lpai'))

    audep.send_notify(SetDeviceProp(devid='lpai', modifier=301, data=Container(unk1=7, unk2=7, unk3=1, unk4=7)))
    audep.send_notify(SetDeviceProp(devid='pdm0', modifier=200, data=pdm_config))
    audep.send_notify(SetDeviceProp(devid='pdm0', modifier=210, data=decimator_config))

    data = open("data/aop/dump.voicetrigger.2024-01-29T01:49:14.803544.bin", "rb").read()
    ret = vtep.send_cmd(0x22, data[:0xa000])
    for n in range(3):
        ret = vtep.send_roundtrip(GetPropertyIsReady())
        print("state: %s" % (ret.state)) # cnfg
        assert(ret.state == "cnfg")

    #ret = vtep.send_notifycmd(0x24, struct.pack("<I", 0)) # reset
    ret = vtep.send_cmd(0x23, struct.pack("<I", 0))
    for n in range(3):
        ret = vtep.send_roundtrip(GetPropertyIsReady())
        print("state: %s" % (ret.state)) # runn
        assert(ret.state == "runn")

    if 1:
        ret = audep.send_notify(AudioPropertyPower(devid='lai ',
            data=Container(
                devid='lai ',
                unk1=1,
                target_pstate='runn',
                unk2=0,
            )
        ))

    # TODO garbage from lpai mic. Not sure why
    if 1:
        ret = audep.send_notify(AudioPropertyPower(devid='lpai',
            data=Container(
                devid='lpai',
                unk1=2,
                target_pstate='runn',
                unk2=1,
            )
        ))

    aop.work_forever()

try:
    main()
    pass
except KeyboardInterrupt:
    pass

#run_shell(locals(), poll_func=aop.work)

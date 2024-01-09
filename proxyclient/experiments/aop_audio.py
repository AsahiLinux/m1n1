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

# on the first terminal: M1N1DEVICE=/dev/ttyACM0 python3 experiments/aop_audio.py
# at that point (hpai at pw1), aop powers on admac and you should be dropped into a shell
# on a second terminal in parallel: M1N1DEVICE=/dev/ttyACM1 tools/admac_stream.py --node admac-aop-audio --channel 1 -v | xxd -g 4 -c 12 -e
# inside the shell (on the first terminal), aop_start()
# there should now be microphone samples streamed to admac
# see povik's commit #fc66046

# aop nodes have no clocks described in adt for j293. it does it itself
p.pmgr_adt_clocks_enable("/arm-io/aop")
p.pmgr_adt_clocks_enable("/arm-io/dart-aop")

# Set up a secondary proxy channel so that we can stream
# the microphone samples
p.usb_iodev_vuart_setup(p.iodev_whoami())
p.iodev_set_usage(IODEV.USB_VUART, USAGE.UARTPROXY)

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
    channelPhaseSelect=pdm2.channelPhaseSelect, # traces say 99 but device tree says 0
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

# incredible power state naming scheme:
# idle: in sleep state (default at boot)
# pw1 : in active state (admac powers on) but not capturing
# pwrd: start capturing
# to start capturing, we put the 'hpai' (high power audio input?) device
# from idle -> pw1 -> pwrd state. it starts capturing at pwrd
# shutdown sequence must also be pwrd -> pw1 -> idle

def aop_start():
    aop.audio.send_notify(SetDeviceProp(
        devid=u'hpai',
        modifier=202,
        data=Container(
            devid=u'hpai',
            cookie=2,
            target_pstate=u'pwrd',
            unk2=1,
        )
    ))

def aop_stop():
    aop.audio.send_notify(SetDeviceProp(
        devid='hpai',
        modifier=202,
        data=Container(
            devid='hpai',
            cookie=3,
            target_pstate='pw1 ',
            unk2=1,
        )
    ))

    aop.audio.send_notify(SetDeviceProp(
        devid='hpai',
        modifier=202,
        data=Container(
            devid='hpai',
            cookie=4,
            target_pstate='idle',
            unk2=0,
        )
    ))

def main():
    aop.start()
    for epno in [0x20, 0x21, 0x22, 0x24, 0x25, 0x26, 0x27, 0x28]:
        aop.start_ep(epno)
    aop.work_for(0.3)
    audep = aop.audio

    audep.send_notify(AttachDevice(devid='hpai')) # high power audio input; actual mic
    audep.send_notify(AttachDevice(devid='lpai')) # low power audio input; voice trigger mic
    audep.send_notify(AttachDevice(devid='pdm0')) # leap: low-energy audio processor I think
    # [syslog] * [udioPDMNodeBase.cpp:554]PDMDev<pdm0> off ->xi0 , 0->2400000 AP state 1

    # initChannelControl (<7, 7, 1, 7>)
    audep.send_notify(SetDeviceProp(devid='lpai', modifier=301, data=Container(unk1=7, unk2=7, unk3=1, unk4=7)))
    audep.send_notify(SetDeviceProp(devid='pdm0', modifier=200, data=pdm_config))
    audep.send_notify(SetDeviceProp(devid='pdm0', modifier=210, data=decimator_config))
    ret = audep.send_roundtrip(AudioPropertyState(devid="hpai"))
    print("hpai state: %s" % (ret.state)) # idle

    audep.send_notify(SetDeviceProp(
        devid='hpai',
        modifier=202,
        data=Container(
            devid='hpai',
            cookie=1,
            target_pstate='pw1 ',
            unk2=0,
        )
    ))

    ret = audep.send_roundtrip(AudioPropertyState(devid="hpai"))
    print("hpai state: %s" % (ret.state))
    assert(ret.state == "pw1 ")

try:
    main()
    pass
except KeyboardInterrupt:
    pass

run_shell(locals(), poll_func=aop.work)

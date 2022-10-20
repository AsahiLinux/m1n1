#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import struct
import traceback
from construct import *

from m1n1.setup import *
from m1n1.shell import run_shell
from m1n1.hw.dart import DART, DARTRegs
from m1n1.fw.asc import StandardASC, ASCDummyEndpoint
from m1n1.fw.asc.base import *
from m1n1.fw.aop import *
from m1n1.fw.aop.ipc import *
from m1n1.fw.afk.rbep import *
from m1n1.fw.afk.epic import *

# Set up a secondary proxy channel so that we can stream
# the microphone samples
p.usb_iodev_vuart_setup(p.iodev_whoami())
p.iodev_set_usage(IODEV.USB_VUART, USAGE.UARTPROXY)

p.pmgr_adt_clocks_enable("/arm-io/dart-aop")

adt_dc = u.adt["/arm-io/aop/iop-aop-nub/aop-audio/dc-2400000"]

pdm_config = Container(
    unk1=2,
    clockSource=u'pll ',
    pdmFrequency=2400000,
    unk3_clk=24000000,
    unk4_clk=24000000,
    unk5_clk=24000000,
    channelPolaritySelect=256,
    unk7=99,
    unk8=1013248,
    unk9=0,
    ratios=Container(
        r1=15,
        r2=5,
        r3=2,
    ),
    filterLengths=0x542c47,
    coeff_bulk=120,
    coefficients=GreedyRange(Int32sl).parse(adt_dc.coefficients),
    unk10=1,
    micTurnOnTimeMs=20,
    unk11=1,
    micSettleTimeMs=50,
)

decimator_config = Container(
    latency=15,
    ratios=Container(
        r1=15,
        r2=5,
        r3=2,
    ),
    filterLengths=0x542c47,
    coeff_bulk=120,
    coefficients=GreedyRange(Int32sl).parse(adt_dc.coefficients),
)

class AFKEP_Hello(AFKEPMessage):
    TYPE = 63, 48, Constant(0x80)
    UNK  = 7, 0

class AFKEP_Hello_Ack(AFKEPMessage):
    TYPE = 63, 48, Constant(0xa0)

class EPICEndpoint(AFKRingBufEndpoint):
    BUFSIZE = 0x1000

    def __init__(self, *args, **kwargs):
        self.seq = 0x0
        self.wait_reply = False
        self.ready = False
        super().__init__(*args, **kwargs)

    @msg_handler(0x80, AFKEP_Hello)
    def Hello(self, msg):
        self.rxbuf, self.rxbuf_dva = self.asc.ioalloc(self.BUFSIZE)
        self.txbuf, self.txbuf_dva = self.asc.ioalloc(self.BUFSIZE)

        self.send(AFKEP_Hello_Ack())

    def handle_hello(self, hdr, sub, fd):
        if sub.type != 0xc0:
            return False

        payload = fd.read()
        name = payload.split(b"\0")[0].decode("ascii")
        self.log(f"Hello! (endpoint {name})")
        self.ready = True
        return True

    def handle_reply(self, hdr, sub, fd):
        if self.wait_reply:
            self.pending_call.read_resp(fd)
            self.wait_reply = False
            return True
        return False

    def handle_ipc(self, data):
        fd = BytesIO(data)
        hdr = EPICHeader.parse_stream(fd)
        sub = EPICSubHeaderVer2.parse_stream(fd)

        handled = False

        if sub.category == EPICCategory.REPORT:
            handled = self.handle_hello(hdr, sub, fd)
        if sub.category == EPICCategory.REPLY:
            handled = self.handle_reply(hdr, sub, fd)

        if not handled and getattr(self, 'VERBOSE', False):
            self.log(f"< 0x{hdr.channel:x} Type {hdr.type} Ver {hdr.version} Tag {hdr.seq}")
            self.log(f"  Len {sub.length} Ver {sub.version} Cat {sub.category} Type {sub.type:#x} Ts {sub.timestamp:#x}")
            self.log(f"  Unk1 {sub.unk1:#x} Unk2 {sub.unk2:#x}")
            chexdump(fd.read())

    def indirect(self, call, chan=0x1000000d, timeout=0.1):
        tx = call.ARGS.build(call.args)
        self.asc.iface.writemem(self.txbuf, tx[4:])

        cmd = self.roundtrip(IndirectCall(
            txbuf=self.txbuf_dva, txlen=len(tx) - 4,
            rxbuf=self.rxbuf_dva, rxlen=self.BUFSIZE,
            retcode=0,
        ), category=EPICCategory.COMMAND, typ=call.TYPE)
        fd = BytesIO()
        fd.write(struct.pack("<I", cmd.rets.retcode))
        fd.write(self.asc.iface.readmem(self.rxbuf, cmd.rets.rxlen))
        fd.seek(0)
        call.read_resp(fd)
        return call

    def roundtrip(self, call, chan=0x1000000d, timeout=0.3,
                  category=EPICCategory.NOTIFY, typ=None):
        tx = call.ARGS.build(call.args)
        fd = BytesIO()
        fd.write(EPICHeader.build(Container(
            channel=chan,
            type=EPICType.NOTIFY,
            version=2,
            seq=self.seq,
        )))
        self.seq += 1
        fd.write(EPICSubHeaderVer2.build(Container(
            length=len(tx),
            category=category,
            type=typ or call.TYPE,
        )))
        fd.write(tx)

        self.pending_call = call
        self.wait_reply = True
        self.send_ipc(fd.getvalue())

        deadline = time.time() + timeout
        while time.time() < deadline and self.wait_reply:
            self.asc.work()
        if self.wait_reply:
            self.wait_reply = False
            raise ASCTimeout("ASC reply timed out")

        return call

class SPUAppEndpoint(EPICEndpoint):
    SHORT = "SPUAppep"

class AccelEndpoint(EPICEndpoint):
    SHORT = "accelep"

class GyroEndpoint(EPICEndpoint):
    SHORT = "gyroep"

class UNK23Endpoint(EPICEndpoint):
    SHORT = "unk23ep"

class LASEndpoint(EPICEndpoint):
    SHORT = "lasep"
    #VERBOSE = True # <--- uncomment to see lid angle measurements

class WakehintEndpoint(EPICEndpoint):
    SHORT = "wakehintep"

class UNK26Endpoint(EPICEndpoint):
    SHORT = "unk26ep"

class AudioEndpoint(EPICEndpoint):
    SHORT = "audioep"


class OSLogMessage(Register64):
    TYPE        = 63, 56

class OSLog_Init(OSLogMessage):
    TYPE        = 63, 56, Constant(1)
    UNK         = 51, 0
    DVA         = 7, 0

class AOPOSLogEndpoint(ASCBaseEndpoint):
    BASE_MESSAGE = OSLogMessage
    SHORT = "oslog"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started = False

    @msg_handler(1, OSLog_Init)
    def Init(self, msg):
        self.iobuffer, self.iobuffer_dva = self.asc.ioalloc(0x1_0000)
        self.send(OSLog_Init(DVA=self.iobuffer_dva//0x1000))
        self.started = True
        return True


class AOPClient(StandardASC, AOPBase):
    ENDPOINTS = {
        8: AOPOSLogEndpoint,

        0x20: SPUAppEndpoint,
        0x21: AccelEndpoint,
        0x22: GyroEndpoint,
        0x23: UNK23Endpoint,
        0x24: LASEndpoint,
        0x25: WakehintEndpoint,
        0x26: UNK26Endpoint,
        0x27: AudioEndpoint,
        0x28: EPICEndpoint,
        0x29: EPICEndpoint,
        0x2a: EPICEndpoint,
        0x2b: EPICEndpoint
    }

    def __init__(self, u, adtpath, dart=None):
        node = u.adt[adtpath]
        self.base = node.get_reg(0)[0]

        AOPBase.__init__(self, u, node)
        super().__init__(u, self.base, dart)

p.dapf_init_all()

dart = DART.from_adt(u, "/arm-io/dart-aop", iova_range=(0x2c000, 0x10_000_000))
dart.initialize()
dart.regs.TCR[0].set(BYPASS_DAPF=0, BYPASS_DART=0, TRANSLATE_ENABLE=1)
dart.regs.TCR[7].set(BYPASS_DAPF=0, BYPASS_DART=0, TRANSLATE_ENABLE=1)
dart.regs.TCR[15].val = 0x20100

aop = AOPClient(u, "/arm-io/aop", dart)

aop.update_bootargs({
    'p0CE': 0x20000,
#    'laCn': 0x0,
#    'tPOA': 0x1,
})

aop.verbose = 4

def set_aop_audio_pstate(devid, pstate):
    audep.roundtrip(SetDeviceProp(
        devid=devid,
        modifier=202,
        data=Container(
            devid=devid,
            cookie=1,
            target_pstate=pstate,
            unk2=1,
        )
    )).check_retcode()

try:
    aop.boot()
    for epno in range(0x20, 0x2c):
        aop.start_ep(epno)

    timeout = 10
    while (not aop.audioep.ready) and timeout:
        aop.work_for(0.1)
        timeout -= 1

    if not timeout:
        raise Exception("Timed out waiting on audio endpoint")

    print("Finished boot")

    audep = aop.audioep

    audep.roundtrip(AttachDevice(devid='pdm0')).check_retcode()
    audep.indirect(SetDeviceProp(
        devid='pdm0', modifier=200, data=pdm_config)
    ).check_retcode()
    audep.indirect(SetDeviceProp(
        devid='pdm0', modifier=210, data=decimator_config)
    ).check_retcode()
    audep.roundtrip(AttachDevice(devid='hpai')).check_retcode()
    audep.roundtrip(AttachDevice(devid='lpai')).check_retcode()
    audep.roundtrip(SetDeviceProp(
        devid='lpai', modifier=301, data=Container(unk1=7, unk2=7, unk3=1, unk4=7))
    ).check_retcode()
except KeyboardInterrupt:
    pass
except Exception:
    print(traceback.format_exc())

run_shell(locals(), poll_func=aop.work)

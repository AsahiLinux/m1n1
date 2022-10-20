# SPDX-License-Identifier: MIT

from m1n1.trace import Tracer
from m1n1.trace.dart import DARTTracer
from m1n1.trace.asc import ASCTracer, EP, EPState, msg, msg_log, DIR, EPContainer
from m1n1.utils import *
from m1n1.constructutils import *
from m1n1.fw.afk.rbep import *
from m1n1.fw.afk.epic import *
from m1n1.fw.aop import *
from m1n1.fw.aop.ipc import *

import sys

class AFKRingBufSniffer(AFKRingBuf):
    def __init__(self, ep, state, base, size):
        super().__init__(ep, base, size)
        self.state = state
        self.rptr = getattr(state, "rptr", 0)

    def update_rptr(self, rptr):
        self.state.rptr = rptr

    def update_wptr(self):
        raise NotImplementedError()

    def get_wptr(self):
        return struct.unpack("<I", self.read_buf(2 * self.BLOCK_SIZE, 4))[0]

    def read_buf(self, off, size):
        return self.ep.dart.ioread(0, self.base + off, size)

class AFKEp(EP):
    BASE_MESSAGE = AFKEPMessage

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)
        self.txbuf = None
        self.rxbuf = None
        self.state.txbuf = EPState()
        self.state.rxbuf = EPState()
        self.state.shmem_iova = None
        self.state.txbuf_info = None
        self.state.rxbuf_info = None
        self.state.verbose = 1

    def start(self):
        self.create_bufs()

    def create_bufs(self):
        if not self.state.shmem_iova:
            return
        if not self.txbuf and self.state.txbuf_info:
            off, size = self.state.txbuf_info
            self.txbuf = AFKRingBufSniffer(self, self.state.txbuf,
                                           self.state.shmem_iova + off, size)
        if not self.rxbuf and self.state.rxbuf_info:
            off, size = self.state.rxbuf_info
            self.rxbuf = AFKRingBufSniffer(self, self.state.rxbuf,
                                           self.state.shmem_iova + off, size)

    Init =          msg_log(0x80, DIR.TX)
    Init_Ack =      msg_log(0xa0, DIR.RX)

    GetBuf =        msg_log(0x89, DIR.RX)

    Shutdown =      msg_log(0xc0, DIR.TX)
    Shutdown_Ack =  msg_log(0xc1, DIR.RX)

    @msg(0xa1, DIR.TX, AFKEP_GetBuf_Ack)
    def GetBuf_Ack(self, msg):
        self.state.shmem_iova = msg.DVA
        self.txbuf = None
        self.rxbuf = None
        self.state.txbuf = EPState()
        self.state.rxbuf = EPState()
        self.state.txbuf_info = None
        self.state.rxbuf_info = None

    @msg(0xa2, DIR.TX, AFKEP_Send)
    def Send(self, msg):
        for data in self.txbuf.read():
            #if self.state.verbose >= 3:
            if True:
                self.log(f"===TX DATA=== epid={self.epid} rptr={self.txbuf.state.rptr:#x}")
                chexdump(data)
                self.log(f"===END DATA===")
                self.log("Backtrace on TX data:")
                self.hv.bt()
            self.handle_ipc(data, dir=">")
        return True

    Hello =         msg_log(0xa3, DIR.TX)

    @msg(0x85, DIR.RX, AFKEPMessage)
    def Recv(self, msg):
        for data in self.rxbuf.read():
            #if self.state.verbose >= 3:
            if True:
                self.log(f"===RX DATA=== epid={self.epid} rptr={self.rxbuf.state.rptr:#x}")
                chexdump(data)
                self.log(f"===END DATA===")
            self.handle_ipc(data, dir="<")
        return True

    def handle_ipc(self, data, dir=None):
        pass

    @msg(0x8a, DIR.RX, AFKEP_InitRB)
    def InitTX(self, msg):
        off = msg.OFFSET * AFKRingBuf.BLOCK_SIZE
        size = msg.SIZE * AFKRingBuf.BLOCK_SIZE
        self.state.txbuf_info = (off, size)
        self.create_bufs()

    @msg(0x8b, DIR.RX, AFKEP_InitRB)
    def InitRX(self, msg):
        off = msg.OFFSET * AFKRingBuf.BLOCK_SIZE
        size = msg.SIZE * AFKRingBuf.BLOCK_SIZE
        self.state.rxbuf_info = (off, size)
        self.create_bufs()

class DummyAFKEp(AFKEp):
    def handle_ipc(self, data, dir=None):
        pass

class EPICEp(AFKEp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_call = None
        self.pending_cmd = None

    def handle_hello(self, hdr, sub, fd):
        if sub.type != 0xc0:
            return False

        payload = fd.read()
        name = payload.split(b"\0")[0].decode("ascii")
        self.log(f"Hello! (endpoint {name})")
        return True

    def handle_notify(self, hdr, sub, fd):
        for calltype in CALLTYPES:
            if calltype.matches(hdr, sub):
                call = calltype.from_stream(fd)
                self.trace_call_early(call)
                self.pending_call = call
                return True

        return False

    def handle_reply(self, hdr, sub, fd):
        if self.pending_call is None:
            return False

        call = self.pending_call
        call.read_resp(fd)
        self.trace_call(call)
        self.pending_call = None
        return True

    def dispatch_ipc(self, dir, hdr, sub, fd):
        if sub.category == EPICCategory.COMMAND:
            return self.handle_notify(hdr, sub, fd)
        if dir == "<" and sub.category == EPICCategory.REPORT:
            return self.handle_hello(hdr, sub, fd)
        if dir == ">" and sub.category == EPICCategory.NOTIFY:
            return self.handle_notify(hdr, sub, fd)
        if dir == "<" and sub.category == EPICCategory.REPLY:
            return self.handle_reply(hdr, sub, fd)

    def handle_ipc(self, data, dir=None):
        fd = BytesIO(data)
        hdr = EPICHeader.parse_stream(fd)
        sub = EPICSubHeaderVer2.parse_stream(fd)

        if not getattr(self, 'VERBOSE', False):
            return

        self.log(f"{dir} 0x{hdr.channel:x} Type {hdr.type} Ver {hdr.version} Tag {hdr.seq}")
        self.log(f"  Len {sub.length} Ver {sub.version} Cat {sub.category} Type {sub.type:#x} Ts {sub.timestamp:#x}")
        self.log(f"  Unk1 {sub.unk1:#x} Unk2 {sub.unk2:#x}")

        if self.dispatch_ipc(dir, hdr, sub, fd):
            return

    def trace_call_early(self, call):
        # called at TX time
        if isinstance(call, IndirectCall):
            call.read_txbuf(self)

    def trace_call(self, call):
        if isinstance(call, IndirectCall):
            call.read_rxbuf(self)
            call = call.unwrap()
        call.dump(self.log)

class SPUAppEp(EPICEp):
    SHORT = "SPUApp"

class AccelEp(EPICEp):
    SHORT = "accel"

class GyroEp(EPICEp):
    SHORT = "gyro"

class LASEp(EPICEp):
    SHORT = "las"

class WakeHintEp(EPICEp):
    SHORT = "wakehint"

class UNK26Ep(EPICEp):
    SHORT = "unk26"

class AudioEp(EPICEp):
    SHORT = "aop-audio"
    VERBOSE = True

class VoiceTriggerEp(EPICEp):
    SHORT = "aop-voicetrigger"
    VERBOSE = True


class AOPTracer(ASCTracer, AOPBase):
    ENDPOINTS = {
        0x20: SPUAppEp,
        0x21: AccelEp,
        0x22: GyroEp,
        0x24: LASEp,
        0x25: WakeHintEp,
        0x26: UNK26Ep,
        0x27: AudioEp,
        0x28: VoiceTriggerEp,
    }

    def __init__(self, hv, devpath, verbose=False):
        self.default_bootargs = None
        super().__init__(hv, devpath, verbose)
        self.u = hv.u
        AOPBase.__init__(self, hv.u, self.dev)

    def start(self, *args):
        self.default_bootargs = self.read_bootargs()
        super().start(*args)

    def w_CPU_CONTROL(self, val):
        if val.RUN:
            self.bootargs = self.read_bootargs()
            self.log("Bootargs patched by AP:")
            self.default_bootargs.dump_diff(self.bootargs, self.log)
            self.log("(End of list)")
        super().w_CPU_CONTROL(val)

    @classmethod
    def replay(cls, f, passthru=False):
        epmap = dict()
        epcont = EPContainer()

        class FakeASCTracer:
            def __init__(self):
                self.hv = None

            def log(self, str):
                print(str)
        asc_tracer = FakeASCTracer()

        for cls in cls.mro():
            eps = getattr(cls, "ENDPOINTS", None)
            if eps is None:
                break
            for k, v in eps.items():
                if k in epmap:
                    continue
                ep = v(asc_tracer, k)
                epmap[k] = ep
                if getattr(epcont, ep.name, None):
                    ep.name = f"{ep.name}{k:02x}"
                setattr(epcont, ep.name, ep)
                ep.start()

        def readdump(firstline, hdr, f):
            l = firstline
            assert hdr in l
            postscribe = l[l.index(hdr) + len(hdr):]
            annotation = dict([s.split("=") for s \
                              in postscribe.strip().split(" ")])

            dump = []
            for l in f:
                if "===END DATA===" in l:
                    break
                dump.append(l)
            return chexundump("".join(dump)), annotation

        def read_txbuf(icall, ep):
            hdr = "===COMMAND TX DATA==="
            for l in f:
                if hdr in l:
                    break
            data, annot = readdump(l, hdr, f)
            assert int(annot["addr"], 16) == icall.args.txbuf
            icall.txbuf = data
        def read_rxbuf(icall, ep):
            hdr = "===COMMAND RX DATA==="
            for l in f:
                if hdr in l:
                    break
            data, annot = readdump(l, hdr, f)
            assert int(annot["addr"], 16) == icall.rets.rxbuf
            icall.rxbuf = data
        IndirectCall.read_rxbuf = read_rxbuf
        IndirectCall.read_txbuf = read_txbuf

        for l in f:
            if (rxhdr := "===RX DATA===") in l:
                dir = "<"
                hdr = rxhdr
            elif (txhdr := "===TX DATA===") in l:
                dir = ">"
                hdr = txhdr
            else:
                if passthru:
                    print(l, end="")
                continue
            data, annot = readdump(l, hdr, f)
            epid = int(annot["epid"])
            epmap[epid].handle_ipc(data, dir)
                        

if __name__ == "__main__":
    # We can replay traces by saving the textual output of live tracing
    # and then passing it to this script.
    with open(sys.argv[1]) as f:
        AOPTracer.replay(f)
    sys.exit(0)

dart_aop_tracer = DARTTracer(hv, "/arm-io/dart-aop", verbose=4)
dart_aop_tracer.start()

dart_aop_base = u.adt["/arm-io/dart-aop"].get_reg(0)[0]

#hv.trace_range(irange(*u.adt["/arm-io/dart-aop"].get_reg(1)))
#hv.trace_range(irange(*u.adt["/arm-io/aop"].get_reg(1)))
#hv.trace_range(irange(*u.adt["/arm-io/aop"].get_reg(3)))
#hv.trace_range(irange(*u.adt["/arm-io/admac-aop-audio"].get_reg(0)))

aop_tracer = AOPTracer(hv, "/arm-io/aop", verbose=1)
aop_tracer.start(dart_aop_tracer.dart)

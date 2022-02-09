
from mmap import PAGESIZE
from . import ADTDevTracer
from .asc import *
from ..hw.uat import UAT

from m1n1.proxyutils import RegMonitor

from construct import *
from construct.core import Int16ul, Int32ul, Int64ul, Int8ul


ControlStruct = Struct(
    "unkptr_0" / Int64ul, # allocation size: 0x4000
    "unk_8" / Int32ul,
    "unk_c"/ Int32ul,
    "unkptr_10" / Int64ul, # allocation size: 0x34000
    "unkptr_18" / Int64ul, # allocation size: 0x88000, heap?
    "unkptr_20" / Int64ul, # allocation size: 0x4000, but probally only 0x80 bytes long
    "unk_28" / Int32ul,
    "unk_2c" / Int32ul,
    "unk_30" / Int32ul,
)

class InitMsg(Register64):
    TYPE    = 59, 52

class InitReq(InitMsg):
    TYPE    = 59, 52, Constant(0x1)
    UNK     = 47, 0

class InitResp(InitMsg):
    # example: 0x0010_4fa0_0c388000
    TYPE    = 59, 52, Constant(0x1)
    UNK1    = 47, 44
    ADDR    = 43, 0 # GPU VA that gets filled with a repating 0xefefefef pattern

class InitEp(EP):
    # This endpoint receives and sends one message during boot.
    # Potentially a "Ready" and a "Init" message.
    BASE_MESSAGE = InitMsg

    @msg(0x1, DIR.RX, InitReq)
    def init_req(self, msg):
        print(f"  Received Init Request, {msg.UNK:x}")

    @msg(0x1, DIR.TX, InitResp)
    def init_resp(self, msg):
        print(f"  CPU Sent Init Response {msg.UNK1:x}, ADDR: {msg.ADDR:x}")

        # monitor whatever is at this address
        self.tracer.mon_addva(msg.ADDR, 0x4000, "init_region")
        self.tracer.mon.poll()
        return True

class GpuMsg(Register64):
    TYPE    = 55, 48

class PongMsg(GpuMsg):
    TYPE    = 59, 52
    UNK     = 47, 0

class PongEp(EP):
    # This endpoint recives pongs. The cpu code reads some status registers after receiving one
    # Might be a "work done" message.
    BASE_MESSAGE = GpuMsg

    @msg(0x42, DIR.RX, PongMsg)
    def pong_rx(self, msg):
        print(f"  Pong {msg.UNK:x}")
        if msg.UNK != 0:
            print(f"  Pong had unexpected value{msg.UNK:x}")
            self.hv.run_shell()

        self.tracer.pong()
        return True

    @msg(0x81, DIR.TX, PongMsg)
    def init_ep(self, msg):
        print(f"  Init {msg.UNK:x}")

        addr = msg.UNK

        #self.tracer.mon_addva(addr, 0x4000, "control_struct")
        control = ControlStruct.parse(self.tracer.uat.ioread(0, addr, 0x34))
        #self.tracer.mon_addva(control.unkptr_0, 0x4000, "control_struct->unkptr_0")
        # self.tracer.mon_addva(control.unkptr_10, 0x34000, "control_struct->unkptr_10")
        # self.tracer.mon_addva(control.unkptr_18, 0x88000, "control_struct->unkptr_18")
        #self.tracer.mon_addva(control.unkptr_20, 0x4000, "control_struct->unkptr_20")
        self.tracer.control = control

        self.tracer.mon.poll()

        self.tracer.kick_init()
        return True

class KickMsg(GpuMsg):
    TYPE    = 59, 52
    KICK    = 7, 0 # Seen: 17, 16 (common), 9, 8, 1 (common), 0 (common)

class KickEp(EP):
    BASE_MESSAGE = GpuMsg

    @msg(0x83, DIR.TX, KickMsg)
    def kick(self, msg):
        print(f"  Kick {msg.KICK:x}")
        self.tracer.kick(msg.KICK)

        return True

class AGXTracer(ASCTracer):
    ENDPOINTS = {
        0x01: InitEp,
        0x20: PongEp,
        0x21: KickEp
    }

    PAGESIZE = 0x4000

    def __init__(self, hv, devpath, verbose=False):
        super().__init__(hv, devpath, verbose)
        self.uat = UAT(hv.iface, hv.u)
        self.mon = RegMonitor(hv.u, ascii=True)
        self.dev_sgx = hv.u.adt["/arm-io/sgx"]
        self.gpu_region = getattr(self.dev_sgx, "gpu-region-base")
        self.gpu_region_size = getattr(self.dev_sgx, "gpu-region-size")
        self.gfx_shared_region = getattr(self.dev_sgx, "gfx-shared-region-base")
        self.gfx_shared_region_size = getattr(self.dev_sgx, "gfx-shared-region-size")
        self.gfx_handoff = getattr(self.dev_sgx, "gfx-handoff-base")
        self.gfx_handoff_size = getattr(self.dev_sgx, "gfx-handoff-size")

        # self.mon.add(self.gpu_region, self.gpu_region_size, "contexts")
        # self.mon.add(self.gfx_shared_region, self.gfx_shared_region_size, "gfx-shared")
        # self.mon.add(self.gfx_handoff, self.gfx_handoff_size, "gfx-handoff")

        self.uat.set_ttbr(self.gpu_region)

    def mon_addva(self, va, size, name=""):
        self.mon.add(va, size, name, readfn= lambda a, s: self.uat.ioread(0, a, s))

    def kick(self, val):
        self.mon.poll()

        # if val not in [0x0, 0x1, 0x10, 0x11]:
        #     self.hv.run_shell()

    def pong(self):
        self.mon.poll()

    def kick_init(self):
        self.hv.run_shell()


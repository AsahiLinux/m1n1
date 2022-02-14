
from .asc import *
from .agx_control import ControlList
from ..hw.uat import UAT

from m1n1.proxyutils import RegMonitor
from m1n1.constructutils import *

from construct import *

ControlList = ControlList._reloadcls()


class WorkCommand_4(ConstructClass):
    """
        sent before WorkCommand_1 on the Submit3d queue.
        Might be for initilzing the tile buckets?

    Example:
    00000004 0c378018 ffffffa0 00000c00 00000006 00000900 08002c9a 00000000
    00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    """
    subcon = Struct(
        "magic" / Const(0x4, Int32ul),
        "ptr" / Int64ul, # These appare to be shared over multiple contexes
        "unk_c" / Int32ul, # Counts up by 0x100 each frame
        "flag" / Int32ul, # 2, 4 or 6
        "unk_14" / Int32ul,  # Counts up by 0x100 each frame? starts at diffrent point?
        "uuid" / Int32ul,
    )

class WorkCommand_6(ConstructClass):
    """
        occationally sent before WorkCommand_0 on the SubmitTA queue.

    Example:
    00000004 0c378018 ffffffa0 00000c00 00000006 00000900 08002c9a 00000000
    00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    """
    subcon = Struct(
        "magic" / Const(0x6, Int32ul),
        "unk_4" / Int32ul, # Might be context?
        "unk_8" / Int32ul, # 0
        "unk_c" / Int32ul, # 0
        "unk_10" / Int32ul, # 0x30
        "unkptr_14" / Int64ul, # same as unkptr_20 of the previous worckcommand_1, has some userspace VAs
        "size" / Int32ul,  # 0x100
    )


class WorkCommand_3(ConstructClass):
    """
    For compute

    Example:
    00000000  00000003 00000000 00000004 0c3d80c0 ffffffa0 00000000 00000000 00000000
    00000020  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    00000040  *
    00000060  00000000 00000000 00088000 00000015 00078000 00000015 000a6300 00000015
    00000080  000a6308 00000015 000a6310 00000015 000a6318 00000015 00000000 00000011
    000000a0  00008c60 00000000 00000041 00000000 000e8000 00000015 00000040 00000000
    000000c0  00000001 00000000 0000001c 00000000 00000000 00000000 00000000 00000000
    000000e0  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    00000100  *
    000001e0  00000000 00000000 0c311cc0 ffffffa0 00000240 00000000 00000000 00000000
    00000200  00000000 00000000 00000000 00000000 00000000 00000000 00088000 00000015
    00000220  00078024 00000015 00000000 00000000 00000000 00000000 00000000 00000000
    00000240  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    00000260  110022b3 00000000 ffffffff 00000500 00000015 00000000 00000000 00000000
    00000280  000c8014 ffffffa0 0c378014 ffffffa0 00003b00 00000005 00000000 00000000
    000002a0  120022b8 00000000 00000000 00000000 00029030 ffffffa0 00029038 ffffffa0
    000002c0  00000000 00000000 00000000 00000000 00000015 00000000 00000000 00000000
    000002e0  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    """

    subcon = Struct(
        "magic" / Const(0x3, Int32ul),
        "unk_4" / Int32ul,
        "context_id" / Int32ul,
        "unkptr_c" / Int64ul,

        # This struct embeeds some data that the Control List has pointers back to, but doesn't
        # seem to be actually part of this struct
        Padding(0x1e8 - 0x14),

        # offset 000001e8
        "controllist_ptr" / Int64ul,
        "controllist_size" / Int32ul,
        "controllist_data" / Pointer(this.controllist_ptr, Bytes(this.controllist_size)),
    )

    def parsed(self, ctx):
        self.controllist = ControlList.parse(self.controllist_data)

    def __repr__(self) -> str:
        str = super().__repr__(ignore=['magic', 'controllist_data'])
        str += f"\nControl List:\n{repr(self.controllist)}"
        return str


class WorkCommand_1(ConstructClass):
    """
    For 3D

    Example: 0xfa00c095640
    00000000  00000001 00000004 00000000 0c2d5f00 ffffffa0 000002c0 0c3d80c0 ffffffa0
    00000020  0c3e0000 ffffffa0 0c3e0100 ffffffa0 0c3e09c0 ffffffa0 01cb0000 00000015
    00000040  00000088 00000000 00000001 0010000c 00000000 00000000 00000000 00000000
    00000060  3a8de3be 3abd2fa8 00000000 00000000 0000076c 00000000 0000a000 00000000
    00000080  ffff8002 00000000 00028044 00000000 00000088 00000000 005d0000 00000015
    000000a0  00758000 00000015 0000c000 00000000 00000640 000004b0 0257863f 00000000
    000000c0  00000000 00000000 00000154 00000000 011d0000 00000015 011d0000 00000015
    000000e0  0195c000 00000015 0195c000 00000015 00000000 00000000 00000000 00000000
    00000100  00000000 00000000 00000000 00000000 0193c000 00000015 00000000 00000000
    00000120  0193c000 00000015 00000000 00000000 01b64000 00000015 00000000 00000000
    00000140  01b64000 00000015 00000000 00000000 01cb0000 00000015 01cb4000 00000015
    00000160  c0000000 00000003 01cb4000 00000015 00010280 00000000 00a38000 00000015
    00000180  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    000001a0  00000000 00000000 00000000 00000000 00000000 00000011 00008c60 00000000
    000001c0  00000000 00000000 00000000 00000000 0000001c 00000000 00000000 00000000
    000001e0  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    00000200  *
    000003c0  00000012 00028084 00000000 00000000 3a8de3be 3abd2fa8 00000000 00000000
    000003e0  0010000c 00000000 00025031 00000004 3f800000 00000700 00000000 00000001
    """

    subcon = Struct(
        "magic" / Const(0x1, Int32ul),
        "context_id" / Int32ul,
        "unk_8" / Int32ul,
        "controllist_ptr" / Int64ul, # Command list
        "controllist_size" / Int32ul,
        "controllist_data" / Pointer(this.controllist_ptr, Bytes(this.controllist_size)),
        "unkptr_18" / Int64ul,
        "unkptr_20" / Int64ul, # Size: 0x100
        "unkptr_28" / Int64ul, # Size: 0x8c0
        "unkptr_30" / Int64ul,
        "unkptr_38" / Int64ul,
        "unk_40" / Int64ul,
        "unk_48" / Int32ul,
        "unk_4c" / Int32ul,
        "unk_50" / Int64ul,
        "unk_58" / Int64ul,
        "uuid1" / Int32ul, # same across repeated submits
        "uuid2" / Int32ul, # same across repeated submits
        "unk_68" / Int64ul,
        "unk_70" / Int64ul,
    )

    def parsed(self, ctx):
        self.controllist = ControlList.parse(self.controllist_data)

    def __repr__(self) -> str:
        str = super().__repr__(ignore=['magic', 'controllist_data'])
        str += f"\nControl List:\n{repr(self.controllist)}"
        return str


class WorkCommand_0(ConstructClass):
    """
    For TA

    00000000  00000000 00000004 00000000 0c3d80c0 ffffffa0 00000002 00000000 0c3e0000
    00000020  ffffffa0 0c3e0100 ffffffa0 0c3e09c0 ffffffa0 00000000 00000200 00000000
    00000040  1e3ce508 1e3ce508 01cb0000 00000015 00000000 00000000 00970000 00000015
    00000060  01cb4000 80000015 006b0003 003a0012 00000001 00000000 00000000 00000000
    00000080  0000a000 00000000 00000088 00000000 01cb4000 00000015 00000000 00000000
    000000a0  0000ff00 00000000 007297a0 00000015 00728120 00000015 00000001 00000000
    000000c0  00728000 00040015 009f8000 00000015 00000000 00000000 00000000 00000000
    000000e0  0000a441 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    00000100  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000011
    00000120  00000000 00000000 0000001c 00000000 00008c60 00000000 00000000 00000000
    00000140  00000000 00000000 00000000 00000000 0000001c 00000000 00000000 00000000
    00000160  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
    00000180  *
    000003a0  00000000 00000000 00000000 00000000 00000000 00000000 00000000 000000f0
    000003c0  00000088 00000202 04af063f 00025031 00404030 00303024 000000c0 00000180
    000003e0  00000100 00008000 00000000 00000000 00000000 00000000 00000000 00000000
    """
    subcon = Struct(
        "magic" / Const(0x0, Int32ul),
        "context_id" / Int32ul,
        "unk_8" / Int32ul,
        "unkptr_c" / Int64ul,
        "unk_14" / Int64ul,
        "unkptr_1c" / Int64ul,
        "unkptr_24" / Int64ul,
        "unkptr_2c" / Int64ul,
        "unk_34" / Int64ul,
        "unk_3c" / Int32ul,
        "uuid1" / Int32ul,
        "uuid2" / Int32ul,
        "unkptr_48" / Int64ul,
        "unkptr_50" / Int64ul,
        "unkptr_58" / Int64ul,
        "unkptr_60" / Int64ul,

    )

class UnknownWorkCommand(ConstructClass):
    subcon = Struct(
        "magic" / Int32ul,
        "unk_4" / Int32ul,
        "unk_8" / Int32ul,
        "unk_c" / Int32ul,
        "unk_10" / Int32ul,
        "unk_14" / Int32ul,
        "unk_18" / Int32ul,
        "unk_1c" / Int32ul,
    )


class CmdBufWork(ConstructClass):
    subcon = Select(
        WorkCommand_0,
        WorkCommand_1,
        WorkCommand_3,
        WorkCommand_4,
        WorkCommand_6,

        UnknownWorkCommand
    )

CommandQueueRingbufferTail = {}

class CommandQueueInfo(ConstructClass):
    """ Structure type shared by Submit3D, SubmitTA and SubmitCompute
        Applications have multiple of these, one of each submit type
        TODO: Can applications have more than one of each type? One per encoder?

    """
    subcon = Struct(
        "unkptr_0" / Int64ul, # data at this pointer seems to match the current offests below
        "RingBuffer_addr" / Int64ul, # 0x4ff pointers
        "Ringbuffer_count" / Computed(0x4ff),
        "ContextInfo" / Int64ul, # ffffffa000000000, size 0x18 (shared by 3D and TA)
        "unkptr_18" / Int64ul, # eventually leads to userspace VAs
        "cpu_tail" / Int32ul, # controled by cpu, tail
        "gpu_tail" / Int32ul, # controled by gpu
        "offset3" / Int32ul, # controled by gpu
        "unk_2c" / Int32sl, # touched by both cpu and gpu, cpu likes -1, gpu likes 3. Might be a return value?
        "unk_30" / Int64ul, # zero
        "unk_38" / Int64ul, # 0xffffffffffff0000, page mask?
        "unk_40" / Int32ul, # 1
        "unk_44" / Int32ul, # 0
        "unk_48" / Int32ul, # 1, 2
        "unk_4c" / Int32sl, # -1
        "unk_50" / Int32ul, # Counts up for each new process or command queue
        "unk_54" / Int32ul, # always 0x04
        "unk_58" / Int64ul, # 0
        "unk_60" / Int32ul, # Set to 1 by gpu after work complete. Reset to zero by cpu
        Padding(0x20),
        "unk_84" / Int32ul, # Set to 1 by gpu after work complete. Reset to zero by cpu
        Padding(0x18),
        "unkptr_a0" / Int64ul, # Size 0x40

        # End of struct
    )

    def getTail(self):
        return self.cpu_tail
        try:
            return CommandQueueRingbufferTail[self._addr]
        except KeyError:
            return self.cpu_tail

    def setTail(self, new_tail):
        CommandQueueRingbufferTail[self._addr] = new_tail

    def getSubmittedWork(self, head):
        Work = []
        orig_tail = tail = self.getTail()
        count = 0

        while tail != head:
            count += 1
            stream = self._stream
            stream.seek(self.RingBuffer_addr + tail * 8, 0)
            pointer = Int64ul.parse_stream(stream)
            stream.seek(pointer, 0)

            Work.append(CmdBufWork.parse_stream(stream))

            tail = (tail + 1) % self.Ringbuffer_count

        #print(f"Parsed {count} items from {orig_tail} to {head}")

        #self.setTail(tail)
        return Work



class NotifyCmdQueueWork(ConstructClass):
    subcon = Struct (
        "queue_type" / Select(Const(0, Int32ul), Const(1, Int32ul), Const(2, Int32ul)),
        "cmdqueue_addr" / Int64ul,
        "cmdqueue" / Pointer(this.cmdqueue_addr, CommandQueueInfo),
        "head" / Int32ul,
        "unk_10" / Int32ul,
        "unk_14" / Int32ul,
        "padding" / Bytes(0x18),
    )

    TYPES = {
        0: "SubmitTA",
        1: "Submit3D",
        2: "SubmitCompute",
    }

    def get_workitems(self):
        try:
            return self.workItems
        except AttributeError:
            self.workItems = self.cmdqueue.getSubmittedWork(self.head)
            return self.workItems

    def __repr__(self):
        str = f"{self.TYPES[self.queue_type]}(0x{self.cmdqueue_addr & 0xfff_ffffffff:x}, {self.head}, {self.unk_10}, {self.unk_14})"
        str += "\n  WorkItems:"
        for work in self.get_workitems():
            str += f"\n\t{work}"
        return str


class UnknownMsg(ConstructClass):
    subcon = Struct (
        "msg_type" / Int32ul,
        "data" / Bytes(0x2c)
    )

    def __repr__(self):
        return f"Unknown(type={self.msg_type}, data={hexdump32(self.data)})"

class DeviceControl_17(ConstructClass):
    subcon =  Struct (
        "msg_type" / Const(0x17, Int32ul),
        "unk_4" / Int32ul,
        "unk_8" / Int32ul,
        "unk_c" / Int32ul,
        "unk_10" / Int32ul,
        "unk_14" / Int32ul,
        "unk_18" / Int32ul,
        "unkptr_1c" / Int64ul,
        "padding" / Bytes(0x0c),
        #Padding(0xc)
    )

    # def __repr__(self):
    #     return f"DeviceControl_17()"

class DeviceControl_19(ConstructClass):
    subcon =  Struct (
        "msg_type" / Const(0x19, Int32ul),
        Padding(0x2c)
    )

    def __repr__(self):
        return f"DeviceControl_19()"

class DeviceControl_1e(ConstructClass):
    subcon =  Struct (
        "msg_type" / Const(0x1e, Int32ul),
        # todo: more fields
        Padding(0x2c)
    )

    def __repr__(self):
        return f"DeviceControl_17()"

class DeviceControl_23(ConstructClass):
    subcon = Struct (
        "msg_type" / Const(0x23, Int32ul),
    )

    def __repr__(self):
        return f"DeviceControl_23()"

class ChannelMessage(ConstructClass):
    subcon = Select (
        NotifyCmdQueueWork,
        DeviceControl_17,
        DeviceControl_19,
        DeviceControl_23,

        UnknownMsg,
    )

ChannelState = Struct (
    "head" / Int32ul,
    Padding(0x0c),
    "unk1" / Int32ul,
    Padding(0x0c),
    "tail" / Int32ul,
    Padding(0x0c),
    "unk2" / Int32ul,
    Padding(0x0c),
    "gpu_head" / Int32ul,
    Padding(0x1c),
    "unk3" / Int32ul,
    Padding(0x1c),
)

ChannelInfo = Struct (
    "state_addr" / Int64ul,
    "state" / Lazy(Pointer(this.state_addr, ChannelState)),
    "ringbuffer_addr" / Int64ul,
    "ringbuffer" / Lazy(Pointer(this.ringbuffer_addr, Array(256, ChannelMessage))),
)

InitData = Struct(
    "unkptr_0" / Int64ul, # allocation size: 0x4000
    "unk_8" / Int32ul,
    "unk_c"/ Int32ul,
    "channels_addr" / Int64ul, # 0xfa00c338000 allocation size: 0x34000
    "channels" / Pointer(this.channels_addr, Array(17, ChannelInfo)),
    "unkptr_18" / Int64ul, # 0xfa000200000 allocation size: 0x88000, heap?
    "unkptr_20" / Int64ul, # allocation size: 0x4000, but probally only 0x80 bytes long
    "unk_28" / Int32ul,
    "unk_2c" / Int32ul,
    "unk_30" / Int32ul
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
        self.tracer.mon_addva(0, msg.ADDR, 0x4000, "init_region")
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
        #print(f"  Pong {msg.UNK:x}")
        if msg.UNK != 0:
            print(f"  Pong had unexpected value{msg.UNK:x}")
            self.hv.run_shell()

        self.tracer.pong()
        return True

    @msg(0x81, DIR.TX, PongMsg)
    def init_ep(self, msg):
        print(f"  Init {msg.UNK:x}")

        self.tracer.pong_init(msg.UNK)
        return True

class KickMsg(GpuMsg):
    TYPE    = 59, 52
    KICK    = 7, 0 # Seen: 17, 16 (common), 9, 8, 1 (common), 0 (common)

class KickEp(EP):
    BASE_MESSAGE = GpuMsg

    @msg(0x83, DIR.TX, KickMsg)
    def kick(self, msg):
        #print(f"  Kick {msg.KICK:x}")
        self.tracer.kick(msg.KICK)

        return True

class AGXTracer(ASCTracer):
    ENDPOINTS = {
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

        self.channels_read_ptr = [0] * 17
        self.channelNames = [
            "TA_0", "3D_0", "CL_0",
            "TA_1", "3D_1", "CL_1",
            "TA_2", "3D_2", "CL_2",
            "TA_3", "3D_3", "CL_3",
            "DevCtrl",
            "Return0", "Return2", "Return3", "Return4"
        ]

        self.ignorelist = []
        self.last_msg = None

        # self.mon.add(self.gpu_region, self.gpu_region_size, "contexts")
        # self.mon.add(self.gfx_shared_region, self.gfx_shared_region_size, "gfx-shared")
        # self.mon.add(self.gfx_handoff, self.gfx_handoff_size, "gfx-handoff")

        self.uat.set_ttbr(self.gpu_region)

    def mon_addva(self, ctx, va, size, name=""):
        self.mon.add(va, size, name, readfn= lambda a, s: self.uat.ioread(ctx, a, s))

    def print_ringmsg(self, channel):
        addr = self.initdata.channels[channel].ringbuffer_addr
        addr += self.channels_read_ptr[channel] * 0x30
        self.channels_read_ptr[channel] = (self.channels_read_ptr[channel] + 1) % 256
        msg = ChannelMessage.parse_stream(self.uat.iostream(0, addr))

        if isinstance(msg, NotifyCmdQueueWork) and (msg.cmdqueue_addr & 0xfff_ffffffff) in self.ignorelist:
            return

        print(f"Channel[{self.channelNames[channel]}]: {msg}")
        self.last_msg = msg

    def ignore(self, addr):
        self.ignorelist += [addr & 0xfff_ffffffff]

    def kick(self, val):
        self.mon.poll()

        if val == 0x10: # Kick Firmware
            #print("KickFirmware")
            self.uat.invalidate_cache()
            return

        if val == 0x11: # Device Control
            channel = 12
            self.uat.invalidate_cache()

        elif val < 0x10:
            type = val & 3
            assert type != 3
            piority = (val >> 2) & 3
            channel = type + piority * 3

        else:
            raise(Exception("Unknown kick type"))

        state = self.initdata.channels[channel].state()

        while state.tail != self.channels_read_ptr[channel]:
            self.print_ringmsg(channel)

        # if val not in [0x0, 0x1, 0x10, 0x11]:
        if self.last_msg and isinstance(self.last_msg, NotifyCmdQueueWork):
            self.hv.run_shell()

            self.last_msg = None

    def pong(self):
        self.mon.poll()

        # check the gfx -> cpu channels
        for i in range(13, 17):
           state = self.initdata.channels[i].state()



    def trace_uatrange(self, ctx, start, size):
        ranges = self.uat.iotranslate(ctx, start, size)
        for range in ranges:
            start, size = range
            if start:
                self.hv.trace_range(irange(start, size), mode=TraceMode.SYNC)


    def pong_init(self, addr):
        self.initdata_addr = addr
        self.initdata = InitData.parse_stream(self.uat.iostream(0, addr))

        # for i, chan in list(enumerate(self.initdata.channels))[13:16]:
        #     self.mon_addva(0, chan.state_addr, 0x40, f"chan[{i}]->state")
        #     self.mon_addva(0, chan.ringbuffer_addr, 256 * 0x30, f"chan[{i}]->ringbuffer")

        self.mon.poll()

        self.hv.run_shell()


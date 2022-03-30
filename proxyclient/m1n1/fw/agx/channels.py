
from m1n1.utils import *
from m1n1.constructutils import ConstructClass
from construct import *

ChannelState = Struct (
    "head" / Default(Int32ul, 0),
    Padding(0x1c),
    "tail" / Default(Int32ul, 0),
    Padding(0x1c),
    "gpu_head" / Default(Int32ul, 0),
    Padding(0x1c),
    "gpu_tail" / Default(Int32ul, 0),
    Padding(0x1c),
)


def ChannelInfo(msg_cls):
    return Struct (
        "state_addr" / Int64ul,
        "state" / Pointer(this.state_addr, ChannelState),
        "ringbuffer_addr" / Int64ul,
        "ringbuffer" / Pointer(this.ringbuffer_addr, Array(256, msg_cls)),
    )

class NotifyCmdQueueWork(ConstructClass):
    subcon = Struct (
        "queue_type" / Default(Int32ul, 0),
        "cmdqueue_addr" / Default(Int64ul, 0),
        #"cmdqueue" / Pointer(this.cmdqueue_addr, CommandQueueInfo),
        "head" / Default(Int32ul, 0),
        "unk_10" / Default(Int32ul, 0),
        "unk_14" / Default(Int32ul, 0),
        Padding(0x18),
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
        if (self.cmdqueue_addr == 0):
            return "<Empty NotifyCmdQueueWork>"

        str = f"{self.TYPES[self.queue_type]}(0x{self.cmdqueue_addr & 0xfff_ffffffff:x}, {self.head}, {self.unk_10}, {self.unk_14})"
        # str += "\n  WorkItems:"
        # for work in self.get_workitems():
        #     str += f"\n\t{work}"
        return str

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
        Padding(0xc)
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

# class DeviceControl_dummy(ConstructClass):
#     subcon =  Struct (
#         "msg_type" / Const(0xcc, Int32ul),
#         Padding(0x2c)
#     )

#     def __init__(self):
#         self.msg_type = 0xcc


class UnknownMsg(ConstructClass):
    subcon = Struct (
        "msg_type" / Int32ul,
        "data" / Bytes(0x2c),
    )

    def __init__(self):
        self.msg_type = 0xcc
        self.data = b"\0"*0x2c

    def __repr__(self):
        return f"Unknown(type={self.msg_type:x}, data={hexdump32(self.data)})"


DeviceControlMsg = Select (
    DeviceControl_17,
    DeviceControl_19,
    DeviceControl_23,
    UnknownMsg,
)

channelNames = [
    "TA_0", "3D_0", "CL_0",
    "TA_1", "3D_1", "CL_1",
    "TA_2", "3D_2", "CL_2",
    "TA_3", "3D_3", "CL_3",
    "DevCtrl",
    "Return0", "Return1", "Return2", "Return3"
]

class Channels(ConstructClass):

    subcon = Struct(
        # 12 channels for notifiy command queues of work submission
        *[ channelNames[i] / ChannelInfo(NotifyCmdQueueWork) for i in range(12)],
        # Device Control Channel
        "DevCtrl" / ChannelInfo(DeviceControlMsg),
        # Return Channels
        "Return0" / ChannelInfo(Bytes(0x38)),
        "Return1" / ChannelInfo(UnknownMsg),
        "Return2" / ChannelInfo(UnknownMsg),
        "Return3" / ChannelInfo(UnknownMsg),
    )

    def __init__(self, heap, shared_heap):
        for i in range(12):
            setattr(self, channelNames[i], Container(
                state_addr = shared_heap.malloc(ChannelState.sizeof()),
                ringbuffer_addr = heap.malloc(256 * NotifyCmdQueueWork.sizeof()),
                ringbuffer = [Container()] * 256,
            ))

        self.DevCtrl = Container(
            state_addr = shared_heap.malloc(ChannelState.sizeof()),
            ringbuffer_addr = heap.malloc(256 * UnknownMsg.sizeof()),
            ringbuffer = [UnknownMsg()] * 256,
        )

        self.Return0 = Container(
            state_addr = heap.malloc(ChannelState.sizeof()),
            ringbuffer_addr = heap.malloc(256 * 0x38),
            ringbuffer = [b"\0" * 0x38] * 256
        )

        self.Return1 = Container(
            state_addr = heap.malloc(ChannelState.sizeof()),
            ringbuffer_addr = heap.malloc(256 * UnknownMsg.sizeof()),
            ringbuffer = [UnknownMsg()] * 256,
        )

        self.Return2 = Container(
            state_addr = heap.malloc(ChannelState.sizeof()),
            ringbuffer_addr = heap.malloc(256 * UnknownMsg.sizeof()),
            ringbuffer = [UnknownMsg()] * 256,
        )

        self.Return3 = Container(
            state_addr = heap.malloc(ChannelState.sizeof()),
            ringbuffer_addr = heap.malloc(256 * UnknownMsg.sizeof()),
            ringbuffer = [UnknownMsg()] * 256,
        )

    def __repr__(self):
        str = "Channels:\n"
        for name in channelNames:
            channel = getattr(self, name)
            str += f"   {name}: head:{channel.state.head} tail:{channel.state.tail} "
            str += f"ringbuffer: {channel.ringbuffer_addr:#x}\n"

        return str
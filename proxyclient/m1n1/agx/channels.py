# SPDX-License-Identifier: MIT

from construct import *
from ..fw.agx.channels import *
from ..fw.agx.cmdqueue import *

class GPUChannel:
    STATE_FIELDS = ChannelStateFields

    def __init__(self, agx, name, channel_id, state_addr, ring_addr, ring_size):
        self.agx = agx
        self.u = agx.u
        self.name = name
        self.channel_id = channel_id
        self.iface = agx.u.iface
        self.state_addr = state_addr
        self.ring_addr = ring_addr
        self.ring_size = ring_size
        self.state = self.STATE_FIELDS(self.u, self.state_addr)
        self.state.READ_PTR.val = 0
        self.state.WRITE_PTR.val = 0

    @classmethod
    @property
    def item_size(cls):
        return cls.MSG_CLASS.sizeof()

    def log(self, msg):
        self.agx.log(f"[{self.name}] {msg}")

class GPUTXChannel(GPUChannel):
    def doorbell(self):
        self.agx.asc.db.doorbell(self.channel_id)

    def send_message(self, msg):
        wptr = self.state.WRITE_PTR.val
        self.iface.writemem(self.ring_addr + self.item_size * wptr,
                            msg.build())
        self.state.WRITE_PTR.val = (wptr + 1) % self.ring_size
        self.doorbell()

class GPURXChannel(GPUChannel):
    def poll(self):
        wptr = self.state.WRITE_PTR.val
        rptr = self.state.READ_PTR.val

        if wptr >= self.ring_size:
            raise Exception(f"wptr = {wptr:#x} > {self.ring_size:#x}")

        while rptr != wptr:
            msg = self.iface.readmem(self.ring_addr + self.item_size * rptr,
                                     self.item_size)
            self.handle_message(self.MSG_CLASS.parse(msg))
            rptr = (rptr + 1) % self.ring_size
        self.state.READ_PTR.val = rptr

    def handle_message(self, msg):
        self.log(f"Message: {msg}")

class GPUCmdQueueChannel(GPUTXChannel):
    MSG_CLASS = RunCmdQueueMsg

    def run(self, queue, event):
        msg = RunCmdQueueMsg()
        msg.queue_type = queue.TYPE
        msg.cmdqueue = queue.info
        msg.cmdqueue_addr = queue.info._addr
        msg.head = queue.wptr
        msg.event_number = event
        msg.new_queue = 1 if queue.first_time else 0
        queue.first_time = False
        #print(msg)
        self.send_message(msg)

class GPUDeviceControlChannel(GPUTXChannel):
    MSG_CLASS = DeviceControlMsg

    def send_init(self):
        self.send_message(DC_Init())

    def dc_09(self, a, ptr, b):
        # Writes to InitData.RegionB
        msg = DC_09()
        msg.unk_4 = a
        msg.unkptr_c = ptr
        msg.unk_14 = b
        self.send_message(msg)

    def send_foo(self, t, d=None):
        msg = DC_Any()
        msg.msg_type = t
        if d is not None:
            msg.data = d
        self.send_message(msg)

    def update_idle_ts(self):
        self.send_message(DC_UpdateIdleTS())

    def destroy_context(self, ctx):
        msg = DC_DestroyContext()
        msg.unk_4 = 0
        msg.unk_8 = 2
        msg.unk_c = 0
        msg.unk_10 = 0
        msg.unk_14 = 0xffff
        msg.unk_18 = 0
        msg.context_addr = ctx.gpu_context._addr
        print(msg)
        self.send_message(msg)

    # Maybe related to stamps?
    def write32(self, addr, val):
        msg = DC_Write32()
        msg.addr = addr
        msg.data = val
        msg.unk_10 = 0
        msg.unk_14 = 0
        msg.unk_18 = 0
        msg.unk_1c = 0
        print(msg)
        self.send_message(msg)

    def dc_1e(self, a, b):
        msg = DC_1e()
        msg.unk_4 = a
        msg.unk_c = b
        print(msg)
        self.send_message(msg)

class GPUFWCtlChannel(GPUTXChannel):
    STATE_FIELDS = FWControlStateFields
    MSG_CLASS = FWCtlMsg

    def doorbell(self):
        self.agx.asc.db.fwctl_doorbell()

    def send_inval(self, ctx, addr=0):
        msg = FWCtlMsg()
        msg.addr = addr
        msg.unk_8 = 0
        msg.context_id = ctx
        msg.unk_10 = 1
        msg.unk_12 = 2
        print(msg)
        self.send_message(msg)

class GPUEventChannel(GPURXChannel):
    MSG_CLASS = EventMsg

    def handle_message(self, msg):
        if isinstance(msg, FlagMsg):
            self.agx.event_mgr.fired(msg.firing)
        elif isinstance(msg, FaultMsg):
            self.agx.faulted(msg)
        elif isinstance(msg, TimeoutMsg):
            self.agx.timeout(msg)
        else:
            self.log(f"Unknown event: {msg}")

class GPULogChannel(GPURXChannel):
    MSG_CLASS = FWLogMsg

    def handle_message(self, msg):
        ts = msg.timestamp / 24000000
        self.log(f"[{msg.seq_no:<4d}{ts:14.7f}] {msg.msg}")

class GPUKTraceChannel(GPURXChannel):
    MSG_CLASS = KTraceMsg

    def handle_message(self, msg):
        self.log(f"{msg}")

class GPUStatsChannel(GPURXChannel):
    MSG_CLASS = HexDump(Bytes(0x60))

    def handle_message(self, msg):
        if self.agx.show_stats:
            self.log(f"stat {msg}")

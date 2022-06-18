# SPDX-License-Identifier: MIT
from ..fw.agx.channels import *
from ..fw.agx.cmdqueue import *

class GPUChannel:
    def __init__(self, agx, name, channel_id, state_addr, ring_addr, ring_size):
        self.agx = agx
        self.u = agx.u
        self.name = name
        self.channel_id = channel_id
        self.iface = agx.u.iface
        self.state_addr = state_addr
        self.ring_addr = ring_addr
        self.ring_size = ring_size
        self.state = ChannelStateFields(self.u, self.state_addr)
        self.state.READ_PTR.val = 0
        self.state.WRITE_PTR.val = 0

    @classmethod
    @property
    def item_size(cls):
        return cls.MSG_CLASS.sizeof()

    def log(self, msg):
        self.agx.log(f"[{self.name}] {msg}")

class GPUTXChannel(GPUChannel):
    def send_message(self, msg):
        wptr = self.state.WRITE_PTR.val
        self.iface.writemem(self.ring_addr + self.item_size * wptr,
                            msg.build())
        self.state.WRITE_PTR.val = (wptr + 1) % self.ring_size
        self.agx.asc.db.doorbell(self.channel_id)

class GPURXChannel(GPUChannel):
    def poll(self):
        wptr = self.state.WRITE_PTR.val
        rptr = self.state.READ_PTR.val

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

    def send_dc19(self):
        self.send_message(DeviceControl_19())

    def send_dc23(self):
        self.send_message(DeviceControl_23())

class GPUEventChannel(GPURXChannel):
    MSG_CLASS = EventMsg

    def handle_message(self, msg):
        if isinstance(msg, FaultMsg):
            self.agx.faulted()
        else:
            self.log(f"Unknown event: {msg}")

class GPULogChannel(GPURXChannel):
    MSG_CLASS = FWLogMsg

    def handle_message(self, msg):
        ts = msg.timestamp / 24000000
        self.log(f"[{msg.seq_no:<4d}{ts:14.7f}] {msg.msg}")

class GPUKTraceChannel(GPURXChannel):
    MSG_CLASS = KTraceMsg

class GPUStatsChannel(GPURXChannel):
    MSG_CLASS = StatsMsg

    def handle_message(self, msg):
        # ignore
        #self.log(f"stat")
        pass

# SPDX-License-Identifier: MIT
from ..utils import chexdump
from ..malloc import Heap
from construct.core import *
from ..fw.agx.channels import *
from ..fw.agx.cmdqueue import *
from ..fw.agx.microsequence import *
from ..hw.uat import MemoryAttr
from .object import *
import textwrap

class GPUEventManager:
    MAX_EVENTS = 128

    def __init__(self, agx):
        self.agx = agx

        self.event_count = 0
        self.free_events = set(range(self.MAX_EVENTS))
        self.events = [None] * self.MAX_EVENTS

    def allocate_event(self):
        if not self.free_events:
            raise Exception("No free events")
        ev_id = self.free_events.pop()

        ev = GPUEvent(ev_id)
        self.events[ev_id] = ev

        return ev

    def free_event(self, ev):
        self.events[ev.id] = None
        self.free_events.add(ev.id)

    def fired(self, flags):
        self.agx.log("= Events fired =")
        for i, v in enumerate(flags):
            for j in range(64):
                if v & (1 << j):
                    ev_id = i * 64 + j
                    ev = self.events[ev_id]
                    self.agx.log(f"Event fired: {ev_id}")
                    if ev is None:
                        raise Exception("Received spurious notification for event ID {ev}")
                    ev.fire()
                    self.event_count += 1

class GPUEvent:
    def __init__(self, ev_id):
        self.id = ev_id
        self.fired = False

    def fire(self):
        self.fired = True

    def rearm(self):
        self.fired = False

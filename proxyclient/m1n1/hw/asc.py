# SPDX-License-Identifier: MIT
from ..utils import *
import time

class R_OUTBOX_CTRL(Register32):
    EMPTY = 17
    FULL  = 16

class R_INBOX_CTRL(Register32):
    EMPTY = 17
    FULL  = 16
    ENABLE = 1

class R_CPU_CONTROL(Register32):
    RUN    = 4

class R_INBOX1(Register64):
    EP      = 7, 0

class R_OUTBOX1(Register64):
    OUTCNT  = 56, 52
    INCNT   = 51, 48
    OUTPTR  = 47, 44
    INPTR   = 43, 40
    EP      = 7, 0

class ASCRegs(RegMap):
    CPU_CONTROL = 0x0044, R_CPU_CONTROL
    CPU_STATUS  = 0x0048, Register32

    INBOX_CTRL  = 0x8110, R_INBOX_CTRL
    OUTBOX_CTRL = 0x8114, R_OUTBOX_CTRL
    INBOX0      = 0x8800, Register64
    INBOX1      = 0x8808, R_INBOX1
    OUTBOX0     = 0x8830, Register64
    OUTBOX1     = 0x8838, R_OUTBOX1

    NMI1        = 0x10004, Register32
    NMI2        = 0x10024, Register32

class ASC:
    def __init__(self, u, asc_base):
        self.u = u
        self.p = u.proxy
        self.iface = u.iface
        self.asc = ASCRegs(u, asc_base)
        self.verbose = 0
        self.epmap = {}

    def send_nmi(self):
        print("send nmi")
        #self.asc.NMI1.val = 0x11
        #self.asc.NMI2.val = 0x1

    def get_status(self):
        return self.asc.CPU_STATUS.val

    def recv(self):
        if self.asc.OUTBOX_CTRL.reg.EMPTY:
            return None, None

        msg0 = self.asc.OUTBOX0.val
        msg1 = R_INBOX1(self.asc.OUTBOX1.val)
        if self.verbose >= 3:
            print(f"< {msg1.EP:02x}:{msg0:#x}")
        return msg0, msg1

    def send(self, msg0, msg1):
        self.asc.INBOX0.val = msg0
        self.asc.INBOX1.val = msg1

        if self.verbose >= 3:
            if isinstance(msg0, Register):
                print(f"> {msg1.EP:02x}:{msg0}")
            else:
                print(f"> {msg1.EP:02x}:{msg0:#x}")

        while self.asc.INBOX_CTRL.reg.FULL:
            pass

    def boot(self):
        #self.send_nmi()
        self.asc.CPU_CONTROL.set(RUN=1)
        self.asc.CPU_CONTROL.set(RUN=0)

    def add_ep(self, idx, ep):
        self.epmap[idx] = ep
        setattr(self, ep.SHORT, ep)

    def work(self):
        if self.asc.OUTBOX_CTRL.reg.EMPTY:
            return True

        msg0, msg1 = self.recv()

        handled = False

        ep = self.epmap.get(msg1.EP, None)
        if ep:
            handled = ep.handle_msg(msg0, msg1)

        if not handled:
            print(f"unknown message: {msg0:#16x} / {msg1}")

        return handled

    def work_forever(self):
        while self.work():
            pass

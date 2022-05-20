# SPDX-License-Identifier: MIT
import time

from .base import *
from ...utils import *

## Management endpoint
class ManagementMessage(Register64):
    TYPE    = 59, 52

class Mgmt_Hello(ManagementMessage):
    TYPE    = 59, 52, Constant(1)
    MAX_VER = 31, 16
    MIN_VER = 15, 0

class Mgmt_HelloAck(ManagementMessage):
    TYPE    = 59, 52, Constant(2)
    MAX_VER = 31, 16
    MIN_VER = 15, 0

class Mgmt_Ping(ManagementMessage):
    TYPE    = 59, 52, Constant(3)

class Mgmt_Pong(ManagementMessage):
    TYPE    = 59, 52, Constant(4)

class Mgmt_StartEP(ManagementMessage):
    TYPE    = 59, 52, Constant(5)
    EP      = 39, 32
    FLAG    = 1, 0

class Mgmt_SetIOPPower(ManagementMessage):
    TYPE    = 59, 52, Constant(6)
    STATE   = 15, 0

class Mgmt_IOPPowerAck(ManagementMessage):
    TYPE    = 59, 52, Constant(7)
    STATE   = 15, 0

class Mgmt_EPMap(ManagementMessage):
    TYPE    = 59, 52, Constant(8)
    LAST    = 51
    BASE    = 34, 32
    BITMAP  = 31, 0

class Mgmt_EPMap_Ack(ManagementMessage):
    TYPE    = 59, 52, Constant(8)
    LAST    = 51
    BASE    = 34, 32
    MORE    = 0

class Mgmt_SetAPPower(ManagementMessage):
    TYPE    = 59, 52, Constant(0xb)
    STATE   = 15, 0

class ASCManagementEndpoint(ASCBaseEndpoint):
    BASE_MESSAGE = ManagementMessage
    SHORT = "mgmt"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.syslog_started = False
        self.iop_power_state = 0
        self.ap_power_state = 0
        self.verbose = 1

    @msg_handler(1, Mgmt_Hello)
    def Hello(self, msg):
        self.log(f"Supported versions {msg.MIN_VER} .. {msg.MAX_VER}")
        # FIXME: we pick the highest version, we should negotiate
        self.send(Mgmt_HelloAck(MIN_VER=msg.MAX_VER, MAX_VER=msg.MAX_VER))
        return True

    @msg_handler(8, Mgmt_EPMap)
    def EPMap(self, msg):
        for i in range(32):
            if msg.BITMAP & (1 << i):
                epno = 32 * msg.BASE + i
                self.asc.eps.append(epno)
                if self.verbose > 0:
                    self.log(f"Adding endpoint {epno:#x}")

        self.send(Mgmt_EPMap_Ack(BASE=msg.BASE, LAST=msg.LAST, MORE=0 if msg.LAST else 1))

        if msg.LAST:
            for ep in self.asc.eps:
                if ep == 0: continue
                if ep < 0x10:
                    self.asc.start_ep(ep)
            self.boot_done()

        return True

    @msg_handler(0xb, Mgmt_SetAPPower)
    def APPowerAck(self, msg):
        if self.verbose > 0:
            self.log(f"AP power state is now {msg.STATE:#x}")
        self.ap_power_state = msg.STATE
        return True

    @msg_handler(7, Mgmt_IOPPowerAck)
    def IOPPowerAck(self, msg):
        if self.verbose > 0:
            self.log(f"IOP power state is now {msg.STATE:#x}")
        self.iop_power_state = msg.STATE
        return True

    @msg_handler(4, Mgmt_Pong)
    def Pong(self, msg):
        return True

    def start(self):
        self.log("Starting via message")
        self.send(Mgmt_SetIOPPower(STATE=0x220))

    def wait_boot(self, timeout=None):
        if timeout is not None:
            timeout += time.time()
        while self.iop_power_state != 0x20 or self.ap_power_state != 0x20:
            self.asc.work()
            if timeout and time.time() > timeout:
                raise ASCTimeout("Boot timed out")
        self.log("Startup complete")

    def start_ep(self, epno):
        self.send(Mgmt_StartEP(EP=epno, FLAG=2))

    def stop_ep(self, epno):
        self.send(Mgmt_StartEP(EP=epno, FLAG=1))

    def boot_done(self):
        self.send(Mgmt_SetAPPower(STATE=0x20))

    def ping(self):
        self.send(Mgmt_Ping())

    def stop(self, state=0x10):
        self.log("Stopping via message")
        self.send(Mgmt_SetAPPower(STATE=0x10))
        while self.ap_power_state == 0x20:
            self.asc.work()
        self.send(Mgmt_SetIOPPower(STATE=state))
        while self.iop_power_state != state:
            self.asc.work()

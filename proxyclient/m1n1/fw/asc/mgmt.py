# SPDX-License-Identifier: MIT
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
    FLAG    = 1

class Mgmt_Init(ManagementMessage):
    TYPE    = 59, 52, Constant(6)
    UNK     = 15, 0

class Mgmt_BootDone(ManagementMessage):
    TYPE    = 59, 52, Constant(7)

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

class Mgmt_StartSyslog(ManagementMessage):
    TYPE    = 59, 52, Constant(0xb)
    UNK1    = 15, 0

class ASCManagementEndpoint(ASCBaseEndpoint):
    BASE_MESSAGE = ManagementMessage
    SHORT = "mgmt"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.syslog_started = False
        self.boot_done = False

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
                self.log(f"Adding endpoint {epno:#x}")

        self.send(Mgmt_EPMap_Ack(BASE=msg.BASE, LAST=msg.LAST, MORE=0 if msg.LAST else 1))

        if msg.LAST:
            for ep in self.asc.eps:
                if ep == 0: continue
                if ep < 0x10:
                    self.asc.start_ep(ep)

        return True

    @msg_handler(0xb, Mgmt_StartSyslog)
    def StartSyslogAck(self, msg):
        self.syslog_started = True
        return True

    @msg_handler(7, Mgmt_BootDone)
    def BootDone(self, msg):
        #self.start_syslog()
        self.boot_done = True
        return True

    @msg_handler(4, Mgmt_Pong)
    def Pong(self, msg):
        return True

    def start(self):
        self.send(Mgmt_Init(UNK=0x220))
        while not self.boot_done or not self.syslog_started:
            self.asc.work()
        self.log("startup complete")

    def start_ep(self, epno):
        self.send(Mgmt_StartEP(EP=epno, FLAG=1))

    def start_syslog(self):
        self.send(Mgmt_StartSyslog(UNK1=0x20))

    def ping(self):
        self.send(Mgmt_Ping())

# SPDX-License-Identifier: MIT
from construct import *

from ...utils import *
from ..asc import StandardASC
from ..afk.epic import *

class DCPAVControllerService(EPICService):
    NAME = "dcpav-controller-epic"
    SHORT = "controller"

    def send_cmd(self, group, cmd, data=b'', replen=None):
        msg = struct.pack("<2xHIII48x", group, cmd, len(data), 0x69706378) + data
        if replen is not None:
            replen += 64
        resp = super().send_cmd(0xc0, msg, replen)
        if not resp:
            return
        rgroup, rcmd, rlen, rmagic = struct.unpack("<2xHIII", resp[:16])
        assert rmagic == 0x69706378
        assert rgroup == group
        assert rcmd == cmd
        return resp[64:64+rlen]

    def open(self, unk=0):
        self.send_cmd(8, 0x6, struct.pack("<16xI12x", unk))

    def close(self):
        self.send_cmd(8, 0x7, bytes(16))

    def setPower(self, power):
        self.send_cmd(8, 0x8, struct.pack("<16xI12x", power))

    def getPower(self, power):
        return struct.unpack("<16xI12x", self.send_cmd(8, 0x9, bytes(32)))

    def wakeDisplay(self):
        self.send_cmd(8, 0xa, bytes(16))

    def sleepDisplay(self):
        self.send_cmd(8, 0xb, bytes(16))

    def forceHotPlugDetect(self):
        self.send_cmd(8, 0xc, bytes(16))

    def setVirtualDeviceMode(self, mode):
        self.send_cmd(8, 0xd, struct.pack("<16xI12x", mode))

class DCPAVEndpoint(EPICEndpoint):
    SHORT = "dcpav"

    SERVICES = [
        DCPAVControllerService,
    ]


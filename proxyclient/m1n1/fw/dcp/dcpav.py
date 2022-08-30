# SPDX-License-Identifier: MIT
from construct import *

from ...utils import *
from ..asc import StandardASC
from ..afk.epic import *

class DCPAVControllerService(EPICStandardService):
    NAME = "dcpav-controller-epic"
    SHORT = "dcpav"

    def setPower(self, power):
        self.call(8, 0x8, struct.pack("<16xI12x", power))

    def getPower(self, power):
        return struct.unpack("<16xI12x", self.call(8, 0x9, bytes(32)))

    def wakeDisplay(self):
        self.call(8, 0xa, bytes(16))

    def sleepDisplay(self):
        self.call(8, 0xb, bytes(16))

    def forceHotPlugDetect(self):
        self.call(8, 0xc, bytes(16))

    def setVirtualDeviceMode(self, mode):
        self.call(8, 0xd, struct.pack("<16xI12x", mode))

class DCPDPControllerService(EPICStandardService):
    NAME = "dcpdp-controller-epic"
    SHORT = "dcpdp"

class DCPDPTXEndpoint(EPICEndpoint):
    SHORT = "dptx"

    SERVICES = [
        DCPAVControllerService,
        DCPDPControllerService,
    ]

ATC0 = 0
ATC1 = 1
ATC2 = 2
ATC3 = 3
LPDPTX = 4
DPTX = 5

DPPHY = 0
DPIN0 = 1
DPIN1 = 2

class DCPDPTXRemotePortService(EPICStandardService):
    NAME = "dcpdptx-port-epic"
    SHORT = "port"

    def displayRequest(self):
        self.call(8, 8, bytes(16))

    def displayRelease(self):
        self.call(8, 9, bytes(16))

    def connectTo(self, connected, unit, port, unk=0):
        target = 0
        if connected:
            target |= (1 << 8)
        target |= unit
        target |= port << 4
        self.call(8, 13, struct.pack("<16xII8x", unk, target))

class DCPDPTXPortEndpoint(EPICEndpoint):
    SHORT = "dpport"

    SERVICES = [
        DCPDPTXRemotePortService,
        DCPDPControllerService,
    ]

class DCPDPDevice(EPICStandardService):
    NAME = "dcpav-device-epic"
    SHORT = "dpdev"

class DCPAVDeviceEndpoint(EPICEndpoint):
    SHORT = "avdev"

    SERVICES = [
        DCPDPDevice,
    ]

class DCPDPService(EPICStandardService):
    NAME = "dcpav-service-epic"
    SHORT = "dpserv"

class DCPAVServiceEndpoint(EPICEndpoint):
    SHORT = "avserv"

    SERVICES = [
        DCPDPService,
    ]

class DCPAVSimpleVideoInterface(EPICStandardService):
    NAME = "dcpav-video-interface-epic"
    SHORT = "video"

class DCPAVVideoEndpoint(EPICEndpoint):
    SHORT = "avserv"

    SERVICES = [
        DCPAVSimpleVideoInterface,
    ]

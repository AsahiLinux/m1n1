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
        self.call(0, 6, bytes(16))

    def displayRelease(self):
        self.call(0, 7, bytes(16))

    def connectTo(self, connected, unit, port, unk=0):
        target = 0
        if connected:
            target |= (1 << 8)
        target |= unit
        target |= port << 4
        self.call(0, 11, struct.pack("<II8x16x", unk, target))

    def handle_notify(self, category, type, seq, fd):
        retcode = struct.unpack("<I", fd.read(4))[0]
        self.log(f"Notify {category}/{type} #{seq} ({retcode})")
        data = fd.read()
        chexdump(data)
        print("Send ACK")

        group, code, length = struct.unpack("<III", data[:12])

        arg = None
        if len(data) >= 0x54:
            arg = struct.unpack("<I", data[0x50:0x54])[0]

        if code == 0x12:
            # DPTX_APCALL_GET_SUPPORTS_HPD
            pass
        elif code == 0x0a:
            # DPTX_APCALL_GET_MAX_LANE_COUNT
            data = data[:0x50] + b"\x04\x00\x00\x00" + data[0x54:]
        elif code == 0x00:
            # DPTX_APCALL_ACTIVATE
            self.phy.activate()
        elif code == 0x07:
            # DPTX_APCALL_GET_MAX_LINK_RATE
            data = data[:0x50] + b"\x1e\x00\x00\x00" + data[0x54:]
        elif code == 0x0c:
            # DPTX_APCALL_SET_ACTIVE_LANE_COUNT
            self.phy.set_active_lane_count(arg)
        elif code == 0x09:
            # DPTX_APCALL_SET_LINK_RATE
            self.phy.set_link_rate()
        elif code == 0x02:
            # DPTX_APCALL_GET_MAX_DRIVE_SETTINGS
            data = data[:0x50] + b"\x03\x00\x00\x00\x03\x00\x00\x00" + data[0x58:]
        elif code == 0x03:
            # DPTX_APCALL_SET_DRIVE_SETTINGS
            # clear err code
            data = data[:0x40] + b"\x00\x00\x00\x00" + data[0x44:]

        pkt = struct.pack("<I", 0) + data

        chexdump(pkt)
        self.ep.send_epic(self.chan, EPICType.NOTIFY_ACK, EPICCategory.REPLY, type, seq, pkt, len(data))

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

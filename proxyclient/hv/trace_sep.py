# SPDX-License-Identifier: MIT

import struct

from enum import IntEnum

from m1n1.proxyutils import RegMonitor
from m1n1.utils import *
from m1n1.trace.dart import DARTTracer
from m1n1.trace.asc import BaseASCTracer, ASCTracer, EP, EPState, msg, msg_log, DIR

trace_device("/arm-io/sep", True, ranges=[1])

DARTTracer = DARTTracer._reloadcls()
ASCTracer = ASCTracer._reloadcls()

iomon = RegMonitor(hv.u, ascii=True)


class SEPMessage(Register64):
    EP = 7, 0
    TAG = 15, 8
    TYPE = 23, 16
    PARAM = 31, 24
    DATA = 63, 32


class SEPEP(EP):
    BASE_MESSAGE = SEPMessage

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)
        self.state.shmem_in_iova = None
        self.state.shmem_in_sz = 0
        self.state.shmem_out_iova = None
        self.state.shmem_out_sz = 0
        self.state.name = self.name
        self.monitor_in = False
        self.monitor_out = False

    def start(self):
        if self.state.name in self.tracer.ignorelist:
            return
        if self.state.shmem_in_iova:
            iomon.add(self.state.shmem_in_iova, self.state.shmem_in_sz,
                      name=f"{self.state.name}.shmem_in@{self.state.shmem_in_iova}", offset=0)
            self.monitor_in = True
        if self.state.shmem_out_iova:
            iomon.add(self.state.shmem_out_iova, self.state.shmem_out_sz,
                      name=f"{self.state.name}.shmem_out@{self.state.shmem_out_iova}", offset=0)
            self.monitor_out = True

    def update_shmem_in_iova(self, iova):
        if self.state.shmem_in_iova == iova:
            return
        if self.monitor_in:
            iomon.remove(
                f"{self.state.name}.shmem_in@{self.state.shmem_in_iova}")
        self.state.shmem_in_iova = iova

        if self.state.name in self.tracer.ignorelist:
            return
        iomon.add(self.state.shmem_in_iova, self.state.shmem_in_sz,
                  name=f"{self.state.name}.shmem_in@{self.state.shmem_in_iova}", offset=0)
        self.monitor_in = True

    def update_shmem_out_iova(self, iova):
        if self.state.shmem_out_iova == iova:
            return
        if self.monitor_out:
            iomon.remove(
                f"{self.state.name}.shmem_out@{self.state.shmem_out_iova}")
        self.state.shmem_out_iova = iova

        if self.state.name in self.tracer.ignorelist:
            return
        iomon.add(self.state.shmem_out_iova, self.state.shmem_out_sz,
                  name=f"{self.state.name}.shmem_out@{self.state.shmem_out_iova}", offset=0)
        self.monitor_out = True

    def log(self, msg):
        if self.state.name in self.tracer.ignorelist:
            return
        self.tracer.log(f"[{self.state.name}] {msg}")
        iomon.poll()


class Management(SEPEP):
    @msg(2, DIR.TX)
    def SetInAddr(self, msg):
        iova = msg.DATA << 0xc
        ep = msg.PARAM
        self.log(f"SetInAddr(ep={ep:x}, iova={iova:x})")
        if ep in self.tracer.epmap:
            self.tracer.epmap[ep].update_shmem_in_iova(iova)
        return True

    @msg(3, DIR.TX)
    def SetOutAddr(self, msg):
        iova = msg.DATA << 0xc
        ep = msg.PARAM
        self.log(f"SetOutAddr(ep={ep:x}, iova={iova:x})")
        if ep in self.tracer.epmap:
            self.tracer.epmap[ep].update_shmem_out_iova(iova)
        return True

    @msg(4, DIR.TX)
    def SetInLen(self, msg):
        ep = msg.PARAM
        sz = msg.DATA
        self.log(f"SetInLen(ep={ep:x}, len={sz:x})")
        if ep in self.tracer.epmap:
            self.tracer.epmap[ep].state.shmem_in_sz = sz
        return True

    @msg(5, DIR.TX)
    def SetOutLen(self, msg):
        ep = msg.PARAM
        sz = msg.DATA
        self.log(f"SetOutLen(ep={ep:x}, len={sz:x})")
        if ep in self.tracer.epmap:
            self.tracer.epmap[ep].state.shmem_out_sz = sz
        return True


class Debug(SEPEP):
    @msg(0, DIR.RX)
    def Log_SetEPName(self, msg):
        a = (msg.DATA >> 24) & 0xff
        b = (msg.DATA >> 16) & 0xff
        c = (msg.DATA >> 8) & 0xff
        d = msg.DATA & 0xff
        ep = msg.PARAM
        epname = "%c%c%c%c" % (a, b, c, d)
        self.log("< SetEPName: 0x%x: %s" % (msg.PARAM, epname))
        if ep in self.tracer.epmap:
            self.tracer.epmap[ep].state.name = epname.strip()
        return True


class Boot254(SEPEP):
    @msg(0x18, DIR.TX)
    def Log_SendScratchMem(self, msg):
        self.log(f"> SendScratchMem: %08x" % (msg.DATA << 0xc))
        iomon.add((msg.DATA << 0xc), 0x30000,
                  name=f"shmem@{(msg.DATA<<0xc):x}", offset=0)
        iomon.poll()
        return True


class Boot255(SEPEP):
    @msg(2, DIR.TX)
    def Log_Ping(self, msg):
        self.log("> Ping")
        return True

    @msg(102, DIR.RX)
    def Log_Pong(self, msg):
        self.log("< Pong")
        return True

    @msg(105, DIR.RX)
    def Log_BootTZ0Done(self, msg):
        self.log("< BootTZ0Done")
        return True

    @msg(106, DIR.RX)
    def Log_BootDone(self, msg):
        self.log("< BootDone")
        return True

    @msg(0xd2, DIR.RX)
    def Log_UnkDone(self, msg):
        self.log("< UnkDone")
        return True

    @msg(5, DIR.TX)
    def Log_BootTZ0(self, msg):
        self.log("> BootTZ0")
        return True

    @msg(6, DIR.TX)
    def Log_SendIMG4(self, msg):
        self.log(f"> SendIMG4: %08x" % (msg.DATA << 0xc))
        return True


class SEPTracer(BaseASCTracer):
    ENDPOINTS = {
        0: Management,
        0x8: SEPEP,
        0xa: SEPEP,
        0xc: SEPEP,
        0xe: SEPEP,
        0xf: SEPEP,
        0x10: SEPEP,
        0x12: SEPEP,
        0x13: SEPEP,
        0x14: SEPEP,
        0x15: SEPEP,
        0x17: SEPEP,
        0x18: SEPEP,
        0xfd: Debug,
        0xfe: Boot254,
        0xff: Boot255,
    }

    def __init__(self, hv, devpath, ignorelist=None, verbose=False):
        super().__init__(hv, devpath, verbose=verbose)
        self.ignorelist = set(ignorelist) if ignorelist else set()

    def start(self, dart=None):
        super().start(dart=dart)

    def handle_msg(self, direction, r0, r1):
        sepmsg = SEPMessage(r0.value)
        if sepmsg.EP in self.epmap:
            if self.epmap[sepmsg.EP].handle_msg(direction, r0, r1):
                return
        d = ">" if direction == DIR.TX else "<"
        self.log(
            f"{d}{sepmsg.EP:02x} {sepmsg.value:016x} ({sepmsg.str_fields()})")


dart_sep_tracer = DARTTracer(hv, "/arm-io/dart-sep")
dart_sep_tracer.start()


def readmem_iova(addr, size):
    try:
        return dart_sep_tracer.dart.ioread(0, addr, size)
    except Exception as e:
        print(e)
        return None


iomon.readmem = readmem_iova

sep_tracer = SEPTracer(hv, "/arm-io/sep", verbose=1, ignorelist={"hdcp"})
sep_tracer.start(dart_sep_tracer.dart)

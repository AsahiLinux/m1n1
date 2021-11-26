# SPDX-License-Identifier: MIT
import struct
from collections import defaultdict, deque
from enum import IntEnum

from ..trace.asc import ASCRegs
from ..utils import *


class BootRomMsg(IntEnum):
    GET_STATUS = 2
    BOOT_TZ0 = 5
    BOOT_IMG4 = 6
    SET_SHMEM = 0x18


class BootRomStatus(IntEnum):
    STATUS_OK = 0x66
    STATUS_BOOT_TZ0_DONE = 0x69
    STATUS_BOOT_IMG4_DONE = 0x6A
    STATUS_BOOT_UNK_DONE = 0xD2


class SEPMessage(Register64):
    EP = 7, 0
    TAG = 15, 8
    TYPE = 23, 16
    PARAM = 31, 24
    DATA = 63, 32


# TODO: make this class actually own the shared memory instead of just
#       generating a static buffer if we actually need to read/write to
#       individual items inside the shmem buffer
class SEPShMem:
    def __init__(self):
        self.items = []
        self.offset = 0x4000

    def add_item(self, name, data, min_size=0):
        sz = align_up(len(data) + 4, 0x4000)
        sz = max(sz, min_size)
        self.items.append((name, self.offset, sz, struct.pack("<I", len(data)) + data))
        self.offset += sz

    def finalize(self):
        bfr = bytearray(b"\x00" * self.offset)
        for i, (name, offset, sz, data) in enumerate(self.items):
            bfr[i * 16 : i * 16 + 12] = struct.pack("<4sII", name, sz, offset)
            bfr[offset : offset + len(data)] = data

        cnt = len(self.items)
        bfr[cnt * 16 : cnt * 16 + 4] = b"llun" # null

        return bfr


class SEP:
    SHMEM_IOVA = 0xBEEF0000
    FW_IOVA = 0xDEAD0000

    def __init__(self, proxy, iface, utils):
        self.i = iface
        self.p = proxy
        self.u = utils

        self.sep_base = self.u.adt["/arm-io/sep"].get_reg(0)[0]
        self.dart_base = self.u.adt["/arm-io/dart-sep"].get_reg(0)[0]

        self.asc = ASCRegs(self.u, self.sep_base)

        self.dart_handle = self.p.dart_init(self.dart_base, 0)

        self.epnum2name = {}
        self.epname2num = {}
        self.msgs = defaultdict(deque)

    def map_sepfw(self):
        sepfw_addr, sepfw_size = self.u.adt["/chosen/memory-map"].SEPFW
        self.p.dart_map(self.dart_handle, self.FW_IOVA, sepfw_addr, sepfw_size)

    def unmap_sepfw(self):
        _, sepfw_size = self.u.adt["/chosen/memory-map"].SEPFW
        self.p.dart_unmap(self.dart_handle, self.FW_IOVA, sepfw_size)

    def create_shmem(self):
        shmem = SEPShMem()

        # PNIC - panic buffer
        shmem.add_item(b"CINP", b"\x00", 0x8000)

        # ALPO / SIPS - unknown img4-like blobs from the ADT
        addr, sz = self.u.adt["/chosen/boot-object-manifests"].lpol
        shmem.add_item(b"OPLA", self.i.readmem(addr, sz))
        addr, sz = self.u.adt["/chosen/boot-object-manifests"].ibot
        shmem.add_item(b"IPIS", self.i.readmem(addr, sz))

        bfr = shmem.finalize()
        sz = align_up(len(bfr), 0x4000)
        self.shmem = self.u.heap.memalign(0x4000, 0x30000)
        self.i.writemem(self.shmem, bfr)
        self.p.dart_map(self.dart_handle, self.SHMEM_IOVA, self.shmem, 0x30000)

    def boot(self):
        self.create_shmem()
        self.map_sepfw()

        self.send_msg(SEPMessage(EP=0xFF, TYPE=BootRomMsg.GET_STATUS))
        self.expect_msg(0xFF, BootRomStatus.STATUS_OK)

        self.send_msg(SEPMessage(EP=0xFF, TYPE=BootRomMsg.BOOT_TZ0))
        self.expect_msg(0xFF, BootRomStatus.STATUS_BOOT_TZ0_DONE)
        self.expect_msg(0xFF, BootRomStatus.STATUS_BOOT_UNK_DONE)

        self.send_msg(SEPMessage(EP=0xFF, TYPE=BootRomMsg.GET_STATUS))
        self.expect_msg(0xFF, BootRomStatus.STATUS_OK)

        self.send_msg(
            SEPMessage(EP=0xFF, TYPE=BootRomMsg.BOOT_IMG4, DATA=self.FW_IOVA >> 0xC)
        )
        self.send_msg(
            SEPMessage(EP=0xFE, TYPE=BootRomMsg.SET_SHMEM, DATA=self.SHMEM_IOVA >> 0xC)
        )

        self.expect_msg(0xFF, BootRomStatus.STATUS_BOOT_IMG4_DONE)

        self.unmap_sepfw()

    def expect_msg(self, ep, type):
        msg = self.recv_msg(ep, block=True)
        if msg.TYPE != type:
            raise ValueError(
                f"Expected type 0x{type:x} but got message with type 0x{msg.TYPE:x}"
            )

    def send_msg(self, msg):
        self.asc.INBOX0 = msg.value
        self.asc.INBOX1 = 0

    def _recv_single_msg(self):
        msg = SEPMessage(self.asc.OUTBOX0.val)
        _ = self.asc.OUTBOX1.val
        return msg

    def _try_recv_msgs(self):
        while not self.asc.OUTBOX_CTRL.reg.EMPTY:
            msg = self._recv_single_msg()
            self.msgs[msg.EP].append(msg)
        self._handle_ep_discovery()

    def _handle_ep_discovery(self):
        while len(self.msgs[0xFD]):
            msg = self.msgs[0xFD].popleft()
            if msg.TYPE == 0:
                cs = "".join(
                    [chr((msg.DATA >> (i * 8)) & 0xFF) for i in range(3, -1, -1)]
                )
                self.epnum2name[msg.PARAM] = cs
                self.epname2num[cs] = msg.PARAM

    def recv_msg(self, ep, block=False):
        self._try_recv_msgs()
        while block and len(self.msgs[ep]) < 1:
            self._try_recv_msgs()

        if len(self.msgs[ep]):
            return self.msgs[ep].popleft()
        else:
            return None

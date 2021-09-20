# SPDX-License-Identifier: MIT
import struct

from ..utils import *

from .asc import StandardASC
from .asc.base import *

class PMPMessage(Register64):
    TYPE = 56, 44

class PMP_Startup(PMPMessage):
    TYPE = 56, 44, Constant(0x00)

class PMP_Configure(PMPMessage):
    TYPE = 56, 44, Constant(0x10)
    DVA = 47, 0

class PMP_Configure_Ack(PMPMessage):
    TYPE = 56, 44, Constant(0x20)
    UNK = 47, 0

class PMP_Init1(PMPMessage):
    TYPE = 56, 44, Constant(0x200)
    UNK1 = 43, 16
    UNK2 = 15, 0

class PMP_Init1_Ack(PMPMessage):
    TYPE = 56, 44, Constant(0x201)
    UNK1 = 43, 16
    UNK2 = 15, 0

class PMP_Init2(PMPMessage):
    TYPE = 56, 44, Constant(0x202)
    UNK1 = 43, 16
    UNK2 = 15, 0

class PMP_Init2_Ack(PMPMessage):
    TYPE = 56, 44, Constant(0x203)
    UNK1 = 43, 16
    UNK2 = 15, 0
    
class PMP_Unk(PMPMessage):
    TYPE = 56, 44, Constant(0x100)
    UNK1 = 43, 16
    UNK2 = 15, 0

class PMP_Unk_Ack(PMPMessage):
    TYPE = 56, 44, Constant(0x110)
    UNK1 = 43, 16
    UNK2 = 15, 0

class PMP_DevPwr(PMPMessage):
    TYPE = 56, 44, Constant(0x20e)
    DEV = 31, 16
    STATE = 15, 0

class PMP_DevPwr_Sync(PMPMessage):
    TYPE = 56, 44, Constant(0x208)
    DEV = 31, 16
    STATE = 15, 0

class PMP_DevPwr_Ack(PMPMessage):
    TYPE = 56, 44, Constant(0x209)
    DEV = 31, 16
    STATE = 15, 0

class PMPEndpoint(ASCBaseEndpoint):
    BASE_MESSAGE = PMPMessage
    SHORT = "pmpep"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shmem = self.shmem_dva = None
        self.init_complete = False
        self.init1_acked = False
        self.init2_acked = False
        self.unk_acked = False

    @msg_handler(0x00, PMP_Startup)
    def Startup(self, msg):
        self.log("Starting up")

        self.shmem, self.shmem_dva = self.asc.ioalloc(0x10000)
        
        self.send_init_config()
        return True

    def send_init_config(self):
        self.asc.p.memset32(self.shmem, 0, 0x10000)
        dram_config = self.asc.u.adt["arm-io/pmp/iop-pmp-nub"].energy_model_dram_configs
        self.asc.iface.writemem(self.shmem + 0x2000, dram_config)
        
        node = self.asc.u.adt["arm-io/pmp"]
        
        maps = []
        dva = 0xc0000000
        for i in range(3, len(node.reg)):
            addr, size = node.get_reg(i)
            if size == 0:
                maps.append(struct.pack("<QQ", 0, 0))
                continue

            self.asc.dart.iomap_at(0, dva, addr, size)
            self.log(f"map {addr:#x} -> {dva:#x} [{size:#x}]")
            maps.append(struct.pack("<QQ", dva, size))
            dva += align(size, 0x4000)

        chexdump(b"".join(maps))

        self.asc.iface.writemem(self.shmem + 0xe000, b"".join(maps))
        self.send(PMP_Configure(DVA=self.shmem_dva))

        while not self.init_complete:
            self.asc.work()
        return True

    @msg_handler(0x20, PMP_Configure_Ack)
    def Configure_Ack(self, msg):
        self.init_complete = True

        props = self.asc.iface.readmem(self.shmem, 0x2000)
        devinfo = self.asc.iface.readmem(self.shmem + 0x4000, 0x1000)
        status = self.asc.iface.readmem(self.shmem + 0xc000, 0x100)

        print("PMP Props:")
        chexdump(props)
        print("PMP Device Info:")
        chexdump(devinfo)
        print("PMP Status:")
        chexdump(status)

        self.send(PMP_Init1(UNK1=1, UNK2=3))
        while not self.init1_acked:
            self.asc.work()

        self.send(PMP_Init2(UNK1=1, UNK2=0))
        while not self.init2_acked:
            self.asc.work()

        self.send(PMP_Unk(UNK1=0x3bc, UNK2=2))
        while not self.unk_acked:
            self.asc.work()

        return True

    @msg_handler(0x201, PMP_Init1_Ack)
    def Init1_Ack(self, msg):
        self.init1_acked = True
        return True

    @msg_handler(0x203, PMP_Init2_Ack)
    def Init2_Ack(self, msg):
        self.init2_acked = True
        return True

    @msg_handler(0x110, PMP_Unk_Ack)
    def Unk_Ack(self, msg):
        self.unk_acked = True
        return True


class PMPClient(StandardASC):
    pass

    ENDPOINTS = {
        0x20: PMPEndpoint,
    }

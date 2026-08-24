import struct

from m1n1.utils import *

from m1n1.fw.asc import StandardASC
from m1n1.fw.asc.base import *

from m1n1.shell import run_shell
import struct

from m1n1.hw.dart import DART

class PMPMessage(Register64):
    TYPE = 56, 44

class PMP_Startup(PMPMessage):
    TYPE = 56, 44, Constant(0x00)

class PMP_Configure(PMPMessage):
    TYPE = 56, 44, Constant(0x10)
    DVA = 43, 0

class PMP_Configure_Ack(PMPMessage):
    TYPE = 56, 44, Constant(0x20)
    UNK = 43, 0

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

# presumed change state
class PMP_ChangeState1(PMPMessage):
    TYPE = 56, 44, Constant(0x20c)
    DEV = 31, 16
    STATE = 15, 0

class PMP_ChangeState1_Ack(PMPMessage):
    TYPE = 56, 44, Constant(0x20d)
    DEV = 31, 16
    STATE = 15, 0

class PMP_ChangeState2(PMPMessage):
    TYPE = 56, 44, Constant(0x20a)
    DEV = 31, 16
    STATE = 15, 0

class PMP_ChangeState2_Ack(PMPMessage):
    TYPE = 56, 44, Constant(0x20b)
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
        self.devpwr_acked = False
        self.unk2_acked = False

        self.unk3_acked = False

    @msg_handler(0x00, PMP_Startup)
    def Startup(self, msg):
        self.log("Starting up")
        self.shmem, self.shmem_dva = self.asc.ioalloc(0x10000)
        self.asc.p.memset32(self.shmem, 0, 0x10000)

        self.send_init_config()
        return True

    def send_init_config(self):
        dram_config = self.asc.u.adt["arm-io/pmp/iop-pmp-nub"].energy_model_dram_configs
        self.asc.iface.writemem(self.shmem + 0x2000, dram_config)

        node = self.asc.u.adt["arm-io/pmp"]
        maps = []
        dva = 0xc0000000

        def map_addresses(reg_indx_start, reg_indx_end):
            nonlocal dva
            for i in range(reg_indx_start, reg_indx_end):
                addr, size = node.get_reg(i)

                if size == 0:
                    maps.append(struct.pack("<QQ", 0, 0))
                    continue

                self.asc.dart.iomap_at(0, dva, addr, size)
                self.log(f"map {addr:#x} -> {dva:#x} [{size:#x}]")
                maps.append(struct.pack("<QQ", dva, size))

                dva += align(size, 0x4000)

        # 1st region
        map_addresses(3, 17)

        # 2nd region
        dva = 0xc1000000
        map_addresses(17, 18)

        # 3rd region
        dva = 0xc2000000
        map_addresses(18, 24)

        # so on...
        dva = 0xc3000000
        map_addresses(24, 30)

        dva = 0xc4000000
        map_addresses(30, 33)

        dva = 0xc5000000
        map_addresses(33, 35)

        dva = 0xc0024000
        map_addresses(35, 37)

        dva = 0xc6000000
        map_addresses(37, 38)

        dva = 0xc1004000
        map_addresses(38, 39)

        dva = 0xc3074000
        map_addresses(39, 42)

        dva = 0xc2074000
        map_addresses(42, 43)

        dva = 0xc1008000
        map_addresses(43, 44)

        chexdump32(b"".join(maps), st=0xe000)

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
        chexdump32(props)
        print("PMP Device Info:")
        chexdump32(devinfo)
        print("PMP Status:")
        chexdump32(status)

        self.send(PMP_Init1(UNK1=1, UNK2=3))
        while not self.init1_acked:
            self.asc.work()

        self.send(PMP_Init2(UNK1=1, UNK2=0))
        while not self.init2_acked:
            self.asc.work()

        self.send(PMP_DevPwr(DEV=0x63, STATE=1))
        self.send(PMP_DevPwr(DEV=0x68, STATE=0))
        # self.send(PMP_DevPwr(DEV=0x68, STATE=1))
        # self.send(PMP_DevPwr(DEV=0x66, STATE=0))

        # for i in range(36):
        #     self.send(0x20400000020000)
        #     while not self.unk3_acked:
        #         self.asc.work()
        #     self.unk3_acked = False
        #     self.send(0x20400000000000)
        #     while not self.unk3_acked:
        #         self.asc.work()
        #     self.unk3_acked = False


        # self.send(PMP_DevPwr(DEV=0x65, STATE=1))

        # self.send(PMP_DevPwr(DEV=0x64, STATE=1))

        # self.send(PMP_DevPwr(DEV=0x5c, STATE=0))
        # self.send(PMP_DevPwr(DEV=0x5c, STATE=1))
        # self.send(PMP_DevPwr(DEV=0x5c, STATE=0))

        return True

    @msg_handler(0x201, PMP_Init1_Ack)
    def Init1_Ack(self, msg):
        self.init1_acked = True
        return True

    @msg_handler(0x203, PMP_Init2_Ack)
    def Init2_Ack(self, msg):
        self.init2_acked = True
        return True

    @msg_handler(0x205)
    def Unk(self, msg):
        self.unk3_acked = True
        return True

class PMPClient(StandardASC):
    ENDPOINTS = {0x20: PMPEndpoint}

    def __init__(self, u, dev_path, dart=None):
        node = u.adt[dev_path]
        asc_base = node.get_reg(0)[0]
        super().__init__(u, asc_base, dart)
        self.dart = dart


if __name__ == "__main__":
    dart = DART.from_adt(u, "/arm-io/dart-pmp")
    dart.verbose = 4
    dart.initialize()

    pmp = PMPClient(u, "/arm-io/pmp", dart)
    pmp.verbose = 4

    pmp.start()
    pmp.start_ep(0x20)
    pmp.work_for(10)

    ep = pmp.epmap[0x20]

    run_shell(locals(), poll_func=pmp.work)

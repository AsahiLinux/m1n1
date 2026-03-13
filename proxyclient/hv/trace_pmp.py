from m1n1.trace import Tracer
from m1n1.trace.dart import DARTTracer
from m1n1.trace.asc import ASCTracer, EP, EPState, msg, msg_log, DIR, EPContainer
from m1n1.utils import *
from m1n1.constructutils import *
from m1n1.proxyutils import RegMonitor

import sys
import struct

iomon = RegMonitor(hv.u, ascii=True)
iomon_args = RegMonitor(hv.u, ascii=True)

class PMPMessage(Register64):
    TYPE = 56, 48

class PMPMessage_IOVATableAck(PMPMessage):
    TYPE = 56, 48, Constant(0x11)
    IOVA = 47, 0

class PMPMessage_Malloc(PMPMessage):
    TYPE = 56, 48, Constant(0x12)
    SIZE = 23, 0

class PMPMessage_MallocAck(PMPMessage):
    TYPE = 56, 48, Constant(0x13)
    IOVA = 47, 0

class PMPMessage_Free(PMPMessage):
    TYPE = 56, 48, Constant(0x14)
    IOVA = 47, 0

class PMPMessage_SetBuf(PMPMessage):
    TYPE = 56, 48, Constant(0x30)
    IOVA = 47, 0

class PMPMessage_Advertise(PMPMessage):
    TYPE = 56, 48, Constant(0x32)
    IOVA = 47, 0

class PMPMessage_AdvertiseAck(PMPMessage):
    TYPE = 56, 48, Constant(0x33)
    INDEX = 47, 32
    SIZE = 31, 0

class PMPMessage_SetVal(PMPMessage):
    TYPE = 56, 48, Constant(0x34)
    INDEX = 15, 0

class PMPMessage_SetValAck(PMPMessage):
    TYPE = 56, 48, Constant(0x35)
    SIZE = 31, 0

class PMPEp(EP):
    BASE_MESSAGE = PMPMessage

    GetIOVATable = msg_log(0x10, DIR.RX)

    @msg(0x11, DIR.TX, PMPMessage_IOVATableAck)
    def GetIOVATableAck(self, msg):
        ptr = msg.IOVA
        lines = []
        self.tracer.dart.invalidate_cache()
        while 1:
            host, periph, size = struct.unpack("<QQQ", self.tracer.ioread(ptr, 24))
            if host == 0:
                break
            ptr += 24
            lines.append(f'Host: {host:x}, Peripheral: {periph:x}, Size: {size:x}')
        self.log('IO Mapping table:\n' + '\n'.join(lines))

    Malloc = msg_log(0x12, DIR.RX, PMPMessage_Malloc)
    MallocAck = msg_log(0x13, DIR.TX, PMPMessage_MallocAck)
    Free = msg_log(0x14, DIR.RX, PMPMessage_Free)
    FreeAck = msg_log(0x15, DIR.TX)

    @msg(0x30, DIR.RX, PMPMessage_SetBuf)
    def SetBuf(self, msg):
        self.log(f'SetBuf: {msg}')
        self.tracer.dart.invalidate_cache()
        self.buf_ptr, _ = struct.unpack("<QQ", self.tracer.ioread(msg.IOVA, 16))
        iomon.add(self.buf_ptr, 4096)

    SetBufAck = msg_log(0x31, DIR.TX, PMPMessage)

    @msg(0x32, DIR.RX, PMPMessage_Advertise)
    def Advertise(self, msg):
        self.tracer.dart.invalidate_cache()
        self.log("Descriptor:")
        data = self.tracer.ioread(msg.IOVA, 0x50)
        chexdump(data, print_fn=self.log)
        self.adv_size = struct.unpack("<I", data[0x40:0x44])[0]

    @msg(0x33, DIR.TX, PMPMessage_AdvertiseAck)
    def AdvertiseAck(self, msg):
        if self.adv_size == 0:
            iomon.poll()



    @msg(0x34, DIR.RX, PMPMessage_SetVal)
    def SetVal(self, msg):
        chexdump(self.tracer.ioread(self.buf_ptr, 0x50), print_fn=self.log)

    SetValAck = msg_log(0x35, DIR.TX, PMPMessage_SetValAck)

class PMPTracer(ASCTracer):
    ENDPOINTS = {0x20: PMPEp}

    def w_CPU_CONTROL(self, val):
        iomon_args.poll()
        super().w_CPU_CONTROL(val)

dart_pmp_tracer = DARTTracer(hv, "/arm-io/dart-pmp", verbose=4)
dart_pmp_tracer.start()

pmp_tracer = PMPTracer(hv, "/arm-io/pmp", verbose=1)
pmp_tracer.start(dart_pmp_tracer.dart)

def readmem_iova(addr, size, readfn=None):
    try:
        return dart_pmp_tracer.dart.ioread(0, addr, size)
    except Exception as e:
        print(e)
        return None

iomon.readmem = readmem_iova
def readmem_phys(addr, size, readfn=None):
    return hv.iface.readmem(addr, size)
iomon_args.readmem = readmem_phys
#iomon_args.add(*u.adt["/arm-io/pmp"].get_reg(2))
#iomon_args.poll()

pmp_ptd_range = u.adt['/arm-io/pmp/iop-pmp-nub'].ptd_range
pmp_ptd_range_map = {}
for i in range(len(pmp_ptd_range) // 32):
    id, offset, _, name = struct.unpack('<II8s16s', pmp_ptd_range[i*32:(i+1)*32])
    pmp_ptd_range_map[name.strip(b'\x00')] = offset

class R_PmpStatus(Register64):
    READY = 0

pmp_bits = {dev.name:(dev.id1 - 1) for dev in u.adt['/arm-io/pmgr'].devices if dev.flags.notify_pmp}
print(pmp_bits)

R_StatusMap = type('R_StatusMap', (Register64,), pmp_bits)

class PMPRegs(RegMap):
    DEV_STATUS_TGT_RD = (pmp_ptd_range_map[b'SOC-DEV-PS-REQ'] * 16), R_StatusMap
    DEV_STATUS_TGT_UNK = (pmp_ptd_range_map[b'SOC-DEV-PS-REQ'] * 16 + 8), Register64
    DEV_STATUS_TGT_WR = (pmp_ptd_range_map[b'SOC-DEV-PS-REQ'] * 8 + 0x10000), R_StatusMap
    DEV_STATUS_ACT = (pmp_ptd_range_map[b'SOC-DEV-PS-ACK'] * 16), R_StatusMap
    DEV_STATUS_ACT_UNK = (pmp_ptd_range_map[b'SOC-DEV-PS-ACK'] * 16 + 8), Register64
    PMP_STATUS = (pmp_ptd_range_map[b'PMP-STATUS'] * 16), R_PmpStatus
    PMP_STATUS_UNK = (pmp_ptd_range_map[b'PMP-STATUS'] * 16 + 8), Register64


class PMPRegTracer(Tracer):

    def start(self):
        start, len = u.adt['/arm-io/pmgr'].get_reg(41)
        #self.trace(start, len, TraceMode.HOOK)
        self.trace_regmap(start, len, PMPRegs, name="PMP", regmap_offset=0, mode=TraceMode.SYNC)
    def hook_w(self, addr, val, width, **kwargs):
        self.hv.log(f"PMP: W {addr:#x} <- {val:#x}")
        super().hook_w(addr, val, width, **kwargs)
    def hook_r(self, addr, width, **kwargs):
        val = super().hook_r(addr, width, **kwargs)
        self.hv.log(f"PMP: R {addr:#x} = {val:#x}")
        return val
    def evt_rw(self, *args, **kwargs):
        super().evt_rw(*args, **kwargs)


rt = PMPRegTracer(hv)
rt.verbose = 4
rt.start()

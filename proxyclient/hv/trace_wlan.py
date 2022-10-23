import struct
from construct import *

from m1n1.utils import irange
from m1n1.hw.dart import DART
from m1n1.utils import chexdump
from m1n1.proxyutils import RegMonitor
from m1n1.constructutils import *

from m1n1.trace.pcie import *

PCIeDevTracer = PCIeDevTracer._reloadcls()

mon = RegMonitor(hv.u)

class WLANCfgSpace(PCICfgSpace):
    BAR0_WINDOW         = 0x80, Register32
    WRAPPERBASE         = 0x70, Register32
    INTSTATUS           = 0x90, Register32
    INTMASK             = 0x94, Register32
    SBMBX               = 0x98, Register32
    LINK_STATUS_CTRL    = 0xbc, Register32

class WLANBAR0(RegMap):
    INTMASK             = 0x2024, Register32
    MAILBOXINT          = 0x2048, Register32
    MAILBOXMASK         = 0x204c, Register32
    CONFIGADDR          = 0x2120, Register32
    CONFIGDATA          = 0x2124, Register32
    H2D_MAILBOX_0       = 0x2140, Register32
    H2D_MAILBOX_1       = 0x2144, Register32

    # Linux uses these, via offset 0 instead of 0x2000
    H2D_MAILBOX_0_ALT   = 0x140, Register32
    H2D_MAILBOX_1_ALT   = 0x144, Register32
    H2D_MAILBOX_0_64    = 0xa20, Register32
    H2D_MAILBOX_1_64    = 0xa24, Register32
    INTMASK_64          = 0xc14, Register32
    MAILBOXINT_64       = 0xc30, Register32
    MAILBOXMASK_64      = 0xc34, Register32

class WLANSRAMEnd(RegMap):
    PAD                 = 0x00, Register32
    SHARED_BASE         = 0x04, Register32

class WLANSRAMShared(RegMap):
    FLAGS               = 0, Register32
    CONSOLE_ADDR        = 20, Register32
    FWID                = 28, Register32
    MAX_RXBUFPOST       = 34, Register16
    RX_DATAOFFSET       = 36, Register32
    HTOD_MB_DATA_ADDR   = 40, Register32
    DTOH_MB_DATA_ADDR   = 44, Register32
    RING_INFO_ADDR      = 48, Register32
    DMA_SCRATCH_LEN     = 52, Register32
    DMA_SCRATCH_ADDR    = 56, Register64
    HOST_SCB_ADDR       = 64, Register64
    HOST_SCB_SIZE       = 72, Register32
    BUZZ_DBG_PTR        = 76, Register32
    FLAGS2              = 80, Register32
    HOST_CAP            = 84, Register32
    HOST_TRAP_ADDR      = 88, Register64
    DEVICE_FATAL_LOGBUF_START = 96, Register32
    HOFFLOAD_ADDR       = 100, Register64
    FLAGS3              = 108, Register32
    HOST_CAP2           = 112, Register32
    HOST_CAP3           = 116, Register32

class WLANSRAMRingInfo(RegMap):
    RINGMEM             = 0x00, Register32
    H2D_W_IDX_PTR       = 0x04, Register32
    H2D_R_IDX_PTR       = 0x08, Register32
    D2H_W_IDX_PTR       = 0x0c, Register32
    D2H_R_IDX_PTR       = 0x10, Register32
    H2D_W_IDX_HOSTADDR  = 0x14, Register64
    H2D_R_IDX_HOSTADDR  = 0x1c, Register64
    D2H_W_IDX_HOSTADDR  = 0x24, Register64
    D2H_R_IDX_HOSTADDR  = 0x2c, Register64
    MAX_FLOWRINGS       = 0x34, Register32
    MAX_SUBMISSIONRINGS = 0x38, Register32
    MAX_COMPLETIONRINGS = 0x3c, Register32

COMMON_RING_CNT = 5

class WLANSRAMRingMem(RegMap):
    MAX_ITEM            = irange(0x04, COMMON_RING_CNT, 0x10), Register16
    LEN_ITEMS           = irange(0x06, COMMON_RING_CNT, 0x10), Register16
    BASE_ADDR           = irange(0x08, COMMON_RING_CNT, 0x10), Register32

class MsgHeader(ConstructClass):
    subcon = Struct(
        "msg_type" / Int8ul,
        "if_id" / Int8sl,
        "flags" / Int8ul,
        "epoch" / Int8ul,
        "request_id" / Int32ul,
    )

class ComplHeader(ConstructClass):
    subcon = Struct(
        "status" / Int16ul,
        "ring_id" / Int16ul,
    )

class IOCtlPtrReq(ConstructClass):
    subcon = Struct(
        "cmd" / Int32ul,
        "trans_id" / Int16ul,
        "input_buf_len" / Int16ul,
        "output_buf_len" / Int16ul,
        "rsvd" / Array(3, Int16ul),
        "host_input_buf_addr" / Int64ul,
    )

class IOCtlResp(ConstructClass):
    subcon = Struct(
        "compl" / ComplHeader,
        "resp_len" / Int16ul,
        "trans_id" / Int16ul,
        "cmd" / Int32ul,
    )

class H2DMailboxData(ConstructClass):
    subcon = Struct(
        "data" / Int32ul
    )

class D2HMailboxData(ConstructClass):
    subcon = Struct(
        "compl" / ComplHeader,
        "data" / Int32ul,
    )

class RingMessage(ConstructClass):
    subcon = Struct(
        "hdr" / MsgHeader,
        "payload" / Switch(this.hdr.msg_type, {
            0x09: IOCtlPtrReq,
            0x0c: IOCtlResp,
            0x23: H2DMailboxData,
            0x24: D2HMailboxData,

        }, default=HexDump(GreedyBytes))
    )

class RingState:
    pass

class WLANRingTracer(PCIeDevTracer):
    def __init__(self, wlan, info):
        self.wlan = wlan
        self.hv = wlan.hv
        self.p = wlan.hv.p
        self.u = wlan.hv.u
        self.ringid = self.RX, self.PTR_IDX
        if self.ringid in wlan.state.rings:
            self.state = wlan.state.rings[self.ringid]
        else:
            self.state = wlan.state.rings[self.ringid] = RingState()
            self.state.rptr = 0

        self.info = info
        assert info.item_size == self.ITEM_SIZE
        self.base_addr = info.base_addr
        self.count = info.count

        if self.RX:
            d2h_paddr = self.wlan.iotranslate(self.wlan.state.d2h_w_idx_ha + 4 * self.PTR_IDX, 4)[0][0]
            assert d2h_paddr is not None
            self.hv.add_tracer(irange(d2h_paddr, 4), self.wlan.ident, TraceMode.SYNC,
                               read=self.d2h_w_idx_readhook)

    def d2h_w_idx_readhook(self, evt):
        self.log("W idx read")
        self.poll()

    def poll(self):
        if self.RX:
            wptr = self.wlan.ioread(self.wlan.state.d2h_w_idx_ha + 4 * self.PTR_IDX, 4)
        else:
            wptr = self.wlan.ioread(self.wlan.state.h2d_w_idx_ha + 4 * self.PTR_IDX, 4)

        wptr = struct.unpack("<I", wptr)[0]

        while wptr != self.state.rptr:
            off = self.state.rptr * self.ITEM_SIZE
            addr = self.base_addr + off
            data = self.wlan.ioread(addr, self.ITEM_SIZE)
            self.pkt(data)
            self.state.rptr = (self.state.rptr + 1) % self.count

    def pkt(self, data):
        self.log("Got packet:")
        pkt = RingMessage.parse(data)
        self.log(pkt)
        if pkt.hdr.msg_type == 0x09:
            self.wlan.ioctlptr_req(pkt)
        if pkt.hdr.msg_type == 0x0c:
            self.wlan.ioctlresp(pkt)

    def log(self, msg):
        self.wlan.log(f"[{self.NAME}]{msg!s}")

class WLANControlSubmitRingTracer(WLANRingTracer):
    NAME = "CTLSubmit"
    PTR_IDX = 0
    RX = False
    ITEM_SIZE = 0x28

class WLANControlCompleteRingTracer(WLANRingTracer):
    NAME = "CTLCompl"
    PTR_IDX = 0
    RX = True
    ITEM_SIZE = 0x18

class RingInfo:
    def __init__(self):
        self.count = None
        self.item_size = None
        self.base_addr = None

    def ready(self):
        return self.count is not None and self.item_size is not None and self.base_addr is not None

class WLANTracer(PCIeDevTracer):
    DEFAULT_MODE = TraceMode.SYNC

    SRAM_BASE = 0x740000
    SRAM_SIZE = 0x1f9000

    BARMAPS = [WLANBAR0, None, None]
    CFGMAP = WLANCfgSpace

    RINGS = [
        WLANControlSubmitRingTracer,
        None, # RXPost
        WLANControlCompleteRingTracer,
        None, # TX complete
        None, # RX complete
    ]

    CMDS = {
        1: "GET_VERSION",
        2: "UP",
        3: "DOWN",
        262: "GET_VAR",
        263: "SET_VAR",
    }

    def __init__(self, hv, apcie, bus, dev, fn, dart_path=None, verbose=False):
        super().__init__(hv, apcie, bus, dev, fn, verbose=verbose)
        self.u = hv.u
        self.p = hv.p
        self.dart_path = dart_path
        self.dart_dev = None
        self.dart = None
        self.rings = {}

    def init_state(self):
        super().init_state()
        self.state.shared_base = None
        self.state.ring_info_base = None
        self.state.ring_mem_base = None
        self.state.tcm_base = None
        self.state.tcm_size = None
        self.state.ring_info = None
        self.state.ring_mem = None
        self.state.ring_info_data = {}
        self.state.rings = {}
        self.state.ioctls = {}
        self.state.h2d_w_idx_ha = None
        self.state.h2d_r_idx_ha = None
        self.state.d2h_w_idx_ha = None
        self.state.d2h_r_idx_ha = None

    def config_dart(self):
        # Ugly...
        if self.dart_dev is None:
            for i in range (16):
                ttbr = self.dart.regs.TTBR[i, 0].reg
                if ttbr.VALID:
                    self.log(f"DART device: {i}")
                    self.dart_dev = i
                    break
            else:
                raise Exception("Failed to find DART device")

    def ioread(self, addr, size):
        self.config_dart()
        return self.dart.ioread(self.dart_dev, addr, size)

    def iotranslate(self, addr, size):
        self.config_dart()
        return self.dart.iotranslate(self.dart_dev, addr, size)

    def r_SHARED_BASE(self, base):
        if base.value & 0xffff == (base.value >> 16) ^ 0xffff:
            return

        self.state.shared_base = base.value
        self.update_shared()

    def w_H2D_W_IDX_HOSTADDR(self, addr):
        self.state.h2d_w_idx_ha = addr.value

    def w_H2D_R_IDX_HOSTADDR(self, addr):
        self.state.h2d_r_idx_ha = addr.value

    def w_D2H_W_IDX_HOSTADDR(self, addr):
        self.state.d2h_w_idx_ha = addr.value

    def w_D2H_R_IDX_HOSTADDR(self, addr):
        self.state.d2h_r_idx_ha = addr.value

    def w_MAX_ITEM(self, val, index):
        info = self.state.ring_info_data.setdefault(index, RingInfo())
        info.count = val.value
        self.update_ring(index)

    def w_LEN_ITEMS(self, val, index):
        info = self.state.ring_info_data.setdefault(index, RingInfo())
        info.item_size = val.value
        self.update_ring(index)

    def w_BASE_ADDR(self, val, index):
        info = self.state.ring_info_data.setdefault(index, RingInfo())
        info.base_addr = val.value
        self.update_ring(index)

    def update_ring(self, idx):
        if idx not in self.state.ring_info_data:
            return
        info = self.state.ring_info_data[idx]
        if not info.ready():
            return

        if idx in self.rings:
            return

        if idx > len(self.RINGS):
            return

        ringcls = self.RINGS[idx]

        if ringcls is None:
            return

        self.rings[idx] = ringcls(self, info)

    def w_H2D_MAILBOX_0(self, val):
        ring = self.rings.get(2, None)
        if ring is not None:
            ring.poll()

        ring = self.rings.get(0, None)
        if ring is not None:
            ring.poll()

    w_H2D_MAILBOX_0_64 = w_H2D_MAILBOX_0
    w_H2D_MAILBOX_0_ALT = w_H2D_MAILBOX_0

    def ioctlptr_req(self, pkt):
        data = self.ioread(pkt.payload.host_input_buf_addr, pkt.payload.input_buf_len)
        cmd = self.CMDS.get(pkt.payload.cmd, "unk")
        self.log(f"IOCTL request ({cmd}):")
        chexdump(data, print_fn = self.log)
        self.state.ioctls[pkt.payload.trans_id] = pkt

    def ioctlresp(self, pkt):
        req = self.state.ioctls.get(pkt.payload.trans_id, None)
        if req is None:
            self.log(f"ERROR: unknown transaction ID {pkt.payload.trans_id:#x}")
            return

        data = self.ioread(req.payload.host_input_buf_addr, req.payload.output_buf_len)
        cmd = self.CMDS.get(pkt.payload.cmd, "unk")
        self.log(f"IOCTL response ({cmd}):")
        chexdump(data, print_fn = self.log)
        del self.state.ioctls[pkt.payload.trans_id]

    def trace_bar(self, idx, start, size):
        if idx != 2:
            return super().trace_bar(idx, start, size)

        self.state.tcm_base = start
        self.state.tcm_size = size

        self.update_tcm_tracers()

    def update_tcm_tracers(self):
        if self.state.tcm_base is None:
            return

        if self.dart is None:
            self.dart = DART.from_adt(self.u, self.dart_path)

        self.trace_regmap(self.state.tcm_base + self.SRAM_BASE + self.SRAM_SIZE - 8, 8,
                          WLANSRAMEnd, name="sram")

    def update_shared(self):
        base = self.state.shared_base
        if base is None:
            return

        if self.state.ring_info_base is None:
            self.shared = WLANSRAMShared(self.hv.u, self.state.tcm_base + base)

            self.log("Reading shared info")
            self.shared.dump_regs()

            self.state.ring_info_base = self.shared.RING_INFO_ADDR.val

        if self.state.ring_mem_base is None:
            self.ring_info = WLANSRAMRingInfo(self.hv.u,
                                            self.state.tcm_base + self.state.ring_info_base)
            self.log("Reading ring info")
            self.ring_info.dump_regs()

            self.state.ring_mem_base = self.ring_info.RINGMEM.val

        self.trace_regmap(self.state.tcm_base + base, 0x100,
                          WLANSRAMShared, name="shared")

        self.trace_regmap(self.state.tcm_base + self.state.ring_info_base, 0x40,
                          WLANSRAMRingInfo, name="ringinfo")

        self.ring_mem = WLANSRAMRingMem(self.hv.u,
                                        self.state.tcm_base + self.state.ring_mem_base)
        self.log("Reading ring mem")
        self.ring_mem.dump_regs()

        self.trace_regmap(self.state.tcm_base + self.state.ring_mem_base,
                          COMMON_RING_CNT * 0x10, WLANSRAMRingMem, name="ringmem")

    def start(self):
        super().start()

        self.update_tcm_tracers()
        self.update_shared()
        for i in range(len(self.RINGS)):
            self.update_ring(i)

wlan_tracer = WLANTracer(hv, "/arm-io/apcie",
                         4, 0, 0, "/arm-io/dart-apcie0")

wlan_tracer.start()

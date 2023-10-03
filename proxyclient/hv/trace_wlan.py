import struct
from construct import *

from m1n1.utils import irange
from m1n1.hw.dart import DART
from m1n1.utils import chexdump
from m1n1.proxyutils import RegMonitor
from m1n1.constructutils import *
from m1n1.hv.types import MMIOTraceFlags

from m1n1.trace.pcie import *

PCIeDevTracer = PCIeDevTracer._reloadcls()

mon = RegMonitor(hv.u)

class WLANCfgSpace(PCICfgSpace):
    PM_CSR              = 0x4c, Register32

    MSI_CAP             = 0x58, Register16
    MSI_CTRL            = 0x5a, Register16
    MSI_ADDR_L          = 0x5c, Register32
    MSI_ADDR_H          = 0x60, Register32
    MSI_DATA            = 0x64, Register32

    BAR0_WIN_1000       = 0x70, Register32
    BAR0_WIN_4000       = 0x74, Register32
    BAR0_WIN_5000       = 0x78, Register32
    BAR0_WINDOW         = 0x80, Register32
    BAR1_WINDOW         = 0x84, Register32
    SPROM_CONTROL       = 0x88, Register32
    CFG_SUBSYS_CONTROL  = 0x8c, Register32
    INTSTATUS           = 0x90, Register32
    INTMASK             = 0x94, Register32
    BACKPLANE_ADDR      = 0x98, Register32
    BACKPLANE_DATA      = 0x9c, Register32
    CLK_CTL_ST          = 0xa8, Register32

    CFG_DEVICE_CONTROL  = 0xb4, Register32
    LINK_STATUS_CTRL    = 0xbc, Register32

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
    ETD_ADDR            = 120, Register32
    DEVICE_TXPOST_EXT_TAGS_BITMASK = 124, Register32

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

class REG_IOCTL(Register32):
    CLK = 0
    FGC = 1
    CORE_SPECIFIC = 13, 2
    PME_EN = 14
    BIST_EN = 15

class REG_IOST(Register32):
    CORE_SPECIFIC = 11, 0
    DMA64 = 12
    GATED_CLK = 13
    BIST_ERROR = 14
    BIST_DONE = 15

class REG_RESET_CTL(Register32):
    RESET = 0

class REG_CLK_CTL(Register32):
    FORCEALP = 0
    FORCEHT = 1
    FORCEILP = 2
    HAVEALPREQ = 3
    HAVEHTREQ = 4
    HWCROFF = 5
    HQCLKREQ = 6
    EXTRESREQ = 11, 8
    HAVEALP = 16
    HAVEHT = 17
    BP_ON_ALP = 18
    BP_ON_HT = 19
    EXTRESST = 26, 24

class REG_PWR_CTL(Register32):
    DMN0 = 0
    DMN1 = 1
    DMN2 = 2
    DMN3 = 3
    DMN4 = 4
    PWRON_DMN0 = 8
    PWRON_DMN1 = 9
    PWRON_DMN2 = 10
    PWRON_DMN3 = 11
    PWRON_DMN4 = 12
    ST_DMN0 = 16
    ST_DMN1 = 17
    ST_DMN2 = 18
    ST_DMN3 = 19
    ST_DMN4 = 20
    BT_STATUS = 21, 20
    DMN_ID = 31, 28

class WLANAgentRegs(RegMap):
    IOCTL               = 0x408, REG_IOCTL
    IOST                = 0x500, REG_IOST
    RESET_CTL           = 0x800, REG_RESET_CTL

class WLANDevice(Reloadable):
    LENGTH = 0x1000
    WRAP_LENGTH = 0x1000
    REGMAP = None
    WRAP_REGMAP = WLANAgentRegs

    def __init__(self, wlan, type, rev, name, base, wrap):
        self.wlan = wlan
        self.hv = wlan.hv
        self.type = type
        self.rev = rev
        self.name = name
        self.base = base
        self.wrap = wrap
        self.regmap = None
        self.wrap_regmap = None

        if self.REGMAP is not None:
            self.regmap = self.REGMAP(self, base)

        if self.WRAP_REGMAP is not None:
            self.wrap_regmap = self.WRAP_REGMAP(self, wrap)

    def read(self, addr, width):
        assert False

    def write(self, addr, data, width):
        assert False

    def evt_rw(self, evt, base):
        reg = rcls = None
        addr = evt.addr + base
        value = evt.data

        t = "w" if evt.flags.WRITE else "r"

        pfx = f"{self.name}:"

        if self.regmap is not None:
            reg, index, rcls = self.regmap.lookup_addr(addr)
            regmap = self.regmap
            if rcls is not None:
                value = rcls(evt.data)

        if reg is None and self.wrap_regmap is not None:
            reg, index, rcls = self.wrap_regmap.lookup_addr(addr)
            regmap = self.wrap_regmap
            if rcls is not None:
                value = rcls(evt.data)
            if reg is not None:
                pfx = f"{self.name}.wrap:"

        if self.wlan.verbose >= 3 or (reg is None and self.wlan.verbose >= 1):
            if reg is None:
                s = pfx + f"{addr:#x} = {value:#x}"
            else:
                s = pfx + f"{regmap.get_name(addr)} = {value!s}"
            m = "+" if evt.flags.MULTI else " "
            self.wlan.log(f"WLAN: {t.upper()}.{1<<evt.flags.WIDTH:<2}{m} " + s)

        if reg is not None:
            attr = f"{t}_{reg}"
            handler = getattr(self, attr, None)
            if handler:
                if index is not None:
                    handler(value, index)
                else:
                    handler(value)
            elif self.wlan.verbose == 2:
                s = pfx + f"{regmap.get_name(evt.addr)} = {value!s}"
                m = "+" if evt.flags.MULTI else " "
                self.wlan.log(f"WLAN: {t.upper()}.{1<<evt.flags.WIDTH:<2}{m} " + s)

    def log(self, msg, show_cpu=True):
        self.wlan.log(f"[{self.name}] {msg}", show_cpu=show_cpu)

class WLANBackplane(Reloadable):
    SRAM_BASE = 0x740000
    SRAM_SIZE = 0x1f9000

    DEVICES = []

    def __init__(self, wlan):
        self.wlan = wlan
        self.hv = wlan.hv
        self.devices = []
        self.addr_map = ScalarRangeMap()
        self.name_map = {}
        self.unk_dev = WLANDevice(wlan, 0, 0, "unk", 0, 0)

        for type, rev, base, wrap, name, cls in self.DEVICES:
            if cls is None:
                cls = WLANDevice
            dev = cls(wlan, type, rev, name, base, wrap)
            self.devices.append(dev)
            self.wlan.log(f"add dev {name} base {base:#x} wrap {wrap:#x}")
            self.name_map[name] = dev
            if base != 0:
                self.addr_map[irange(base, dev.LENGTH)] = dev
            if wrap != 0:
                self.addr_map[irange(wrap, dev.LENGTH)] = dev
            setattr(self, name, dev)

    def evt_rw(self, evt, base):
        if isinstance(base, str):
            dev = self.name_map.get(base, self.unk_dev)
            base = dev.base
        else:
            dev = self.addr_map.get(base, self.unk_dev)

        dev.evt_rw(evt, base)
        regmap = dev.regmap

class WLANChipCommonRegs(RegMap):
    pass

class WLANPCIE2Regs(RegMap):
    INTMASK                 = 0x24, Register32
    MAILBOXINT              = 0x48, Register32
    MAILBOXMASK             = 0x4c, Register32
    CONFIGADDR              = 0x120, Register32
    CONFIGDATA              = 0x124, Register32
    H2D_MAILBOX_0           = 0x140, Register32
    H2D_MAILBOX_1           = 0x144, Register32

    CLK_CTL                 = 0x1e0, REG_CLK_CTL
    PWR_CTL                 = 0x1e8, REG_PWR_CTL

    HMAP_WINDOW_BASE_L      = 0x540, Register32
    HMAP_WINDOW_BASE_H      = 0x544, Register32
    HMAP_WINDOW_SIZE        = 0x548, Register32
    HMAP_VIOLATION_ADDR_L   = 0x5c0, Register32
    HMAP_VIOLATION_ADDR_H   = 0x5c4, Register32
    HMAP_VIOLATION_INFO     = 0x5c8, Register32
    HMAP_WINDOW_CONFIG      = 0x5d0, Register32

    HMAP_WINDOW_BASE_L_64   = 0x580, Register32
    HMAP_WINDOW_BASE_H_64   = 0x584, Register32
    HMAP_WINDOW_SIZE        = 0x588, Register32
    HMAP_VIOLATION_ADDR_L_64= 0x600, Register32
    HMAP_VIOLATION_ADDR_H_64= 0x604, Register32
    HMAP_VIOLATION_INFO_64  = 0x608, Register32
    HMAP_WINDOW_CONFIG_64   = 0x610, Register32

    H2D_MAILBOX_0_64        = 0xa20, Register32
    H2D_MAILBOX_1_64        = 0xa24, Register32
    INTMASK_64              = 0xc14, Register32
    MAILBOXINT_64           = 0xc30, Register32
    MAILBOXMASK_64          = 0xc34, Register32

class WLANPCIE2Core(WLANDevice):
    REGMAP = WLANPCIE2Regs

    def w_H2D_MAILBOX_0(self, val):
        ring = self.wlan.rings.get(2, None)
        if ring is not None:
            ring.poll()

        ring = self.wlan.rings.get(0, None)
        if ring is not None:
            ring.poll()

    w_H2D_MAILBOX_0_64 = w_H2D_MAILBOX_0

    def w_MAILBOXMASK_64(self, val):
        pass
        #self.hv.run_shell()

class WLANGCIRegs(RegMap):
    OTPDATA = irange(0x1000, 0x400, 2), Register16

class WLANGCICore(WLANDevice):
    LENGTH = 0x2000
    REGMAP = WLANGCIRegs

class WLANBackplane4388(WLANBackplane):
    SRAM_BASE = 0x200000
    SRAM_SIZE = 0x2e0000

    DEVICES = [
        (0x800, 75,  0x18000000, 0x18100000, "cc",      None),
        (0x83c, 74,  0x18001000, 0x18101000, "pcie2",   WLANPCIE2Core),
        (0x847, 11,  0x18020000, 0x18120000, "arm_ca7", None),
        (0x812, 87,  0x18021000, 0x18121000, "80211_0", None),
        (0x812, 87,  0x18022000, 0x18122000, "80211_1", None),
        (0x812, 87,  0x18023000, 0x18123000, "80211_2", None),
        (0x850, 1,   0x00000000, 0x1812c000, "850?",    None),
        (0x849, 12,  0x18024000, 0x18124000, "sys_mem", None),
        (0x857, 8,   0x00000000, 0x18108000, "857?",    None),
        (0x840, 27,  0x18010000, 0x00000000, "gci",     WLANGCICore),
        (0x827, 43,  0x18012000, 0x00000000, "pmu",     None),
        (0x135, 0,   0x00000000, 0x18106000, "apb_0",  None),
        (0x135, 0,   0x00000000, 0x18107000, "apb_1",  None),
        (0x135, 0,   0x00000000, 0x18132000, "apb_2",  None),
        (0x31,  0,   0x00000000, 0x18131000, "31_0?",   None),
        (0x31,  0,   0x00000000, 0x1810b000, "31_1?",   None),
        (0x31,  0,   0x00000000, 0x1810c000, "31_2?",   None),
        (0xfff, 0,   0x1801f000, 0x18104000, "fff_0?",  None),
        (0xfff, 0,   0x1801f000, 0x1812f000, "fff_1?",  None),
    ]

class WLANTracer(PCIeDevTracer):
    DEFAULT_MODE = TraceMode.SYNC

    BARMAPS = [None, None, None]
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

    CHIPSETS = {
        4388: WLANBackplane4388,
    }

    def __init__(self, hv, apcie, bus, dev, fn, dart_path=None, verbose=False):
        super().__init__(hv, apcie, bus, dev, fn, verbose=verbose)
        self.u = hv.u
        self.p = hv.p
        self.dart_path = dart_path
        self.dart_dev = None
        self.dart = None
        self.rings = {}
        self.chipset = u.adt["/product"].wifi_chipset
        self.bp = self.CHIPSETS.get(int(self.chipset), WLANBackplane)(self)

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

    def bar0_rw(self, evt):
        off = evt.addr - self.state.bar0_base
        value = evt.data

        t = "w" if evt.flags.WRITE else "r"

        evt = evt.copy()
        evt.addr = off & 0xfff

        if 0x0000 <= off < 0x1000:
            self.bp.evt_rw(evt, self.cfg.cached.BAR0_WINDOW.val)
        elif 0x1000 <= off < 0x2000:
            self.bp.evt_rw(evt, self.cfg.cached.BAR0_WIN_1000.val)
        elif 0x2000 <= off < 0x3000:
            self.bp.evt_rw(evt, "pcie2")
        elif 0x3000 <= off < 0x4000:
            self.bp.evt_rw(evt, "cc")
        elif 0x4000 <= off < 0x5000:
            self.bp.evt_rw(evt, self.cfg.cached.BAR0_WIN_4000.val)
        elif 0x5000 <= off < 0x6000:
            self.bp.evt_rw(evt, self.cfg.cached.BAR0_WIN_5000.val)
        else:
            self.bp.evt_rw(evt, f"unk{off>>12:#x}")

    def config_dart(self):
        # Ugly...
        if self.dart_dev is None:
            for i in range (16):
                ttbr = self.dart.dart.regs.TTBR[i].reg
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

    def w_cfg_BACKPLANE_DATA(self, val):
        win = self.cfg.cached.BAR0_WINDOW.val
        evt = Container()
        evt.flags = MMIOTraceFlags(WIDTH=2, WRITE=1)
        evt.addr = self.cfg.cached.BACKPLANE_ADDR.val
        evt.data = val.value
        self.bp.evt_rw(evt, win)

    def r_cfg_BACKPLANE_DATA(self, val):
        win = self.cfg.cached.BAR0_WINDOW.val
        evt = Container()
        evt.flags = MMIOTraceFlags(WIDTH=2, WRITE=0)
        evt.addr = self.cfg.cached.BACKPLANE_ADDR.val
        evt.data = val.value
        self.bp.evt_rw(evt, win)

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
        if idx == 2:
            self.state.tcm_base = start
            self.state.tcm_size = size

            self.update_tcm_tracers()
        elif idx == 0:
            self.state.bar0_base = start
            self.state.bar0_size = size

            self.update_bar0_tracers()
        else:
            return super().trace_bar(idx, start, size)

    def update_tcm_tracers(self):
        if self.state.tcm_base is None:
            return

        if self.dart is None:
            self.dart = DART.from_adt(self.u, self.dart_path)

        self.trace_regmap(self.state.tcm_base + self.bp.SRAM_BASE + self.bp.SRAM_SIZE - 8, 8,
                          WLANSRAMEnd, name="sram")

    def update_bar0_tracers(self):
        if self.state.bar0_base is None:
            return

        zone = irange(self.state.bar0_base, self.state.bar0_size)
        self.hv.add_tracer(zone, self.ident, self.DEFAULT_MODE, self.bar0_rw,
                           self.bar0_rw)

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

devno = 2 if hv.xnu_mode else 1

wlan_tracer = WLANTracer(hv, "/arm-io/apcie",
                         devno, 0, 0, "/arm-io/dart-apcie0")

wlan_tracer.start()

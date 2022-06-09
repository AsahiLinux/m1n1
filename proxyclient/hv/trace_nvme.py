# SPDX-License-Identifier: MIT

from construct import *
from construct.core import Int16ul, Int32ul, Int64ul, Int8ul

from m1n1.hv import TraceMode
from m1n1.utils import *
from m1n1.trace import ADTDevTracer
from m1n1.trace.asc import ASCRegs
from m1n1.trace.asc import ASCTracer

ASCTracer = ASCTracer._reloadcls()

class NVMERegs(RegMap):
    APPLE_NVMMU_NUM = 0x28100, Register32
    APPLE_NVMMU_BASE_ASQ = 0x28108, Register32
    APPLE_NVMMU_BASE_ASQ1 = 0x2810C, Register32
    APPLE_NVMMU_BASE_IOSQ = 0x28110, Register32
    APPLE_NVMMU_BASE_IOSQ1 = 0x28114, Register32
    APPLE_NVMMU_TCB_INVAL = 0x28118, Register32
    APPLE_NVMMU_TCB_STAT = 0x28120, Register32
    APPLE_ANS2_LINEAR_SQ_CTRL = 0x24908, Register32
    APPLE_ANS2_UNKNOWN_CTRL = 0x24008, Register32
    APPLE_ANS2_BOOT_STATUS = 0x1300, Register32
    APPLE_ANS2_MAX_PEND_CMDS_CTRL = 0x1210, Register32
    APPLE_ANS2_LINEAR_ASQ_DB = 0x2490C, Register32
    APPLE_ANS2_LINEAR_IOSQ_DB = 0x24910, Register32

    NVME_REG_CAP = 0x0000, Register32
    NVME_REG_VS = 0x0008, Register32
    NVME_REG_INTMS = 0x000C, Register32
    NVME_REG_INTMC = 0x0010, Register32
    NVME_REG_CC = 0x0014, Register32
    NVME_REG_CSTS = 0x001C, Register32
    NVME_REG_NSSR = 0x0020, Register32
    NVME_REG_AQA = 0x0024, Register32
    NVME_REG_ASQ = 0x0028, Register32
    NVME_REG_ASQ1 = 0x002C, Register32
    NVME_REG_ACQ = 0x0030, Register32
    NVME_REG_CMBLOC = 0x0038, Register32
    NVME_REG_CMBSZ = 0x003C, Register32
    NVME_REG_BPINFO = 0x0040, Register32
    NVME_REG_BPRSEL = 0x0044, Register32
    NVME_REG_BPMBL = 0x0048, Register32
    NVME_REG_CMBMSC = 0x0050, Register32
    NVME_REG_PMRCAP = 0x0E00, Register32
    NVME_REG_PMRCTL = 0x0E04, Register32
    NVME_REG_PMRSTS = 0x0E08, Register32
    NVME_REG_PMREBS = 0x0E0C, Register32
    NVME_REG_PMRSWTP = 0x0E10, Register32
    NVME_REG_DBS = 0x1000, Register32
    NVME_REG_DBS_ASQ = 0x1004, Register32
    NVME_REG_DBS_IOSQ = 0x100C, Register32


AppleTunnelSetTime = Struct(
    "unk" / Int32ul,
    "unix_timestamp" / Int32ul,
    "time_0" / Int64ul,
    "time_1" / Int64ul,
)

NVMECommand = Struct(
    "opcode" / Int8ul,
    "flags" / Int8ul,
    "command_id" / Int16ul,
    "nsid" / Int32ul,
    "cdw0" / Int32ul,
    "cdw1" / Int32ul,
    "metadata" / Int64ul,
    "prp1" / Int64ul,
    "prp2" / Int64ul,
    "cdw10" / Int32ul,
    "cdw11" / Int32ul,
    "cdw12" / Int32ul,
    "cdw13" / Int32ul,
    "cdw14" / Int32ul,
    "cdw16" / Int32ul,
)

NVME_IO_COMMANDS = {
    0x00: "nvme_cmd_flush",
    0x01: "nvme_cmd_write",
    0x02: "nvme_cmd_read",
    0x04: "nvme_cmd_write_uncor",
    0x05: "nvme_cmd_compare",
    0x08: "nvme_cmd_write_zeroes",
    0x09: "nvme_cmd_dsm",
    0x0C: "nvme_cmd_verify",
    0x0D: "nvme_cmd_resv_register",
    0x0E: "nvme_cmd_resv_report",
    0x11: "nvme_cmd_resv_acquire",
    0x15: "nvme_cmd_resv_release",
    0x79: "nvme_cmd_zone_mgmt_send",
    0x7A: "nvme_cmd_zone_mgmt_recv",
    0x7D: "nvme_cmd_zone_append",
}

NVME_ADMIN_COMMANDS = {
    0x00: "nvme_admin_delete_sq",
    0x01: "nvme_admin_create_sq",
    0x02: "nvme_admin_get_log_page",
    0x04: "nvme_admin_delete_cq",
    0x05: "nvme_admin_create_cq",
    0x06: "nvme_admin_identify",
    0x08: "nvme_admin_abort_cmd",
    0x09: "nvme_admin_set_features",
    0x0A: "nvme_admin_get_features",
    0x0C: "nvme_admin_async_event",
    0x0D: "nvme_admin_ns_mgmt",
    0x10: "nvme_admin_activate_fw",
    0x11: "nvme_admin_download_fw",
    0x14: "nvme_admin_dev_self_test",
    0x15: "nvme_admin_ns_attach",
    0x18: "nvme_admin_keep_alive",
    0x19: "nvme_admin_directive_send",
    0x1A: "nvme_admin_directive_recv",
    0x1C: "nvme_admin_virtual_mgmt",
    0x1D: "nvme_admin_nvme_mi_send",
    0x1E: "nvme_admin_nvme_mi_recv",
    0x7C: "nvme_admin_dbbuf",
    0x80: "nvme_admin_format_nvm",
    0x81: "nvme_admin_security_send",
    0x82: "nvme_admin_security_recv",
    0x84: "nvme_admin_sanitize_nvm",
    0x86: "nvme_admin_get_lba_status",
    0xC0: "nvme_admin_vendor_start",
}

APPLE_TUNNEL_CMDS = {0x06: "set_time", 0x38: "get_nand_id", 0xBA: "get_nand_geometry"}

NVMMUTcb = Struct(
    "opcode" / Int8ul,
    "dma_flags" / Int8ul,
    "command_id" / Int8ul,
    "unk0" / Int8ul,
    "length" / Int32ul,
    "unk1a" / Int64ul,
    "unk1b" / Int64ul,
    "prp0" / Int64ul,
    "prp1" / Int64ul,
    "unk2a" / Int64ul,
    "unk2b" / Int64ul,
    # aes_iv, u8[8]
    # aes_data, u8[64]
)


class NVMETracer(ASCTracer):
    DEFAULT_MODE = TraceMode.SYNC

    REGMAPS = [ASCRegs, None, None, NVMERegs]
    NAMES = ["asc", None, None, "nvme"]

    ENDPOINTS = {}

    def init_state(self):
        self.state.ep = {}
        self.state.cmd_cache = {}
        self.state.nvmmu_asq_base = None
        self.state.nvmmu_iosq_base = None
        self.state.asq = None

    def r_APPLE_NVMMU_TCB_STAT(self, r):
        pass

    def w_APPLE_NVMMU_BASE_ASQ(self, r):
        self.state.nvmmu_asq_base = r.value

    def w_APPLE_NVMMU_BASE_ASQ1(self, r):
        self.state.nvmmu_asq_base |= r.value << 32

    def w_APPLE_NVMMU_BASE_IOSQ(self, r):
        self.state.nvmmu_iosq_base = r.value

    def w_APPLE_NVMMU_BASE_IOSQ1(self, r):
        self.state.nvmmu_iosq_base |= r.value << 32

    def w_NVME_REG_ASQ(self, r):
        self.state.asq = r.value

    def w_NVME_REG_ASQ1(self, r):
        self.state.asq |= r.value << 32

    def w_APPLE_ANS2_LINEAR_ASQ_DB(self, r):
        tag = r.value
        cmd = NVMECommand.parse(self.hv.iface.readmem(self.state.asq + 64 * tag, 0x40))
        tcb = NVMMUTcb.parse(
            self.hv.iface.readmem(self.state.nvmmu_asq_base + 0x80 * tag, 0x80)
        )

        self.state.cmd_cache[tag] = (True, cmd, tcb)

        if cmd.opcode == 0xD8:
            self.log("apple_tunnel_cmd:")
            self.parse_apple_tunnel_cmd(cmd, False)
            return

        cmdname = NVME_ADMIN_COMMANDS.get(cmd.opcode, "unknown")
        self.log(f"{cmdname}:")
        self.log(f"   {repr(cmd)}")
        self.log(f"   {repr(tcb)}")

        if cmd.opcode == 1:
            self.state.iosq = cmd.prp1

    def w_APPLE_ANS2_LINEAR_IOSQ_DB(self, r):
        tag = r.value
        cmd = NVMECommand.parse(self.hv.iface.readmem(self.state.iosq + 64 * tag, 0x40))
        tcb = NVMMUTcb.parse(
            self.hv.iface.readmem(self.state.nvmmu_iosq_base + 0x80 * tag, 0x80)
        )
        cmdname = NVME_IO_COMMANDS.get(cmd.opcode, "unknown")
        self.log(f"{cmdname}:")
        self.log(f"   {repr(cmd)}")
        self.log(f"   {repr(tcb)}")

        self.state.cmd_cache[tag] = (False, cmd, tcb)

    def parse_apple_tunnel_cmd(self, cmd, done):
        ptr0 = (cmd.cdw12 << 32) | cmd.cdw11
        ptr1 = (cmd.cdw14 << 32) | cmd.cdw13

        data = self.hv.iface.readmem(ptr0, 0x4000)
        if ptr1 > 0:
            data1 = self.hv.iface.readmem(ptr1, 0x4000)

        apple_cmd_opcode = data[12]
        apple_cmd = APPLE_TUNNEL_CMDS.get(apple_cmd_opcode, "Unknown")

        if apple_cmd_opcode == 0x06:
            self.log(
                f"  apple_tunnel_cmd: set_time: {repr(AppleTunnelSetTime.parse(data[0x18:0x30]))}"
            )
        elif apple_cmd_opcode == 0x38:
            self.log(f"  apple_tunnel_cmd: get_nand_id")
            if done:
                self.log(f"    manufacturer id: {hexdump(data1[:8])}")
        else:
            self.log(f"  apple_tunnel_cmd: {apple_cmd} ({apple_cmd_opcode})")
            chexdump(data, print_fn=self.log)
            if ptr1 > 0:
                chexdump(self.hv.iface.readmem(ptr1, 0x4000), print_fn=self.log)

    def w_APPLE_NVMMU_TCB_INVAL(self, r):
        self.log(f"   NVMMU inval for {r.value}")
        tag = r.value
        if tag not in self.state.cmd_cache:
            self.log("     NVMMU tag not found in cmd_cache")
            return

        is_admin, cmd, tcb = self.state.cmd_cache[tag]
        del self.state.cmd_cache[tag]

        if is_admin:
            if cmd.opcode == 0xD8:
                self.log(f"  done apple_tunnel_cmd")
                self.parse_apple_tunnel_cmd(cmd, True)
            else:
                cmdname = NVME_ADMIN_COMMANDS.get(cmd.opcode, "unknown")
                self.log(f"  done {cmdname}")
        else:
            cmdname = NVME_IO_COMMANDS.get(cmd.opcode, "unknown")
            self.log(f"  done {cmdname}")

    def start(self):
        self.state.cmd_cache = {}
        super().start()


NVMETracer = NVMETracer._reloadcls()
nvme_tracer = NVMETracer(hv, "/arm-io/ans", verbose=1)
nvme_tracer.start()

trace_device("/arm-io/sart-ans")

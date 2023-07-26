# SPDX-License-Identifier: MIT
from ...utils import chexdump32
from construct import *
import struct
import time
from .isp_opcodes import *

class ISPIORequestCommand:
    def __init__(self, iova, insize, outsize, args):
        self.iova = iova
        self.insize = insize
        self.outsize = outsize
        self.args = args
        self.opcode = struct.unpack("<l", self.args[0x4:0x8])[0]

class ISPIOCommandDispatcher:
    def __init__(self, isp):
        self.isp = isp
        self.opcode_dict = opcode_dict
        self.cmd_iova = self.isp.cmd_iova
        self._stfu = False

    @property
    def stfu(self): self._stfu = True

    def log(self, *args):
        if (not self._stfu):
            if (args): print("ISP:", *args)
            else: print()

    def send(self, cmd, cb=None):
        # TX: REQ: [0x1813140, 0xc, 0xc]  # iova, insize, outsize
        # RX: RSP: [0x1813141, 0xc, 0x0]  # iova, insize, zero
        req = ISPChannelMessage.build(
            arg0 = cmd.iova, # iova
            arg1 = cmd.insize,  # insize
            arg2 = cmd.outsize,  # outsize
        )
        # print("CHAN: IO: TX: REQ: [iova: 0x%x, insize: 0x%x, outsize: 0x%x]" % (req.arg0, req.arg1, req.arg2))

        # The largest (used) struct is 0x118. This should be good.
        patch = struct.pack("<l", 0x0)*(0x200//4)
        self.isp.iowrite(req.arg0, patch)
        self.isp.iowrite(req.arg0, cmd.args)

        rsp = self.isp.table.io.send(req)
        if (rsp == None):
            self.isp.table.terminal.dump()
            self.isp.table.dump()
            raise RuntimeError("Command %s [0x%04x] failed!" % (self.opcode2name(cmd.opcode), cmd.opcode))
        else:
            self.log("Command %s [0x%04x] success!" % (self.opcode2name(cmd.opcode), cmd.opcode))
            if (cb): cb()
        return rsp

    def opcode2name(self, opcode):
        if opcode in self.opcode_dict: return self.opcode_dict[opcode]
        else: return "CISP_CMD_UNKNOWN_%04x" % (opcode)

    def cmd_print_enable(self):
        s_cmd_print_enable = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "enable" / Int32ul,
        )
        args = s_cmd_print_enable.build(dict(
                opcode=CISP_CMD_PRINT_ENABLE,
                enable=0x1,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xc,
            outsize=0xc,
            args=args,
        )
        return self.send(cmd)

    def cmd_trace_enable(self):
        s_cmd_trace_enable = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "arg1" / Int32ul,
                "arg2" / Int32ul,
        )
        args = s_cmd_trace_enable.build(dict(
                opcode=CISP_CMD_TRACE_ENABLE,
                arg1=0x0,
                arg2=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xc,
            outsize=0xc,
            args=args,
        )
        return self.send(cmd)

    def cmd_set_isp_pmu_base(self):
        s_cmd_set_isp_pmu_base = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "base" / Int64ul,
        )
        args = s_cmd_set_isp_pmu_base.build(dict(
                opcode=CISP_CMD_SET_ISP_PMU_BASE,
                base=0x23b704000,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x10,
            outsize=0x10,
            args=args,
        )
        return self.send(cmd)

    def cmd_set_dsid_clr_req_base2(self):
        s_cmd_set_dsid_clr_req_base2 = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "base0" / Int64ul,
            "base1" / Int64ul,
            "base2" / Int64ul,
            "base3" / Int64ul,
            "regRange0" / Int32ul,
            "regRange1" / Int32ul,
            "regRange2" / Int32ul,
            "regRange3" / Int32ul,
        )
        args = s_cmd_set_dsid_clr_req_base2.build(dict(
                opcode=CISP_CMD_SET_DSID_CLR_REG_BASE2,
                base0=0x200014000,
            base1=0x200054000,
            base2=0x200094000,
            base3=0x2000d4000,
            regRange0=0x1000,
            regRange1=0x1000,
            regRange2=0x1000,
            regRange3=0x1000,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x38,
            outsize=0x0,
            args=args,
        )
        return self.send(cmd)

    def cmd_pmp_ctrl_set(self):
        """
        ISPCPU: PMP clock[scratch 0x23b738010,Int 0x23bc3c000(bit 1),size 4],bandwidth[scratch 0x23b73800c,Int 0x23bc3c000(bit 0),size 4
        Requested Vmin (300MHz) to PMP
        00000000  00000000 0000001c 3b738010 00000002 3bc3c000 00000002 00000401 3b73800c
        00000020  00000002 3bc3c000 00000002 00000400 00001000 00001000
        """
        s_cmd_pmp_ctrl_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "addr0" / Int64ul,
            "addr1" / Int64ul,
            "unk_18" / Int32ul,
            "addr3" / Int64ul,
            "addr4" / Int64ul,
            "unk_2c" / Int32ul,
            "unk_30" / Int32ul,
            "unk_34" / Int32ul,
        )
        args = s_cmd_pmp_ctrl_set.build(dict(
                opcode=CISP_CMD_PMP_CTRL_SET,
                addr0=0x23b738010,
            addr1=0x23bc3c000,
            unk_18=0x401,
            addr3=0x23b73800c,
            addr4=0x23bc3c000,
            unk_2c=0x400,
            unk_30=0x1000,
            unk_34=0x1000,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x38,
            outsize=0x0,
            args=args,
        )
        return self.send(cmd)

    def cmd_start(self):
        s_cmd_start = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "unk_8" / Int32ul,
            "unk_c" / Int32ul,
        )
        args = s_cmd_start.build(dict(
                opcode=CISP_CMD_START,
                unk_8=0x0,
            unk_c=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xc,
            outsize=0xc,
            args=args,
        )
        return self.send(cmd)

    def cmd_config_get(self):
        s_cmd_config_get = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "unk_8" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
            "unk_14" / Int32ul,
            "unk_18" / Int32ul,
        )
        args = s_cmd_config_get.build(dict(
                opcode=CISP_CMD_CONFIG_GET,
                unk_8=0x0,
            unk_c=0x0,
            unk_10=0x0,
            unk_14=0x0,
            unk_18=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x1c,
            outsize=0x1c,
            args=args,
        )
        def cb(): chexdump32(self.isp.ioread(self.cmd_iova, 0x20))
        """
        00000000  00000000 00000003 016e3600 00000001 0000000a 00000000 00000001 00000000
        """
        return self.send(cmd, cb=cb)

    def cmd_ch_info_get(self):
        s_cmd_ch_info_get = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
            "unk_14" / Int32ul,
            "unk_18" / Int32ul,
        )
        args = s_cmd_ch_info_get.build(dict(
                opcode=CISP_CMD_CH_INFO_GET,
                chan=0x0,
            unk_c=0x0,
            unk_10=0x0,
            unk_14=0x0,
            unk_18=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x118,
            outsize=0x118,
            args=args,
        )
        def cb(): chexdump32(self.isp.ioread(self.cmd_iova, 0x120))
        """
        00000000  00000000 0000010d 00000000 07da0001 000300ac 00040007 00000005 00000001
        00000020  00000248 00000007 00000001 00000001 00000000 00000000 00000000 00000000
        00000040  00000000 00000000 00000000 00010000 00000001 00000000 00000004 00000010
        00000060  00000001 00000000 000044c0 00000040 00000001 00000002 00004000 00000040
        00000080  00000001 00000000 00000000 00000036 00000000 00000000 000f4240 43430000
        000000a0  32353032 38513033 59334a56 00303333 00000000 00000008 00000000 00000000
        000000c0  00000004 00000000 00000000 00000000 00000000 00000000 00000000 00ff0000
        000000e0  00000c00 00000000 0000001c 00000640 00000004 00000004 00000000 00000000
        00000100  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
        """
        return self.send(cmd, cb=cb)

    def cmd_ch_camera_config_get(self):
        s_cmd_ch_camera_config_get = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
            "unk_14" / Int32ul,
            "unk_18" / Int32ul,
        )
        args = s_cmd_ch_camera_config_get.build(dict(
                opcode=CISP_CMD_CH_CAMERA_CONFIG_GET,
                chan=0x0,
            unk_c=0x0,
            unk_10=0x0,
            unk_14=0x0,
            unk_18=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xdc,
            outsize=0xdc,
            args=args,
        )
        def cb(): chexdump32(self.isp.ioread(self.cmd_iova, 0xe0))
        """
        00000000  00000000 00000106 00000000 00000000 02e00510 02e00510 00000000 00001df8
        00000020  00000100 00000001 00000040 00000040 00000040 00000040 00000040 00000040
        00000040  00000003 00000040 00000040 00000005 00000000 00000528 00000001 00000000
        00000060  0249f000 00000006 00000007 00000000 00000009 000f4240 00000025 00000000
        00000080  00004000 00000014 00000015 00000000 00000000 00000000 00000510 000002e0
        000000a0  00010000 00000000 00000080 039f2990 0000001f 00000000 00000000 00000000
        000000c0  00000510 000002e0 00000100 00000000 00000000 00000510 000002e0 00000000
        """
        return self.send(cmd, cb=cb)

    def cmd_ch_camera_config_select(self):
        s_cmd_ch_camera_config_select = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
            "unk_14" / Int32ul,
            "unk_18" / Int32ul,
        )
        args = s_cmd_ch_camera_config_select.build(dict(
                opcode=CISP_CMD_CH_CAMERA_CONFIG_SELECT,
                chan=0x0,
            unk_c=0x0,
            unk_10=0x0,
            unk_14=0x0,
            unk_18=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x10,
            outsize=0x10,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_sbs_enable(self):
        s_cmd_ch_sbs_enable = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
        )
        args = s_cmd_ch_sbs_enable.build(dict(
                opcode=CISP_CMD_CH_SBS_ENABLE,
                chan=0x0,
            unk_c=0x1,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x10,
            outsize=0x10,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_buffer_recycle_mode_set(self):
        # ISPCPU: b'[MSC] CH = 0x0   Dynamic Buffers Recycling Mode Set [EMPTY ONLY] \n']
        s_cmd_ch_buffer_recycle_mode_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
        )
        args = s_cmd_ch_buffer_recycle_mode_set.build(dict(
                opcode=CISP_CMD_CH_BUFFER_RECYCLE_MODE_SET,
                chan=0x0,
            unk_c=0x1,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x10,
            outsize=0x10,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_buffer_recycle_start(self):
        s_cmd_ch_buffer_recycle_start = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
        )
        args = s_cmd_ch_buffer_recycle_start.build(dict(
                opcode=CISP_CMD_CH_BUFFER_RECYCLE_START,
                chan=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xc,
            outsize=0xc,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_buffer_pool_config_set(self):
        """
        00000000  00000000 00000117 00000000 00100008 00004640 00004640 00000000 00000000
        00000080  00000000 00000000 00000000 00000000 00000000 00000001 00000000 000002e0
        TRC: CDSControllerBase.cpp, BufferPoolConfig, 2937:  0, type=8, count=16, id=8, compress=0, dataBlocks=1
        """
        s_cmd_ch_buffer_pool_config_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
            "unk_14" / Int32ul,
            "zero" / Padding(0x7c),
            "dataBlocks" / Int32ul,
        )
        args = s_cmd_ch_buffer_pool_config_set.build(dict(
                opcode=CISP_CMD_CH_BUFFER_POOL_CONFIG_SET,
                chan=0x0,
            unk_c=0x100008,
            unk_10=0x4640,
            unk_14=0x4640,
            dataBlocks=0x1,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x9c,
            outsize=0x9c,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_buffer_recycle_stop(self):
        s_cmd_ch_buffer_recycle_stop = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
        )
        args = s_cmd_ch_buffer_recycle_stop.build(dict(
                opcode=CISP_CMD_CH_BUFFER_RECYCLE_STOP,
                chan=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xc,
            outsize=0xc,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_camera_agile_freq_array_current_get(self):
        s_cmd_ch_camera_agile_freq_array_current_get = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
        )
        args = s_cmd_ch_camera_agile_freq_array_current_get.build(dict(
                opcode=CISP_CMD_CH_CAMERA_AGILE_FREQ_ARRAY_CURRENT_GET,
                chan=0x0,
            unk_c=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x10,
            outsize=0x10,
            args=args,
        )
        def cb(): chexdump32(self.isp.ioread(self.cmd_iova, 0x20))
        return self.send(cmd, cb=cb)

    def cmd_ch_crop_set(self):
        """
        00000000  00000000 00000801 00000000 00000008 00000008 00000500 000002d0 00000001
        00000020  00000248 00000007 00000001 00000001 00000000 00000000 00000000 00000000
        ISPCPU: b'[MSC] CH = 0 BES[0] Crop [8 8 1280 720] FES output [1296 736]\n']
        ISPCPU: b'[MSC] CH = 0x0  BES[0] CROP -> [8, 8][1280, 720] within [0, 0][1296, 736]  original crop = [8 8 1280 720]\n']
        """
        s_cmd_ch_crop_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
            "unk_14" / Int32ul,
            "unk_18" / Int32ul,
            "unk_1c" / Int32ul,
        )
        args = s_cmd_ch_crop_set.build(dict(
                opcode=CISP_CMD_CH_CROP_SET,
                chan=0x0,
            unk_c=0x8,     # 8
            unk_10=0x8,    # 8
            unk_14=0x500,  # 1280
            unk_18=0x2d0,  # 720
            unk_1c=0x1,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x1c,
            outsize=0x1c,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_output_config_set(self):
        """
        00000000  00000000 00000b01 00000000 00000500 000002d0 00000001 00000000 00000500
        00000020  00000500 00000000 00000000 000002d0 00000000 00000500 00000000 00000000
        [MSC] CH = 0x0 Scl=0 Output Config: format=0,range=1,size=1280x720,paddingRows=0,cmpEn=0
        """
        s_cmd_ch_crop_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
            "unk_14" / Int32ul,
            "unk_18" / Int32ul,
            "unk_1c" / Int32ul,
            "unk_20" / Int32ul,
            "unk_24" / Int32ul,
            "unk_28" / Int32ul,
            "unk_2c" / Int32ul,
            "unk_30" / Int32ul,
            "unk_34" / Int32ul,
            "unk_38" / Int32ul,
        )
        args = s_cmd_ch_crop_set.build(dict(
                opcode=CISP_CMD_CH_OUTPUT_CONFIG_SET,
                chan=0x0,

            unk_c=0x500,
            unk_10=0x2d0,
            unk_14=0x1,
            unk_18=0x0,

            unk_1c=0x500,
            unk_20=0x500,
            unk_24=0x0,
            unk_28=0x0,

            unk_2c=0x2d0,
            unk_30=0x0,
            unk_34=0x500,
            unk_38=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x38,
            outsize=0x38,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_preview_stream_set(self):
        # [MSC] CH = 0x0   Preview stream set = 1
        s_cmd_ch_preview_stream_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
        )
        args = s_cmd_ch_preview_stream_set.build(dict(
                opcode=CISP_CMD_CH_PREVIEW_STREAM_SET,
                chan=0x0,
            unk_c=0x1,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x10,
            outsize=0x10,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_cnr_start(self):
        s_cmd_ch_cnr_start = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
        )
        args = s_cmd_ch_cnr_start.build(dict(
                opcode=CISP_CMD_CH_CNR_START,
                chan=0x0,
            unk_c=0x1,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xc,
            outsize=0xc,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_mbnr_enable(self):
        """
        00000000  00000000 00000a3a 00000000 00000000 00000001 00000001
        ISPCPU: [MSC] CH = 0, mbnrMode = 1,useCase = 0, enableChroma = 1
        """
        s_cmd_ch_mbnr_enable = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
            "unk_14" / Int32ul,
        )
        args = s_cmd_ch_mbnr_enable.build(dict(
                opcode=CISP_CMD_CH_MBNR_ENABLE,
                chan=0x0,
            unk_c=0x0,
            unk_10=0x1,
            unk_14=0x1,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x18,
            outsize=0x18,
            args=args,
        )
        return self.send(cmd)

    def cmd_apple_ch_temporal_filter_start(self):
        """
        00000000  00000000 0000c100 00000000 00000001 00000000 00000001 00000000 00000500
        [MSC] CH = 0x0   bMSTFScale0En=1, fusionType=0, isStreaming=0
        """
        s_cmd_apple_ch_temporal_filter_start = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
            "unk_14" / Int32ul,
        )
        args = s_cmd_apple_ch_temporal_filter_start.build(dict(
                opcode=CISP_CMD_APPLE_CH_TEMPORAL_FILTER_START,
                chan=0x0,
            unk_c=0x1,
            unk_10=0x0,
            unk_14=0x1,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x14,
            outsize=0x14,
            args=args,
        )
        return self.send(cmd)

    def cmd_apple_ch_motion_history_start(self):
        s_cmd_apple_ch_motion_history_start = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
        )
        args = s_cmd_apple_ch_motion_history_start.build(dict(
                opcode=CISP_CMD_APPLE_CH_MOTION_HISTORY_START,
                chan=0x0,
            unk_c=0x1,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xc,
            outsize=0xc,
            args=args,
        )
        return self.send(cmd)

    def cmd_apple_ch_temporal_filter_enable(self):
        s_cmd_apple_ch_temporal_filter_enable = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
        )
        args = s_cmd_apple_ch_temporal_filter_enable.build(dict(
                opcode=CISP_CMD_APPLE_CH_TEMPORAL_FILTER_ENABLE,
                chan=0x0,
            unk_c=0x1,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xc,
            outsize=0xc,
            args=args,
        )
        return self.send(cmd)

    def cmd_apple_ch_ae_fd_scene_metering_config_set(self):
        """
        00000000  00000000 0000820e 00000000 000000b8 02000200 00280800 00e10028 000a0399
        00000020  03cc02cc 00000000 00000000 000002d0 00000000 00000500 00000000 00000000
        ISPCPU: scene: T=184 low/hiK:0/512 sc:512..2048 outl:40,40 Q:10,716,972
        ISPCPU: face: T:225 maxFW:921
        """
        s_cmd_apple_ch_ae_fd_scene_metering_config_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
            "unk_14" / Int32ul,
            "unk_18" / Int32ul,
            "unk_1c" / Int32ul,
            "unk_20" / Int32ul,
            "unk_24" / Int32ul,
            "unk_28" / Int32ul,
        )
        args = s_cmd_apple_ch_ae_fd_scene_metering_config_set.build(dict(
                opcode=CISP_CMD_APPLE_CH_AE_FD_SCENE_METERING_CONFIG_SET,
                chan=0x0,
            unk_c=0xb8,
            unk_10=0x2000200,
            unk_14=0x280800,
            unk_18=0xe10028,
            unk_1c=0xa0399,
            unk_20=0x3cc02cc,
            unk_24=0x0,
            unk_28=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x24,
            outsize=0x24,
            args=args,
        )
        return self.send(cmd)

    def cmd_apple_ch_ae_metering_mode_set(self):
        s_cmd_apple_ch_ae_metering_mode_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "mode" / Int32ul,
        )
        args = s_cmd_apple_ch_ae_metering_mode_set.build(dict(
                opcode=CISP_CMD_APPLE_CH_AE_METERING_MODE_SET,
                chan=0x0,
            mode=0x3,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x10,
            outsize=0x10,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_ae_stability_set(self):
        s_cmd_ch_ae_stability_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "stability" / Int32ul,
        )
        args = s_cmd_ch_ae_stability_set.build(dict(
                opcode=CISP_CMD_CH_AE_STABILITY_SET,
                chan=0x0,
            stability=0x20,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x10,
            outsize=0x10,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_ae_stability_to_stable_set(self):
        s_cmd_ch_ae_stability_to_stable_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "stability" / Int32ul,
        )
        args = s_cmd_ch_ae_stability_to_stable_set.build(dict(
                opcode=CISP_CMD_CH_AE_STABILITY_TO_STABLE_SET,
                chan=0x0,
            stability=0x14,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x10,
            outsize=0x10,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_sif_pixel_format_set(self):
        """
        00000000  00000000 00000115 00000000 00000103 00000000
        [MSC] CH = 0x0   Sif Pixel Format3, type 1 DmaCompress 0 Companding 0
        """
        s_cmd_ch_sif_pixel_format_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
        )
        args = s_cmd_ch_sif_pixel_format_set.build(dict(
                opcode=CISP_CMD_CH_SIF_PIXEL_FORMAT_SET,
                chan=0x0,
            unk_c=0x103,
            unk_10=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x14,
            outsize=0x14,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_face_detection_config_get(self):
        s_cmd_ch_face_detection_config_get = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
            "unk_14" / Int32ul,
            "unk_18" / Int32ul,
        )
        args = s_cmd_ch_face_detection_config_get.build(dict(
                opcode=CISP_CMD_CH_FACE_DETECTION_CONFIG_GET,
                chan=0x0,
            unk_c=0x103,
            unk_10=0x0,
            unk_14=0x0,
            unk_18=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x1c,
            outsize=0x1c,
            args=args,
        )
        def cb(): chexdump32(self.isp.ioread(self.cmd_iova, 0x20))
        """
        00000000  00000000 00000d02 00000000 00000000 0000000a 0000000a 00000000 00000000
        """
        return self.send(cmd, cb=cb)

    def cmd_ch_face_detection_config_set(self):
        """
        00000000  00000000 00000d03 00000000 0000000a 01000000 00000001
        MSG: : FDConfig Eye 0 Blink 0 Smile 0 nFace 10
        CISP_CMD_CH_FACE_DETECTION_CONFIG_SET enableAttr = 0
        enableOd = 0
        enableSaliency = 0, enableSaliencyHW = 1
        """
        s_cmd_ch_face_detection_config_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
            "unk_14" / Int32ul,
        )
        args = s_cmd_ch_face_detection_config_set.build(dict(
                opcode=CISP_CMD_CH_FACE_DETECTION_CONFIG_SET,
                chan=0x0,
            unk_c=0xa,
            unk_10=0x1000000,
            unk_14=0x1,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x18,
            outsize=0x18,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_face_detection_enable(self):
        s_cmd_ch_face_detection_enable = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "FDEnableMask" / Int32ul,
        )
        args = s_cmd_ch_face_detection_enable.build(dict(
                opcode=CISP_CMD_CH_FACE_DETECTION_ENABLE,
                chan=0x0,
            FDEnableMask=0x1,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x10,
            outsize=0x10,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_face_detection_start(self):
        s_cmd_ch_face_detection_start = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
        )
        args = s_cmd_ch_face_detection_start.build(dict(
                opcode=CISP_CMD_CH_FACE_DETECTION_START,
                chan=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xc,
            outsize=0xc,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_camera_config_current_get(self):
        s_cmd_ch_camera_config_current_get = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
            "unk_10" / Int32ul,
            "unk_14" / Int32ul,
            "unk_18" / Int32ul,
        )
        args = s_cmd_ch_camera_config_current_get.build(dict(
                opcode=CISP_CMD_CH_CAMERA_CONFIG_CURRENT_GET,
                chan=0x0,
            unk_c=0x0,
            unk_10=0x0,
            unk_14=0x0,
            unk_18=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xdc,
            outsize=0xdc,
            args=args,
        )
        def cb(): chexdump32(self.isp.ioread(self.cmd_iova, 0xe0))
        """
        00000000  00000000 00000105 00000000 00000000 02e00510 02e00510 00000000 00001df8
        00000020  00000100 00000001 00000040 00000040 00000040 00000040 00000040 00000040
        00000040  00000003 00000040 00000040 00000005 00000000 00000528 00000001 00000000
        00000060  0249f000 00000006 00000007 00000000 00000009 000f4240 00000025 00000000
        00000080  00004000 00000014 00000015 00000000 00000000 00000000 00000510 000002e0
        000000a0  00010000 00000000 00000000 00000000 0000001f 00000000 00000000 00000000
        000000c0  00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
        """
        return self.send(cmd, cb=cb)

    def cmd_ch_ae_frame_rate_max_set(self):
        # TODO IMPORTANT DONT FORGET EILEEN !!!!!!!!!!!
        # Normal framerate set by macos is 0x1e00 for both min/max.
        # Since m1n1 is too slow to keep up, temporarily using 1/8th, 0x3c0
        s_cmd_ch_ae_frame_rate_max_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
        )
        args = s_cmd_ch_ae_frame_rate_max_set.build(dict(
                opcode=CISP_CMD_CH_AE_FRAME_RATE_MAX_SET,
                chan=0x0,
            unk_c=0x3c0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x10,
            outsize=0x10,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_ae_frame_rate_min_set(self):
        s_cmd_ch_ae_frame_rate_min_set = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
            "unk_c" / Int32ul,
        )
        args = s_cmd_ch_ae_frame_rate_min_set.build(dict(
                opcode=CISP_CMD_CH_AE_FRAME_RATE_MIN_SET,
                chan=0x0,
            unk_c=0x3c0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0x10,
            outsize=0x10,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_start(self):  # green light :)
        s_cmd_ch_start = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
        )
        args = s_cmd_ch_start.build(dict(
                opcode=CISP_CMD_CH_START,
                chan=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xc,
            outsize=0xc,
            args=args,
        )
        return self.send(cmd)

    def cmd_ch_stop(self):  # no more green light
        s_cmd_ch_stop = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "chan" / Int32ul,
        )
        args = s_cmd_ch_stop.build(dict(
                opcode=CISP_CMD_CH_STOP,
                chan=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xc,
            outsize=0xc,
            args=args,
        )
        return self.send(cmd)

    def cmd_stop(self):
        s_cmd_stop = Struct(
                "pad" / Default(Int32ul, 0),
                "opcode" / Int32ul,
                "unk_c" / Int32ul,
        )
        args = s_cmd_stop.build(dict(
                opcode=CISP_CMD_STOP,
                unk_c=0x0,
        ))
        cmd = ISPIORequestCommand(
            iova=self.cmd_iova,
            insize=0xc,
            outsize=0xc,
            args=args,
        )
        return self.send(cmd)

# SPDX-License-Identifier: MIT
from ..common import Padding
from construct import *
import cv2
import datetime
import numpy as np
import struct
import _thread

from .isp_cmd import ISPIOCommandDispatcher

ISPFrameMeta = Struct(
        "unk_0" / Hex(Int32ul),
        "pad" / Default(Int32ul, 0),
        "unk_8" / Hex(Int32ul),
        "pad" / Default(Int32ul, 0),

        "meta_iova" / Hex(Int32ul),
        "pad" / Default(Int32ul, 0),
        "pad" / Default(Int32ul, 0),
        "pad" / Default(Int32ul, 0),

        "pad" / Padding(0x10),

        "unk_30" / Hex(Int32ul),
        "pad" / Default(Int32ul, 0),
        "pad" / Default(Int32ul, 0),
        "pad" / Default(Int32ul, 0),

        "unk_40" / Hex(Int32ul),
        "pad" / Default(Int32ul, 0),
        "unk_48" / Hex(Int32ul),
        "pad" / Default(Int32ul, 0),

        "luma_iova" / Hex(Int32ul),
        "pad" / Default(Int32ul, 0),
        "cbcr_iova" / Hex(Int32ul),
        "pad" / Default(Int32ul, 0),

        "pad" / Padding(0x20),

        "unk_80" / Hex(Int32ul),
        "unk_84" / Hex(Int32ul),
        "unk_88" / Hex(Int32ul),
        "pad" / Default(Int32ul, 0),

        "pad" / Padding(0x30),
    "pad" / Padding(0x140),

    "pad" / Padding(0x10),

        "unk_210" / Hex(Int32ul),
        "pad" / Default(Int32ul, 0),
        "index" / Hex(Int32ul),
        "unk_21c" / Hex(Int32ul),

        "unk_220" / Hex(Int32ul),
        "pad" / Default(Int32ul, 0),
        "pad" / Default(Int32ul, 0),
        "pad" / Default(Int32ul, 0),

        "unk_230" / Hex(Int32ul),
        "unk_234" / Hex(Int32ul),
        "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),

        "pad" / Padding(0x40),
)
assert((ISPFrameMeta.sizeof() == 0x280))


class ISPFrame:
    def __init__(self, isp, req):
        self.isp = isp
        self.height = 720
        self.width = 1280
        self.meta_size = 0x4640
        self.luma_size = self.height * self.width       # 1280 * 720; 921600; 0xe1000
        self.cbcr_size = self.height * self.width // 2  # 1280 * 360; 460800; 0x70800

        assert((req.arg1 == 0x280))
        x = ISPFrameMeta.parse(self.isp.ioread(req.arg0, req.arg1))
        self.meta_iova = x.meta_iova
        self.luma_iova = x.luma_iova
        self.cbcr_iova = x.cbcr_iova
        self.index = x.index

        self.luma_data = self.isp.ioread(self.luma_iova, self.luma_size)
        self.cbcr_data = self.isp.ioread(self.cbcr_iova, self.cbcr_size)

        self.timestamp = datetime.datetime.now()

    def to_bgr(self):  # TODO
        y = np.frombuffer(self.luma_data[:1280*360*2], dtype=np.uint8).reshape((720, 1280))
        cbcr = np.frombuffer(self.cbcr_data[:1280*360*1], dtype=np.uint8).reshape((360, 1280))
        u = cv2.resize(cbcr[:,::2], (1280, 720))
        v = cv2.resize(cbcr[:,1::2], (1280, 720))
        yuv = np.stack((y, u, v), axis=-1)
        bgr = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
        return bgr

    def process(self):
        bgr = self.to_bgr()
        mirrored = bgr[:,::-1,:].copy()
        s = "Frame %d: %s" % (self.index, str(self.timestamp))
        cv2.putText(mirrored, s, (10, self.height - 20), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0,255,0), 1, cv2.LINE_AA)
        return mirrored

    def __str__(self):
        s = "Frame %d: [luma: 0x%x cbcr: 0x%x] at %s" % (self.index, self.luma_iova, self.cbcr_iova, self.timestamp.strftime('%H:%M:%S.%f'))
        return s


BufH2TSendArgsHeader = Struct(
    "unk_0" / Int32ul,
    "pad" / Default(Int32ul, 0),
        "batch" / Int32ul,
    "pad" / Default(Int32ul, 0),
)

BufH2TSendArgs = Struct(
    "iova0" / Int32ul,
    "pad" / Default(Int32ul, 0),
        "iova1" / Int32ul,
    "pad" / Default(Int32ul, 0),
        "pad" / Padding(0x10),
    "flag0" / Int32ul,
        "flag1" / Int32ul,
    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),
    "unk_30" / Int32ul,
        "pool" / Int32ul,
    "tag" / Int32ul,
    "pad" / Default(Int32ul, 0),
)
assert((BufH2TSendArgs.sizeof() == 0x40))


class ISPBufH2TBuffer:
    def __init__(self, surf0, surf1, buftype, index, args):
        self.surf0 = surf0
        self.surf1 = surf1
        self.buftype = buftype
        self.index = index
        self.args = args


class ISPBufH2TPool:
    def __init__(self, isp, bufs, header):
        self.isp = isp
        self.bufs = bufs
        self.args = header + b''.join([buf.args for buf in self.bufs])

    @classmethod
    def meta_pool(cls, isp, batch=2):
        bufs = []
        for n in range(10):
            bufs.append(cls.make_metabuf(isp, n))
        header = BufH2TSendArgsHeader.build(dict(
            unk_0=0x1,
            batch=batch,
        ))
        return cls(isp, bufs, header)

    @classmethod
    def yuv_pool(cls, isp, batch=2):
        bufs = []
        for n in range(batch):
            bufs.append(cls.make_yuvbuf(isp, n))
        for n in range(10-batch):
            bufs.append(cls.make_unkbuf(isp, n+batch))

        header = BufH2TSendArgsHeader.build(dict(
            unk_0=0x1,
            batch=batch,
        ))
        return cls(isp, bufs, header)

    @staticmethod
    def make_metabuf(isp, index):
        # CImageCaptureCore.cpp, 4788: FrontRGB: Cannot get host meta buffer, dropping frame #2
        # (461): ISPASC: WRN: ./h10isp/filters/IC/CImageCaptureCore.cpp, 4997: FrontRGB: Host metadata unavailable.
        # AppleH13CamIn::ISP_SendBuffers_gated - h2tBuf: pool=0, tag=0x13f, addr=0x056A8000, len=17984
        # 056a8000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
        # 40000000 00000000 00000000 00000000 00000001 00000000 0000013f 00000000
        surf = isp.mmger.alloc_size(0x4640, name="META")  # 17984
        args = BufH2TSendArgs.build(dict(
                iova0=surf.iova,
            iova1=0x0,
                flag0=0x40000000,
            flag1=0x0,
            unk_30=0x1,
            pool=0x0,
            tag=surf.index,
        ))
        return ISPBufH2TBuffer(surf0=surf, surf1=None, buftype=0, index=index, args=args)

    @staticmethod
    def make_yuvbuf(isp, index):
        # FLOW ERR: ./h10isp/filters/Flow/H13/CVideoFlowH13.cpp, 5351: flow=0, ch=0 can't get output yuv buf, dropped frame=0 (1) 0
        # AppleH13CamIn::ISP_SendBuffers_gated - h2tBuf: pool=1, tag=0x16e, addr0=0x0754C040, len0=921600, addr1=0x0762D040, len1=460800
        # 0754c040 00000000 0762d040 00000000 00000000 00000000 00000000 00000000
        # 40000000 40000000 00000000 00000000 00000002 00000001 0000016e 00000000
        surf0 = isp.mmger.alloc_size(0xe1000, name="LUMA")  # 921600; 1280 * 720
        surf1 = isp.mmger.alloc_size(0x70800, name="CBCR")  # 460800; 1280 * 360
        args = BufH2TSendArgs.build(dict(
                iova0=surf0.iova,
            iova1=surf1.iova,
                flag0=0x40000000,
            flag1=0x40000000,
            unk_30=0x2,
            pool=0x1,
            tag=surf0.index,
        ))
        return ISPBufH2TBuffer(surf0=surf0, surf1=surf1, buftype=1, index=index, args=args)

    @staticmethod
    def make_unkbuf(isp, index):
        # AppleH13CamIn::ISP_SendBuffers_gated - h2tBuf: pool=2, tag=0x165, addr=0x074F8000, len=16960
        # 074f8000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
        # 40000000 00000000 00000000 00000000 00000001 00000002 00000165 00000000
        surf = isp.mmger.alloc_size(0x4240, name="UNK")  # 16960
        args = BufH2TSendArgs.build(dict(
                iova0=surf.iova,
            iova1=0x0,
                flag0=0x40000000,
            flag1=0x0,
            unk_30=0x1,
            pool=0x2,
            tag=surf.index,
        ))
        return ISPBufH2TBuffer(surf0=surf, surf1=None, buftype=2, index=index, args=args)

    def send(self):
        # TX: REQ: [0x1813140, 0x280, 0x30000000]  # iova, size, flag
        # RX: RSP: [0x1813141, 0x000, 0x80000000]  # iova, zero, flag
        req = ISPChannelMessage.build(
            arg0 = self.isp.cmd_iova,  # iova
            arg1 = 0x280,  # size
            arg2 = 0x30000000,  # FFW_INTERPROC_BUFF_EXCHANGE_FLAG_CHECK
        )
        # print("CHAN: BR: TX: REQ: [iova: 0x%x, size: 0x%x, flag: 0x%x]" % (req.arg0, req.arg1, req.arg2))
        self.isp.iowrite(req.arg0, self.args)
        rsp = self.isp.table.bufh2t.send(req)
        if (rsp == None):
            self.isp.table.dump()
            raise RuntimeError("failed to send buf")
        return rsp


class ISPFrameReceiver:
    def __init__(self, isp, batch=2):
        assert((batch <= 10))
        self.isp = isp
        self.meta_pool = ISPBufH2TPool.meta_pool(self.isp, batch)
        self.yuv_pool = ISPBufH2TPool.yuv_pool(self.isp, batch)
        self.dp = ISPIOCommandDispatcher(self.isp)

    def work(self):
        self.yuv_pool.send()
        self.isp.table.buft2h.handler()
        self.meta_pool.send()
        self.isp.table.buft2h.handler()

    @staticmethod
    def input_thread(a_list):  # https://stackoverflow.com/a/25442391
        input()
        a_list.append(True)

    def work_loop(self):
        # self.meta_pool.send()  # sent ahead of time
        a_list = []
        _thread.start_new_thread(self.input_thread, (a_list,))
        while not a_list:
            self.work()

    def stream(self):
        print("Kicking up hardware...")
        self.ch_start()
        print("Starting stream...")
        self.work_loop()
        cv2.destroyAllWindows()
        print("Ended stream.")
        self.ch_stop()
        print("Powered down hardware.")

    def ch_start(self):
        dp = self.dp
        dp.cmd_print_enable()
        dp.cmd_trace_enable()

        dp.cmd_set_isp_pmu_base()
        dp.cmd_set_dsid_clr_req_base2()
        dp.cmd_pmp_ctrl_set()
        dp.cmd_start()

        dp.cmd_ch_camera_config_select()
        dp.cmd_ch_sbs_enable()

        dp.cmd_ch_crop_set()
        dp.cmd_ch_output_config_set()
        dp.cmd_ch_preview_stream_set()

        dp.cmd_ch_cnr_start()
        dp.cmd_ch_mbnr_enable()

        dp.cmd_apple_ch_temporal_filter_start()
        dp.cmd_apple_ch_motion_history_start()
        dp.cmd_apple_ch_temporal_filter_enable()
        dp.cmd_apple_ch_ae_fd_scene_metering_config_set()
        dp.cmd_apple_ch_ae_metering_mode_set()
        dp.cmd_ch_ae_stability_set()
        dp.cmd_ch_ae_stability_to_stable_set()

        dp.cmd_ch_sif_pixel_format_set()
        #dp.cmd_ch_buffer_recycle_mode_set()
        #dp.cmd_ch_buffer_recycle_start()

        dp.cmd_ch_ae_frame_rate_max_set()
        dp.cmd_ch_ae_frame_rate_min_set()
        dp.cmd_ch_buffer_pool_config_set()

        # call right before cmd_ch_start() as to not drop start frames
        self.meta_pool.send()
        dp.cmd_ch_start()

    def ch_stop(self):
        dp = self.dp
        dp.cmd_ch_buffer_recycle_stop()
        dp.cmd_ch_stop()
        dp.cmd_stop()

# SPDX-License-Identifier: MIT
import cv2
import numpy as np
import time
import os

MAX_TRIES = 100
def round_up(x, y): return ((x + (y - 1)) & (-y))
def round_down(x, y): return (x - (x % y))

class AVDFrame:
    def __init__(self, img, sl, y_data, uv_data):
        self.img = img
        self.sl = sl
        self.y_data = y_data
        self.uv_data = uv_data

class AVDDec:
    def __init__(self, avd):
        self.avd = avd
        self.frames = []
        self.last_poc = -1
        self.winname = "img"
        self.count = 0

    def log(self, x):
        return self.avd.log(x)

    def setup_dma(self, ctx, sl):
        avd_w32 = self.avd.avd_w32; avd_r32 = self.avd.avd_r32
        #self.avd.avd_dma_tunables_stage0()
        assert((ctx.inst_fifo_idx >= 0) and (ctx.inst_fifo_idx < ctx.inst_fifo_count))
        avd_w32(0x1104068 + (ctx.inst_fifo_idx * 0x4), ctx.inst_fifo_iova >> 8)
        avd_w32(0x1104084 + (ctx.inst_fifo_idx * 0x4), 0x100000)
        avd_w32(0x11040a0 + (ctx.inst_fifo_idx * 0x4), 0x0)
        avd_w32(0x11040bc + (ctx.inst_fifo_idx * 0x4), 0x0)
        if (sl.mode == "h265"):
            x = 0x7
            avd_w32(0x1104040, 0x0)
        if (sl.mode == "h264"):
            x = 0x1c00
            avd_w32(0x1104048, 0x0)
        if (sl.mode == "vp09"):
            x = 0x38000
            avd_w32(0x110404c, 0x0)
        avd_w32(0x110405c, avd_r32(0x110405c) | x)
        self.avd.poll()

    def get_nv12_disp_frame(self, ctx, sl, r=2):
        w = round_up(ctx.orig_width, 16)
        h = round_up(ctx.orig_height, 16)
        y_data = self.avd.ioread(ctx.y_addr & 0xffffff00, w * h, stream=0)
        y = np.frombuffer(y_data, dtype=np.uint8).reshape((h, w))
        uv_data = self.avd.ioread(ctx.uv_addr & 0xffffff00, w * (h // 2), stream=0)
        uv = np.frombuffer(uv_data, dtype=np.uint8).reshape((h // 2, w))
        u2 = cv2.resize(uv[:,::2], (w, h), interpolation=cv2.INTER_AREA)
        v2 = cv2.resize(uv[:,1::2], (w, h), interpolation=cv2.INTER_AREA)
        yuv = np.stack((y, u2, v2), axis=-1)
        img = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)[:ctx.orig_height, :ctx.orig_width, :]
        return AVDFrame(img, sl, y_data, uv_data)

    def get_nv12_disp_frame2(self, ctx, sl):
        fmt = ctx.fmt
        w = fmt.in_width
        h = fmt.in_height
        y_data = self.avd.ioread(ctx.y_addr & 0xffffff00, w * h, stream=0)
        y = np.frombuffer(y_data, dtype=np.uint8).reshape((h, w))
        if (fmt.chroma <= 1):
            ch = h // 2
        elif (fmt.chroma == 2):
            ch = h
        uv_data = self.avd.ioread(ctx.uv_addr & 0xffffff00, w * ch, stream=0)
        uv = np.frombuffer(uv_data, dtype=np.uint8).reshape((ch, w))
        u2 = cv2.resize(uv[:,::2], (w, h), interpolation=cv2.INTER_AREA)
        v2 = cv2.resize(uv[:,1::2], (w, h), interpolation=cv2.INTER_AREA)
        yuv = np.stack((y, u2, v2), axis=-1)
        img = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)[fmt.y0:fmt.y1, fmt.x0:fmt.x1,:]
        return AVDFrame(img, sl, y_data, uv_data)

    def set_insn(self, x):
        raise ValueError()

    def set_payload(self, ctx, sl):
        self.avd.iowrite(ctx.slice_data_addr, sl.get_payload(), stream=0)
        self.avd.iomon.poll()

    def get_disp_frame(self, ctx, sl):
        raise ValueError()

    def display(self, frame):
        cv2.imshow(self.winname, frame.img); cv2.waitKey(1)
        if (frame.sl.mode == "h264") or (frame.sl.mode == "h265"):
            self.last_poc = frame.sl.pic.poc
        else:
            self.last_poc = 0
        self.frames = [f for f in self.frames if f != frame]
        self.count += 1

    def select_disp_frame(self, ctx, sl):
        return self.frames[0]

    def decode(self, ctx, sl, inst_stream):
        if not inst_stream: return
        self.set_payload(ctx, sl)
        self.setup_dma(ctx, sl)
        for x in inst_stream:
            v = x if isinstance(x, int) else x.val
            self.set_insn(v)
        self.get_disp_frame(ctx, sl)
        assert(self.avd.avd_r32(0x1104060) == 0x2842108)
        if (hasattr(ctx, "fmt")):
            frame = self.get_nv12_disp_frame2(ctx, sl)
        else:
            frame = self.get_nv12_disp_frame(ctx, sl)
        self.frames.append(frame)
        frame = self.select_disp_frame(ctx, sl)
        if (frame != None):
            self.display(frame)
        return frame

class AVDH265Dec(AVDDec):
    def __init__(self, avd):
        super().__init__(avd)

    def set_insn(self, x):
        self.avd.avd_w32(0x1104004, x)

    def set_payload(self, ctx, sl):
        self.avd.iowrite(sl.payload_addr, sl.get_payload(), stream=0)
        for seg in sl.slices:
            self.avd.iowrite(seg.payload_addr, seg.get_payload(), stream=0)
        self.avd.iomon.poll()

    def get_disp_frame(self, ctx, sl):
        avd_w32 = self.avd.avd_w32; avd_r32 = self.avd.avd_r32
        avd_w32(0x1104014, 0x2b000100 | ctx.inst_fifo_idx * 0x10 | 7)
        if (ctx.pos > 1):
            for n in range(ctx.pos - 1):
                avd_w32(0x1104014, 0x2b000000 | ctx.inst_fifo_idx * 0x10 | 7)
        self.avd.poll(); self.avd.iomon.poll()

        for n in range(MAX_TRIES):
            status = avd_r32(0x1104060)
            if (status & 0xc00000 == 0xc00000): # 0x2c4210c -> 0x2c4210c
                break
            self.log("[H265] status: 0x%x" % (status))
            if (n >= MAX_TRIES - 1): raise RuntimeError("error")
        avd_w32(0x1104060, 0x4)

        for n in range(MAX_TRIES):
            status = avd_r32(0x1104060)
            if (status & 0x3000 == 0x2000): # 0x2c4210c -> 0x2c42108
                break
            self.log("[H265] status: 0x%x" % (status))
            if (n >= MAX_TRIES - 1): raise RuntimeError("error")
        avd_w32(0x1104060, 0x400000)  # 0x2c42108 -> 0x2842108
        self.avd.poll(); self.avd.iomon.poll()

    def select_disp_frame(self, ctx, sl):
        dpb_size = ctx.vps_list[0].vps_max_num_reorder_pics + 1
        if (len(self.frames) >= dpb_size):
            frames = [f for f in self.frames if f.sl.pic.poc == self.last_poc + 1]
            if (len(frames) == 1):
                    return frames[0]
            frames = sorted(self.frames, key=lambda f: (f.sl.pic.poc))
            return frames[0]
        return None

class AVDH264Dec(AVDDec):
    def __init__(self, avd):
        super().__init__(avd)

    def set_insn(self, x):
        self.avd.avd_w32(0x110400c, x)

    def set_payload(self, ctx, sl):
        self.avd.iowrite(ctx.slice_data_addr, sl.get_payload(), stream=0)
        self.avd.iomon.poll()

    def get_disp_frame(self, ctx, sl):
        avd_w32 = self.avd.avd_w32; avd_r32 = self.avd.avd_r32
        avd_w32(0x1104014, 0x2b000100 | (ctx.inst_fifo_idx * 0x10) | 7)
        self.avd.poll(); self.avd.iomon.poll()

        for n in range(MAX_TRIES):
            status = avd_r32(0x1104060)
            if (status & 0xc00000 == 0xc00000): # 0x2843108 -> 0x2c43108
                break
            self.log("[H264] status: 0x%x" % (status))
            if (n >= MAX_TRIES - 1): raise RuntimeError("error")
        avd_w32(0x1104060, 0x1000)

        for n in range(MAX_TRIES):
            status = avd_r32(0x1104060)
            if (status & 0x3000 == 0x2000): # 0x2c43108 -> 0x2c42108
                break
            self.log("[H264] status: 0x%x" % (status))
            if (n >= MAX_TRIES - 1): raise RuntimeError("error")
        avd_w32(0x1104060, 0x400000)  # 0x2c42108 -> 0x2842108
        self.avd.poll(); self.avd.iomon.poll()

    def select_disp_frame(self, ctx, sl):
        dpb_size = ctx.num_reorder_frames
        if (len(self.frames) >= dpb_size):
                frames = [f for f in self.frames if f.sl.pic.poc == self.last_poc + 2]
                if (len(frames) == 1):
                    return frames[0]
                    return
                frames = sorted(self.frames, key=lambda f: (f.sl.pic.poc))
                return frames[0]
        return None

class AVDVP9Dec(AVDDec):
    def __init__(self, avd):
        super().__init__(avd)

    def set_insn(self, x):
        self.avd.avd_w32(0x1104010, x)

    def set_payload(self, ctx, sl):
        self.avd.iowrite(ctx.slice_data_addr, sl.get_payload(), stream=0)
        self.avd.iowrite(ctx.probs_addr, sl.get_probs(), stream=0)
        self.avd.iomon.poll()

    def get_disp_frame(self, ctx, sl):
        avd_w32 = self.avd.avd_w32; avd_r32 = self.avd.avd_r32
        avd_w32(0x1104014, 0x2bfff100 | (ctx.inst_fifo_idx * 0x10) | 7)
        if (len(sl.tiles) > 1):
            for n in range(len(sl.tiles) - 1):
                avd_w32(0x1104014, 0x2bfff000 | (ctx.inst_fifo_idx * 0x10) | 7)
        self.avd.poll(); self.avd.iomon.poll()

        for n in range(MAX_TRIES):
            status = avd_r32(0x1104060)
            if (status & 0xc00000 == 0xc00000): # 0x2862108 -> 0x2c62108
                break
            self.log("[VP9] status: 0x%x" % (status))
            if (n >= MAX_TRIES - 1):
                raise RuntimeError("error")
        avd_w32(0x1104060, 0x20000)

        for n in range(MAX_TRIES):
            status = avd_r32(0x1104060)
            if (status & 0x3000 == 0x2000): # 0x2c62108 -> 0x2c42108
                break
            self.log("[VP9] status: 0x%x" % (status))
            if (n >= MAX_TRIES - 1):
                raise RuntimeError("error")
        avd_w32(0x1104060, 0x400000)  # 0x2c42108 -> 0x2842108
        self.avd.poll(); self.avd.iomon.poll()

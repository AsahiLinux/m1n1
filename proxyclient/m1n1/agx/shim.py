#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import errno, ctypes, sys, atexit, os, os.path
from construct import *

from m1n1 import malloc
from m1n1.utils import Register32
from m1n1.agx import AGX
from m1n1.agx.render import *
from m1n1.agx.uapi import *
from m1n1.proxyutils import *
from m1n1.utils import *

PAGE_SIZE = 32768
SHIM_MEM_SIZE = 4 * 1024 * 1024 * 1024

class IOCTL(Register32):
    NR = 7, 0
    TYPE = 15, 8
    SIZE = 29, 16
    DIR = 31, 30

_IOC_NONE = 0
_IOC_WRITE = 1
_IOC_READ = 2

_IO = lambda type, nr: IOCTL(TYPE=type, NR=nr, SIZE=0, DIR=_IOC_NONE)
_IOR = lambda type, nr, size: IOCTL(TYPE=type, NR=nr, SIZE=size, DIR=_IOC_READ)
_IOW = lambda type, nr, size: IOCTL(TYPE=type, NR=nr, SIZE=size, DIR=_IOC_WRITE)
_IOWR = lambda type, nr, size: IOCTL(TYPE=type, NR=nr, SIZE=size, DIR=_IOC_READ|_IOC_WRITE)

DRM_IOCTL_BASE = ord('d')

def IO(nr):
    def dec(f):
        f._ioctl = _IO(DRM_IOCTL_BASE, nr)
        return f
    return dec

def IOR(nr, cls):
    def dec(f):
        f._ioctl = _IOR(DRM_IOCTL_BASE, nr, cls.sizeof())
        f._arg_cls = cls
        return f
    return dec

def IOW(nr, cls):
    def dec(f):
        f._ioctl = _IOW(DRM_IOCTL_BASE, nr, cls.sizeof())
        f._arg_cls = cls
        return f
    return dec

def IOWR(nr, cls):
    def dec(f):
        f._ioctl = _IOWR(DRM_IOCTL_BASE, nr, cls.sizeof())
        f._arg_cls = cls
        return f
    return dec

class DRMAsahiShim:
    def __init__(self, memfd):
        self.memfd = open(memfd, closefd=False, mode="r+b")
        self.initialized = False
        self.ioctl_map = {}
        for key in dir(self):
            f = getattr(self, key)
            ioctl = getattr(f, "_ioctl", None)
            if ioctl is not None:
                self.ioctl_map[ioctl.value] = ioctl, f
        self.bos = {}
        self.pull_buffers = False

    def read_buf(self, ptr, size):
        return ctypes.cast(ptr, ctypes.POINTER(ctypes.c_ubyte * size))[0]

    def init_agx(self):
        from m1n1.setup import p, u, iface

        p.pmgr_adt_clocks_enable("/arm-io/gfx-asc")
        p.pmgr_adt_clocks_enable("/arm-io/sgx")

        self.agx = agx = AGX(u)

        mon = RegMonitor(u, ascii=True, bufsize=0x8000000)
        agx.mon = mon

        sgx = agx.sgx_dev
        #mon.add(sgx.gpu_region_base, sgx.gpu_region_size, "contexts")
        #mon.add(sgx.gfx_shared_region_base, sgx.gfx_shared_region_size, "gfx-shared")
        #mon.add(sgx.gfx_handoff_base, sgx.gfx_handoff_size, "gfx-handoff")

        #mon.add(agx.initdasgx.gfx_handoff_base, sgx.gfx_handoff_size, "gfx-handoff")

        atexit.register(p.reboot)
        agx.start()

    def init(self):
        if self.initialized:
            return

        self.init_agx()
        self.renderer = GPURenderer(self.agx)

        self.initialized = True

    @IOW(DRM_COMMAND_BASE + 0x00, drm_asahi_submit_t)
    def submit(self, fd, args):
        #print("Submit!")
        sys.stdout.write(".")
        sys.stdout.flush()

        size = drm_asahi_cmdbuf_t.sizeof()
        cmdbuf = drm_asahi_cmdbuf_t.parse(self.read_buf(args.cmdbuf, size))

        #print(cmdbuf)

        for obj in self.bos.values():
            self.memfd.seek(obj._memfd_offset)
            obj.val = self.memfd.read(obj._size)
            obj.push(True)

        self.renderer.submit(cmdbuf)
        self.renderer.run()
        self.renderer.wait()

        if self.pull_buffers:
            for i in cmdbuf.attachments:
                for obj in self.bos.values():
                    if obj._addr == i.pointer:
                        obj.pull()
                        self.memfd.seek(obj._memfd_offset)
                        self.memfd.write(obj.val)

        return 0

    @IOW(DRM_COMMAND_BASE + 0x01, drm_asahi_wait_bo_t)
    def wait_bo(self, fd, args):
        print("Wait BO!", args)
        return 0

    @IOWR(DRM_COMMAND_BASE + 0x02, drm_asahi_create_bo_t)
    def create_bo(self, fd, args):
        memfd_offset = args.offset

        if args.flags & ASAHI_BO_PIPELINE:
            alloc = self.renderer.ctx.pobj
        else:
            alloc = self.renderer.ctx.gobj

        obj = alloc.new(HexDump(Bytes(args.size)), name=f"GBM offset {memfd_offset:#x}", track=False)
        obj._memfd_offset = memfd_offset
        self.bos[memfd_offset] = obj
        args.offset = obj._addr

        if args.flags & ASAHI_BO_PIPELINE:
            args.offset -= self.renderer.ctx.pipeline_base

        print(f"Create BO @ {memfd_offset:#x}")
        return 0

    @IOWR(DRM_COMMAND_BASE + 0x04, drm_asahi_get_param_t)
    def get_param(self, fd, args):
        print("Get Param!", args)
        return 0

    @IOWR(DRM_COMMAND_BASE + 0x05, drm_asahi_get_bo_offset_t)
    def get_bo_offset(self, fd, args):
        print("Get BO Offset!", args)
        return 0

    def bo_free(self, memfd_offset):
        print(f"Free BO @ {memfd_offset:#x}")
        self.bos[memfd_offset].free()
        del self.bos[memfd_offset]

    def ioctl(self, fd, request, p_arg):
        self.init()

        p_arg = ctypes.c_void_p(p_arg)

        if request not in self.ioctl_map:
            print(f"Unknown ioctl: fd={fd} request={IOCTL(request)} arg={p_arg:#x}")
            return -errno.ENOSYS

        ioctl, f = self.ioctl_map[request]

        size = ioctl.SIZE
        if ioctl.DIR & _IOC_WRITE:
            args = f._arg_cls.parse(self.read_buf(p_arg, size))
            ret = f(fd, args)
        elif ioctl.DIR & _IOC_READ:
            args = f._arg_cls.parse(bytes(size))
            ret = f(fd, args)
        else:
            ret = f(fd)

        if ioctl.DIR & _IOC_READ:
            data = args.build()
            assert len(data) == size
            ctypes.memmove(p_arg, data, size)

        return ret

Shim = DRMAsahiShim

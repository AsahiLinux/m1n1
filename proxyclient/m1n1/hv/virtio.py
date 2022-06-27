# SPDX-License-Identifier: MIT
from construct import Struct, Int8ul, Int16ul, Int32sl, Int32ul, Int64ul
from subprocess import Popen, PIPE
import pathlib
import struct
import os
import sys

from ..utils import *

VirtioConfig = Struct(
    "irq" / Int32sl,
    "devid" / Int32ul,
    "feats" / Int64ul,
    "num_qus" / Int32ul,
    "data" / Int64ul,
    "data_len" / Int64ul,
    "verbose" / Int8ul,
)

class VirtioDescFlags(Register16):
    WRITE = 1
    NEXT  = 0

VirtioDesc = Struct(
    "addr" / Int64ul,
    "len" / Int32ul,
    "flags" / RegAdapter(VirtioDescFlags),
    "next" / Int16ul,
)

VirtioExcInfo = Struct(
    "devbase" / Int64ul,
    "qu" / Int16ul,
    "idx" / Int16ul,
    "pad" / Int32ul, 
    "descbase" / Int64ul,
)

class VirtioDev:
    def __init__(self):
        self.base, self.hv = None, None # assigned by HV object

    def read_buf(self, desc):
        return self.hv.iface.readmem(desc.addr, desc.len)

    def read_desc(self, ctx, idx):
        off = VirtioDesc.sizeof() * idx
        return self.hv.iface.readstruct(ctx.descbase + off, VirtioDesc)

    @property
    def config_data(self):
        return b""

    @property
    def devid(self):
        return 0

    @property
    def num_qus(self):
        return 1

    @property
    def feats(self):
        return 0

class Virtio9PTransport(VirtioDev):
    def __init__(self, tag="m1n1", root=None):
        p_stdin, self.fin = os.pipe()
        self.fout, p_stdout = os.pipe()
        if root is None:
            root = str(pathlib.Path(__file__).resolve().parents[3])
        if type(tag) is str:
            self.tag = tag.encode("ascii")
        else:
            self.tag = tag
        self.p = Popen([
            "u9fs",
            "-a", "none", # no auth
            "-n", # not a network conn
            "-u", os.getlogin(), # single user
            root,
        ], stdin=p_stdin, stdout=p_stdout, stderr=sys.stderr)

    @property
    def config_data(self):
        return struct.pack("=H", len(self.tag)) + self.tag

    @property
    def devid(self):
        return 9

    @property
    def num_qus(self):
        return 1

    @property
    def feats(self):
        return 1

    def call(self, req):
        os.write(self.fin, req)
        resp = os.read(self.fout, 4)
        length = int.from_bytes(resp, byteorder="little")
        resp += os.read(self.fout, length - 4)
        return resp

    def handle_exc(self, ctx):
        head = self.read_desc(ctx, ctx.idx)
        assert not head.flags.WRITE

        req = bytearray()

        while not head.flags.WRITE:
            req += self.read_buf(head)

            if not head.flags.NEXT:
                break
            head = self.read_desc(ctx, head.next)

        resp = self.call(bytes(req))
        resplen = len(resp)

        while len(resp):
            self.hv.iface.writemem(head.addr, resp[:head.len])
            resp = resp[head.len:]
            if not head.flags.NEXT:
                break
            head = self.read_desc(ctx, head.next)

        self.hv.p.virtio_put_buffer(ctx.devbase, ctx.qu, ctx.idx, resplen)

        return True

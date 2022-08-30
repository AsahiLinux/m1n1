# SPDX-License-Identifier: MIT

from dataclasses import dataclass
from enum import IntEnum
from m1n1.utils import *
from construct import *

uint8_t = Int8ul
int16_t = Int16sl
uint16_t = Int16ul
int32_t = Int32sl
uint32_t = Int32ul
int64_t = Int64sl
uint64_t = Int64ul

uint = uint32_t
int_ = int32_t
ulong = uint64_t
long_ = int64_t

def Bool(c):
    return ExprAdapter(c, lambda d, ctx: bool(d & 1), lambda d, ctx: int(d))

def SizedArray(count, svar, subcon):
    return Padded(subcon.sizeof() * count, Array(lambda ctx: min(count, ctx.get(svar, ctx._.get(svar))), subcon))

def SizedBytes(count, svar):
    return Lazy(Padded(count, Bytes(lambda ctx: ctx.get(svar) or ctx._.get(svar))))

def UnkBytes(s):
    return Default(HexDump(Bytes(s)), b"\x00" * s)

bool_ = Bool(Int8ul)

class OSObject(Construct):
    TYPE = None

    def _parse(self, stream, context, path, recurse=False):
        tag = stream.read(1).decode("ascii")
        if not recurse and self.TYPE is not None and self.TYPE != tag:
            raise Exception("Object type mismatch")

        if tag == "d":
            count = Int32ul.parse_stream(stream)
            d = {}
            for i in range(count):
                k = self._parse(stream, context, path, True)
                v = self._parse(stream, context, path, True)
                d[k] = v
            return d
        elif tag == "n":
            return Int64ul.parse_stream(stream)
        elif tag == "s":
            length = Int32ul.parse_stream(stream)
            s = stream.read(length).decode("utf-8")
            assert stream.read(1) == b'\0'
            return s
        else:
            raise Exception(f"Unknown object tag {tag!r}")

    def _build(self, obj, stream, context, path):
        assert False

    def _sizeof(self, context, path):
        return None

class OSDictionary(OSObject):
    TYPE = 'd'

class OSSerialize(Construct):
    def _parse(self, stream, context, path, recurse=False):
        hdr = Int32ul.parse_stream(stream)
        if hdr != 0xd3:
            raise Exception("Bad header")

        obj, last = self.parse_obj(stream)
        assert last
        return obj

    def parse_obj(self, stream, level=0):
        # align to 32 bits
        pos = stream.tell()
        if pos & 3:
            stream.read(4 - (pos & 3))

        tag = Int32ul.parse_stream(stream)

        last = bool(tag & 0x80000000)
        otype = (tag >> 24) & 0x1f
        size = tag & 0xffffff

        #print(f"{'  '*level} @{stream.tell():#x} {otype} {last} {size}")

        if otype == 1:
            d = {}
            for i in range(size):
                k, l = self.parse_obj(stream, level + 1)
                assert not l
                v, l = self.parse_obj(stream, level + 1)
                assert l == (i == size - 1)
                d[k] = v
        elif otype == 2:
            d = []
            for i in range(size):
                v, l = self.parse_obj(stream, level + 1)
                assert l == (i == size - 1)
                d.append(v)
        elif otype == 4:
            d = Int64ul.parse_stream(stream)
        elif otype == 9:
            d = stream.read(size).decode("utf-8")
        elif otype == 10:
            d = stream.read(size)
        elif otype == 11:
            d = bool(size)
        else:
            raise Exception(f"Unknown tag {otype}")

        #print(f"{'  '*level}  => {d}")
        return d, last

    def build_obj(self, obj, stream, last=True, level=0):
        tag = 0
        if last:
            tag |= 0x80000000

        if isinstance(obj, dict):
            tag |= (1 << 24) | len(obj)
            Int32ul.build_stream(tag, stream)
            for i, (k, v) in enumerate(obj.items()):
                self.build_obj(k, stream, False, level + 1)
                self.build_obj(v, stream, i == len(obj) - 1, level + 1)
        elif isinstance(obj, list):
            tag |= (2 << 24) | len(obj)
            Int32ul.build_stream(tag, stream)
            for i, v in enumerate(obj):
                self.build_obj(v, stream, i == len(obj) - 1, level + 1)
        elif isinstance(obj, int):
            tag |= (4 << 24) | 64
            Int32ul.build_stream(tag, stream)
            Int64ul.build_stream(obj, stream)
        elif isinstance(obj, str):
            obj = obj.encode("utf-8")
            tag |= (9 << 24) | len(obj)
            Int32ul.build_stream(tag, stream)
            stream.write(obj)
        elif isinstance(obj, bytes):
            tag |= (10 << 24) | len(obj)
            Int32ul.build_stream(tag, stream)
            stream.write(obj)
        elif isinstance(obj, bool):
            tag |= (11 << 24) | int(obj)
            Int32ul.build_stream(tag, stream)
        else:
            raise Exception(f"Cannot encode {obj!r}")

        pos = stream.tell()
        if pos & 3:
            stream.write(bytes(4 - (pos & 3)))

    def _build(self, obj, stream, context, path):
        Int32ul.build_stream(0xd3, stream)
        self.build_obj(obj, stream)

    def _sizeof(self, context, path):
        return None

def string(size):
    return Padded(size, CString("utf8"))


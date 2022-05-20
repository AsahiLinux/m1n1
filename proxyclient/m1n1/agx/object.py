# SPDX-License-Identifier: MIT
from ..malloc import Heap
from ..utils import *
from ..constructutils import ConstructClassBase
from construct import Bytes, Container

class GPUObject:
    def __init__(self, allocator, objtype):

        if isinstance(objtype, ConstructClassBase):
            self.val = objtype
            objtype = type(objtype)
            self._size = objtype.sizeof()
        elif isinstance(objtype, type) and issubclass(objtype, ConstructClassBase):
            self._size = objtype.sizeof()
            self.val = objtype()
        else:
            self._size = objtype.sizeof()
            self.val = objtype.parse(bytes(self._size))

        self._alloc = allocator
        self._type = objtype
        self._addr = None
        self._name = type(objtype).__name__

    def push(self):
        assert self._addr is not None
        stream = self._alloc.make_stream(self._addr)
        context = Container()
        context._parsing = False
        context._building = True
        context._sizing = False
        context._params = context
        print(f"[{self._name} @{self._addr:#x}] pushing {self._size} bytes")
        self._type._build(self.val, stream, context, "(pushing)")

        return self

    def __getattr__(self, attr):
        return getattr(self.val, attr)

    def __setattr__(self, attr, val):
        if attr.startswith("_") or attr == "val":
            self.__dict__[attr] = val
            return

        setattr(self.val, attr, val)

class GPUAllocator:
    PAGE_SIZE = 16384

    def __init__(self, agx, name, start, size, **kwargs):
        self.agx = agx
        self.name = name
        self.heap = Heap(start, start + size, block=self.PAGE_SIZE)
        self.verbose = 1
        self.objects = {}
        self.flags = kwargs

    def make_stream(self, base):
        return self.agx.uat.iostream(0, base)

    def new(self, objtype, name=None, **kwargs):
        obj = GPUObject(self, objtype)
        obj._stream = self.make_stream
        if name is not None:
            obj._name = name

        size_align = align_up(obj._size, self.PAGE_SIZE)
        addr = self.heap.malloc(size_align + self.PAGE_SIZE * 2)
        obj._addr = addr + self.PAGE_SIZE

        obj._paddr = self.agx.u.memalign(self.PAGE_SIZE, size_align)

        print(f"[{self.name}] Alloc {name} size {obj._size:#x} @ {obj._addr:#x} ({obj._paddr:#x})")

        flags = dict(self.flags)
        flags.update(kwargs)

        self.agx.uat.iomap_at(0, obj._addr, obj._paddr, size_align, **flags)
        self.objects[obj._addr] = obj
        return obj

    def buf(self, size, name):
        return self.new(Bytes(size), name=name).push()._addr

# SPDX-License-Identifier: MIT

from ..hv import TraceMode
from ..utils import *

__all__ = []

class RegCacheAlwaysCached(Reloadable):
    def __init__(self, parent):
        self.parent = parent

    def read(self, addr, width):
        return self.parent.read_cached(addr, width)

class RegCache(Reloadable):
    def __init__(self, hv):
        self.hv = hv
        self.u = hv.u
        self.cache = {}

        self.cached = RegCacheAlwaysCached(self)

    def update(self, addr, data):
        self.cache[addr] = data

    def read(self, addr, width):
        if self.hv.ctx:
            data = self.u.read(addr, width)
            self.cache[addr] = data
            return data
        else:
            return self.read_cached(addr, width)

    def read_cached(self, addr, width):
        data = self.cache.get(addr, None)
        if data is None:
            print(f"RegCache: no cache for {addr:#x}")
        return data

    def write(self, addr, data, width):
        if self.hv.ctx:
            self.u.write(addr, data, width)
            self.cache[addr] = data
        else:
            raise Exception("Cannot write register in asynchronous context")

class TracerState:
    pass

class Tracer(Reloadable):
    DEFAULT_MODE = TraceMode.ASYNC

    def __init__(self, hv, verbose=False, ident=None):
        super().__init__()
        self.hv = hv
        self.ident = ident or type(self).__name__
        self.regmaps = {}
        self.verbose = verbose
        self.state = TracerState()
        self.init_state()
        self._cache = RegCache(hv)
        cache = hv.tracer_caches.get(self.ident, None)
        if cache is not None:
            self._cache.cache.update(cache.get("regcache", {}))
            self.state.__dict__.update(cache.get("state", {}))
        hv.tracer_caches[self.ident] = {
            "regcache": self._cache.cache,
            "state": self.state.__dict__
        }

    def init_state(self):
        pass

    def evt_rw(self, evt, regmap=None, prefix=None):
        self._cache.update(evt.addr, evt.data)
        reg = rcls = None
        value = evt.data

        t = "w" if evt.flags.WRITE else "r"

        if regmap is not None:
            reg, index, rcls = regmap.lookup_addr(evt.addr)
            if rcls is not None:
                value = rcls(evt.data)

        if self.verbose >= 3 or reg is None and self.verbose >= 1:
            if reg is None:
                s = f"{evt.addr:#x} = {value:#x}"
            else:
                s = f"{regmap.get_name(evt.addr)} = {value!s}"
            m = "+" if evt.flags.MULTI else " "
            self.log(f"MMIO: {t.upper()}.{1<<evt.flags.WIDTH:<2}{m} " + s)

        if reg is not None:
            if prefix is not None:
                attr = f"{t}_{prefix}_{reg}"
            else:
                attr = f"{t}_{reg}"
            handler = getattr(self, attr, None)
            if handler:
                if index is not None:
                    handler(value, index)
                else:
                    handler(value)
            elif self.verbose >= 2:
                s = f"{regmap.get_name(evt.addr)} = {value!s}"
                m = "+" if evt.flags.MULTI else " "
                self.log(f"MMIO: {t.upper()}.{1<<evt.flags.WIDTH:<2}{m} " + s)

    def trace(self, start, size, mode, **kwargs):
        zone = irange(start, size)
        self.hv.add_tracer(zone, self.ident, mode, self.evt_rw, self.evt_rw, **kwargs)

    def trace_regmap(self, start, size, cls, mode=None, name=None, prefix=None):
        if mode is None:
            mode = self.DEFAULT_MODE
        if name is None:
            name = cls.__name__
        regmap = cls(self._cache, start)
        regmap.cached = cls(self._cache.cached, start)
        setattr(self, name, regmap)
        self.trace(start, size, mode=mode, regmap=regmap, prefix=prefix)
        self.regmaps[start] = regmap

    def start(self):
        pass

    def stop(self):
        self.hv.clear_tracers(self.ident)

    def log(self, msg):
        print(f"[{self.ident}] {msg}")

class PrintTracer(Tracer):
    def __init__(self, hv, device_addr_tbl):
        super().__init__(hv)
        self.device_addr_tbl = device_addr_tbl

    def event_mmio(self, evt):
        dev, zone = self.device_addr_tbl.lookup(evt.addr)
        t = "W" if evt.flags.WRITE else "R"
        m = "+" if evt.flags.MULTI else " "
        print(f"[0x{evt.pc:016x}] MMIO: {t}.{1<<evt.flags.WIDTH:<2}{m} " +
              f"0x{evt.addr:x} ({dev}, offset {evt.addr - zone.start:#04x}) = 0x{evt.data:x}")

class ADTDevTracer(Tracer):
    REGMAPS = []
    NAMES = []
    PREFIXES = []

    def __init__(self, hv, devpath, verbose=False):
        super().__init__(hv, verbose=verbose, ident=type(self).__name__ + "@" + devpath)
        self.dev = hv.adt[devpath]

    @classmethod
    def _reloadcls(cls):
        cls.REGMAPS = [i._reloadcls() if i else None for i in cls.REGMAPS]
        return super(ADTDevTracer, cls)._reloadcls()

    def start(self):
        for i in range(len(self.dev.reg)):
            if i >= len(self.REGMAPS) or (regmap := self.REGMAPS[i]) is None:
                continue
            prefix = name = None
            if i < len(self.NAMES):
                name = self.NAMES[i]
            if i < len(self.PREFIXES):
                prefix = self.PREFIXES[i]

            start, size = self.dev.get_reg(i)
            self.trace_regmap(start, size, regmap, name=name, prefix=prefix)

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__.startswith(__name__))

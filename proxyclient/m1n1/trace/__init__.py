# SPDX-License-Identifier: MIT

from ..hv import TraceMode
from ..utils import *

__all__ = []

class RegCacheAlwaysCached(Reloadable):
    def __init__(self, parent):
        self.parent = parent

    def read(self, addr, width):
        return self.parent.read_cached(addr, width)

    def write(self, addr, data, width):
        raise Exception("Trying to write a register to the cache")

class RegCache(Reloadable):
    def __init__(self, hv):
        self.hv = hv
        self.u = hv.u
        self.cache = {}

        self.cached = RegCacheAlwaysCached(self)

    def update(self, addr, data):
        self.cache[addr] = data

    def read(self, addr, width):
        if self.hv.ctx or not self.hv.started:
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

    def hook_w(self, addr, val, width, **kwargs):
        self.hv.u.write(addr, val, width)

    def hook_r(self, addr, width, **kwargs):
        return self.hv.u.read(addr, width)

    def evt_rw(self, evt, regmap=None, prefix=None):
        self._cache.update(evt.addr, evt.data)
        reg = rcls = None
        value = evt.data

        t = "w" if evt.flags.WRITE else "r"

        if regmap is not None:
            reg, index, rcls = regmap.lookup_addr(evt.addr)
            if rcls is not None:
                value = rcls(evt.data)

        if self.verbose >= 3 or (reg is None and self.verbose >= 1):
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
            elif self.verbose == 2:
                s = f"{regmap.get_name(evt.addr)} = {value!s}"
                m = "+" if evt.flags.MULTI else " "
                self.log(f"MMIO: {t.upper()}.{1<<evt.flags.WIDTH:<2}{m} " + s)

    def trace(self, start, size, mode, read=True, write=True, **kwargs):
        zone = irange(start, size)
        if mode == TraceMode.HOOK:
            self.hv.add_tracer(zone, self.ident, mode, self.hook_r if read else None,
                               self.hook_w if write else None, **kwargs)
        else:
            self.hv.add_tracer(zone, self.ident, mode, self.evt_rw if read else None,
                               self.evt_rw if write else None, **kwargs)

    def trace_regmap(self, start, size, cls, mode=None, name=None, prefix=None, regmap_offset=0):
        if mode is None:
            mode = self.DEFAULT_MODE
        if name is None:
            name = cls.__name__

        regmap = self.regmaps.get(start - regmap_offset, None)
        if regmap is None:
            regmap = cls(self._cache, start - regmap_offset)
            regmap.cached = cls(self._cache.cached, start - regmap_offset)
            self.regmaps[start - regmap_offset] = regmap
        else:
            assert isinstance(regmap, cls)

        setattr(self, name, regmap)
        self.trace(start, size, mode=mode, regmap=regmap, prefix=prefix)

    def start(self):
        pass

    def stop(self):
        self.hv.clear_tracers(self.ident)

    def log(self, msg, show_cpu=True):
        self.hv.log(f"[{self.ident}] {msg}", show_cpu=show_cpu)

class PrintTracer(Tracer):
    def __init__(self, hv, device_addr_tbl):
        super().__init__(hv)
        self.device_addr_tbl = device_addr_tbl
        self.log_file = None

    def event_mmio(self, evt, name=None, start=None):
        dev, zone2 = self.device_addr_tbl.lookup(evt.addr)
        if name is None:
            name = dev
            start = zone2.start
        t = "W" if evt.flags.WRITE else "R"
        m = "+" if evt.flags.MULTI else " "
        logline = (f"[cpu{evt.flags.CPU}] [0x{evt.pc:016x}] MMIO: {t}.{1<<evt.flags.WIDTH:<2}{m} " +
                   f"0x{evt.addr:x} ({name}, offset {evt.addr - start:#04x}) = 0x{evt.data:x}")
        print(logline)
        if self.log_file:
            self.log_file.write(f"# {logline}\n")
            width = 8 << evt.flags.WIDTH
            if evt.flags.WRITE:
                stmt = f"p.write{width}({start:#x} + {evt.addr - start:#x}, {evt.data:#x})\n"
            else:
                stmt = f"p.read{width}({start:#x} + {evt.addr - start:#x})\n"
            self.log_file.write(stmt)

class ADTDevTracer(Tracer):
    REGMAPS = []
    NAMES = []
    PREFIXES = []

    def __init__(self, hv, devpath, verbose=False):
        super().__init__(hv, verbose=verbose, ident=type(self).__name__ + "@" + devpath)
        self.dev = hv.adt[devpath]

    @classmethod
    def _reloadcls(cls, force=False):
        regmaps = []
        for i in cls.REGMAPS:
            if i is None:
                reloaded = None
            elif isinstance(i, tuple):
                reloaded = (i[0]._reloadcls(force), i[1])
            else:
                reloaded = i._reloadcls(force)
            regmaps.append(reloaded)
        cls.REGMAPS = regmaps

        return super()._reloadcls(force)

    def start(self):
        for i in range(len(self.dev.reg)):
            if i >= len(self.REGMAPS) or (regmap := self.REGMAPS[i]) is None:
                continue
            if isinstance(regmap, tuple):
                regmap, regmap_offset = regmap
            else:
                regmap_offset = 0
            prefix = name = None
            if i < len(self.NAMES):
                name = self.NAMES[i]
            if i < len(self.PREFIXES):
                prefix = self.PREFIXES[i]

            start, size = self.dev.get_reg(i)
            self.trace_regmap(start, size, regmap, name=name, prefix=prefix, regmap_offset=regmap_offset)

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__.startswith(__name__))

# SPDX-License-Identifier: MIT
from enum import Enum
import bisect, copy
from construct import Adapter, Int64ul, Int32ul, Int16ul, Int8ul

__all__ = []

def align(v, a=16384):
    return (v + a - 1) & ~(a - 1)

def hexdump(s, sep=" "):
    return sep.join(["%02x"%x for x in s])

def hexdump32(s, sep=" "):
    vals = struct.unpack("<%dI" % (len(s)//4), s)
    return sep.join(["%08x"%x for x in vals])

def _ascii(s):
    s2 = ""
    for c in s:
        if c < 0x20 or c > 0x7e:
            s2 += "."
        else:
            s2 += chr(c)
    return s2

def chexdump(s,st=0):
    for i in range(0,len(s),16):
        print("%08x  %s  %s  |%s|" % (
            i + st,
            hexdump(s[i:i+8], ' ').rjust(23),
            hexdump(s[i+8:i+16], ' ').rjust(23),
            _ascii(s[i:i+16]).rjust(16)))

def chexdump32(s, st=0, abbreviate=True):
    last = None
    skip = False
    for i in range(0,len(s),32):
        val = s[i:i+32]
        if val == last and abbreviate:
            if not skip:
                print("%08x  *" % (i + st))
                skip = True
        else:
            print("%08x  %s" % (
                i + st,
                hexdump32(val, ' ')))
            last = val
            skip = False

class Register:
    def __init__(self, v=0, **kwargs):
        self.value = v
        for k,v in kwargs.items():
            setattr(self, k, v)

    def __getattribute__(self, attr):
        if attr.startswith("_") or attr not in self._fields:
            return object.__getattribute__(self, attr)

        field = getattr(self.__class__, attr)
        value = self.value

        if isinstance(field, int):
            return (value >> field) & 1
        elif isinstance(field, tuple):
            if len(field) == 2:
                msb, lsb = field
                ftype = int
            else:
                msb, lsb, ftype = field
            return ftype((value >> lsb) & ((1 << ((msb + 1) - lsb)) - 1))
        else:
            raise AttributeError(f"Invalid field definition {attr} = {field!r}")

    def __setattr__(self, attr, fvalue):
        if attr not in self._fields:
            self.__dict__[attr] = fvalue
            return

        field = getattr(self.__class__, attr)

        value = self.value

        if isinstance(field, int):
            self.value = (value & ~(1 << field)) | ((fvalue & 1) << field)
        elif isinstance(field, tuple):
            if len(field) == 2:
                msb, lsb = field
            else:
                msb, lsb, ftype = field
            mask = ((1 << ((msb + 1) - lsb)) - 1)
            self.value = (value & ~(mask << lsb)) | ((fvalue & mask) << lsb)
        else:
            raise AttributeError(f"Invalid field definition {attr} = {field!r}")

    @property
    def _fields(self):
        return (k for k in self.__class__.__dict__ if k != "value" and not k.startswith("_"))

    def _field_val(self, field_name, as_repr=False):
        field = getattr(self.__class__, field_name)
        val = getattr(self, field_name)
        if isinstance(val, Enum):
            if as_repr:
                return str(val)
            else:
                msb, lsb = field[:2]
                if (msb - lsb + 1) > 3:
                    return f"0x{val.value:x}({val.name})"
                else:
                    return f"{val.value}({val.name})"
        elif not isinstance(val, int):
            return val
        elif isinstance(field, int):
            return val
        elif isinstance(field, tuple):
            msb, lsb = field[:2]
            if (msb - lsb + 1) > 3:
                return f"0x{val:x}"

        return val

    def __str__(self):
        d = '.'
        return f"0x{self.value:x} ({', '.join(f'{k}={self._field_val(k)}' for k in self._fields)})"

    def __repr__(self):
        return f"{type(self).__name__}({', '.join(f'{k}={self._field_val(k, True)}' for k in self._fields)})"

class Register8(Register):
    __WIDTH__ = 8

class Register16(Register):
    __WIDTH__ = 16

class Register32(Register):
    __WIDTH__ = 32

class Register64(Register):
    __WIDTH__ = 64

class RegAdapter(Adapter):
    def __init__(self, register):
        if register.__WIDTH__ == 64:
            subcon = Int64ul
        elif register.__WIDTH__ == 32:
            subcon = Int32ul
        elif register.__WIDTH__ == 16:
            subcon = Int16ul
        elif register.__WIDTH__ == 8:
            subcon = Int8ul
        else:
            raise ValueError("Invalid reg width")

        self.reg = register
        super().__init__(subcon)

    def _decode(self, obj, context, path):
        return self.reg(obj)

    def _encode(self, obj, context, path):
        return obj.value

class RangeMap:
    def __init__(self):
        self.__start = []
        self.__end = []
        self.__value = []

    def __len__(self):
        return len(self.__start)

    def __contains(self, pos, addr):
        if pos < 0 or pos >= len(self.__start):
            return False

        return self.__start[pos] <= addr and addr <= self.__end[pos]

    def __split(self, pos, addr):
        self.__start.insert(pos + 1, addr)
        self.__end.insert(pos, addr - 1)
        self.__value.insert(pos + 1, copy.copy(self.__value[pos]))

    def lookup(self, addr, default=None):
        addr = int(addr)

        pos = bisect.bisect_left(self.__end, addr)
        if self.__contains(pos, addr):
            return self.__value[pos]
        else:
            return default

    def ranges(self):
        return ((range(s, e + 1), v) for s, e, v in zip(self.__start, self.__end, self.__value))

    def overlaps(self, zone):
        if len(zone) == 0:
            return

        start = bisect.bisect_left(self.__end, zone.start)

        for pos in range(start, len(self.__start)):
            if self.__start[pos] >= zone.stop:
                break
            yield range(self.__start[pos], self.__end[pos] + 1), self.__value[pos]

    def populate(self, zone, default=[]):
        if len(zone) == 0:
            return

        start, stop = zone.start, zone.stop

        # Starting insertion point, overlap inclusive
        pos = bisect.bisect_left(self.__end, zone.start)

        # Handle left-side overlap
        if self.__contains(pos, zone.start) and self.__start[pos] != zone.start:
            self.__split(pos, zone.start)
            pos += 1
            assert self.__start[pos] == zone.start

        # Iterate through overlapping ranges
        while start < stop:
            if pos == len(self.__start):
                # Append to end
                val = copy.copy(default)
                self.__start.append(start)
                self.__end.append(stop - 1)
                self.__value.append(val)
                yield range(start, stop), val
                break

            assert self.__start[pos] >= start
            if self.__start[pos] > start:
                # Insert new range
                boundary = stop
                if pos < len(self.__start):
                    boundary = min(stop, self.__start[pos])
                val = copy.copy(default)
                self.__start.insert(pos, start)
                self.__end.insert(pos, boundary - 1)
                self.__value.insert(pos, val)
                yield range(start, boundary), val
                start = boundary
            else:
                # Handle right-side overlap
                if self.__end[pos] > stop - 1:
                    self.__split(pos, stop)
                # Add to existing range
                yield range(self.__start[pos], self.__end[pos] + 1), self.__value[pos]
                start = self.__end[pos] + 1

            pos += 1
        else:
            assert start == stop

    def compact(self, equal=lambda a, b: a == b, empty=lambda a: not a):
        if len(self) == 0:
            return

        new_s, new_e, new_v = [], [], []

        for pos in range(len(self)):
            s, e, v = self.__start[pos], self.__end[pos], self.__value[pos]
            if empty(v):
                continue
            if new_v and equal(last, v):
                new_e[-1] = e
            else:
                new_s.append(s)
                new_e.append(e)
                new_v.append(v)
                last = v

        self.__start, self.__end, self.__value = new_s, new_e, new_v

    def _assert(self, expect, val=lambda a:a):
        state = []
        for i, j, v in zip(self.__start, self.__end, self.__value):
            state.append((i, j, val(v)))
        if state != expect:
            print(f"Expected: {expect}")
            print(f"Got:      {state}")

class AddrLookup(RangeMap):
    def __str__(self):
        b = [""]
        for zone, values in self.ranges():
            b.append(f"{zone.start:#11x} - {zone.stop - 1:#11x}")
            if len(values) == 0:
                b.append(f" (empty range)")
            elif len(values) == 1:
                b.append(f" : {values[0][0]}\n")
            if len(values) > 1:
                b.append(f" ({len(values):d} devices)\n")
                for value, r in sorted(values, key=lambda r: r[1].start):
                    b.append(f"      {r.start:#10x} - {r.stop - 1:#8x} : {value}\n")

        return "".join(b)

    def add(self, zone, value):
        for r, values in self.populate(zone):
            values.append((value, zone))

    def remove(self, zone, value):
        for r, values in self.overlaps(zone):
            try:
                values.remove((value, zone))
            except:
                pass

    def lookup(self, addr, default='unknown'):
        maps = super().lookup(addr)
        return maps[0] if maps else (default, range(0, 1 << 64))

    def lookup_all(self, addr):
        return super().lookup(addr, [])

    def _assert(self, expect, val=lambda a:a):
        super()._assert(expect, lambda v: [i[0] for i in v])

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)

if __name__ == "__main__":
    # AddrLookup test
    a = AddrLookup()
    a.add(range(0, 10), 0)
    a._assert([
        (0, 9, [0])
    ])
    a.add(range(10, 20), 1)
    a._assert([
        (0, 9, [0]), (10, 19, [1])
    ])
    a.add(range(20, 25), 2)
    a._assert([
        (0, 9, [0]), (10, 19, [1]), (20, 24, [2])
    ])
    a.add(range(30, 40), 3)
    a._assert([
        (0, 9, [0]), (10, 19, [1]), (20, 24, [2]), (30, 39, [3])
    ])
    a.add(range(0, 15), 4)
    a._assert([
        (0, 9, [0, 4]), (10, 14, [1, 4]), (15, 19, [1]), (20, 24, [2]), (30, 39, [3])
    ])
    a.add(range(0, 15), 5)
    a._assert([
        (0, 9, [0, 4, 5]), (10, 14, [1, 4, 5]), (15, 19, [1]), (20, 24, [2]), (30, 39, [3])
    ])
    a.add(range(21, 44), 6)
    a._assert([
        (0, 9, [0, 4, 5]), (10, 14, [1, 4, 5]), (15, 19, [1]), (20, 20, [2]), (21, 24, [2, 6]),
        (25, 29, [6]), (30, 39, [3, 6]), (40, 43, [6])
    ])
    a.add(range(70, 80), 7)
    a._assert([
        (0, 9, [0, 4, 5]), (10, 14, [1, 4, 5]), (15, 19, [1]), (20, 20, [2]), (21, 24, [2, 6]),
        (25, 29, [6]), (30, 39, [3, 6]), (40, 43, [6]), (70, 79, [7])
    ])
    a.add(range(0, 100), 8)
    a._assert([
        (0, 9, [0, 4, 5, 8]), (10, 14, [1, 4, 5, 8]), (15, 19, [1, 8]), (20, 20, [2, 8]),
        (21, 24, [2, 6, 8]), (25, 29, [6, 8]), (30, 39, [3, 6, 8]), (40, 43, [6, 8]),
        (44, 69, [8]), (70, 79, [7, 8]), (80, 99, [8])
    ])
    a.remove(range(21, 44), 6)
    a._assert([
        (0, 9, [0, 4, 5, 8]), (10, 14, [1, 4, 5, 8]), (15, 19, [1, 8]), (20, 20, [2, 8]),
        (21, 24, [2, 8]), (25, 29, [8]), (30, 39, [3, 8]), (40, 43, [8]),
        (44, 69, [8]), (70, 79, [7, 8]), (80, 99, [8])
    ])
    a.compact()
    a._assert([
        (0, 9, [0, 4, 5, 8]), (10, 14, [1, 4, 5, 8]), (15, 19, [1, 8]), (20, 24, [2, 8]),
        (25, 29, [8]), (30, 39, [3, 8]), (40, 69, [8]), (70, 79, [7, 8]),
        (80, 99, [8])
    ])
    a.remove(range(0, 100), 8)
    a._assert([
        (0, 9, [0, 4, 5]), (10, 14, [1, 4, 5]), (15, 19, [1]), (20, 24, [2]), (25, 29, []),
        (30, 39, [3]), (40, 69, []), (70, 79, [7]), (80, 99, [])
    ])
    a.compact()
    a._assert([
        (0, 9, [0, 4, 5]), (10, 14, [1, 4, 5]), (15, 19, [1]), (20, 24, [2]), (30, 39, [3]),
        (70, 79, [7])
    ])

# SPDX-License-Identifier: MIT
from enum import Enum
import bisect
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

class AddrLookup:
    def __init__(self):
        self.__addr = []
        self.__end = []
        self.__ranges = []

    def __len__(self):
        return len(self.__addr)

    def __str__(self):
        b = ""
        for i in range(len(self)):
            b += f"{i:4d}: {self.__addr[i]:#010x} - {self.__end[i]:#010x}"
            if len(self.__ranges[i]) > 1:
                b += f" {len(self.__ranges[i]):2d} sub ranges"
            b += '\n'
            for r, value in sorted(self.__ranges[i], key=lambda r: r[0].start):
                b += f"      {r.start:#010x}   {len(r):#08x}   {value}: \n"
        return b

    def __overlaps(self, zone, pos):
        if self.__addr[pos] in zone or self.__end[pos] in zone:
            return True
        return self.__addr[pos] <= zone.start and zone.start < self.__end[pos]

    def __merge(self, a, b):
        self.__addr.pop(b)
        self.__end.pop(a)
        self.__ranges[a] = sorted(self.__ranges[a] + self.__ranges[b], key=lambda r: len(r[0]))
        self.__ranges.pop(b)

    def __append(self, pos, zone, value):
        if zone.start < self.__addr[pos]:
            self.__addr[pos] = zone.start
        if zone.stop - 1 >  self.__end[pos]:
            self.__end[pos] = zone.stop - 1
        # insert sorted and merge identical ranges
        sizes = [len(e[0]) for e in self.__ranges[pos]]
        start = bisect.bisect_left(sizes, len(zone))
        for subpos in range(start, len(self.__ranges[pos])):
            e_zone, e_value = self.__ranges[pos][subpos]
            if len(zone) < len(e_zone):
                self.__ranges[pos].insert(subpos, (zone, [value]))
                break
        else:
            self.__ranges[pos].append((zone, [value]))

    def add(self, zone, value):
        pos = bisect.bisect(self.__addr, zone.start)
        overlap_left = pos > 0 and self.__overlaps(zone, pos - 1)
        overlap_right = pos < len(self) and self.__overlaps(zone, pos)

        if overlap_left and overlap_right:
            self.__merge(pos - 1, pos)
            self.__append(pos - 1, zone, value)
        elif overlap_left:
            self.__append(pos - 1, zone, value)
        elif overlap_right:
            self.__append(pos, zone, value)
        else:
            self.__addr.insert(pos, zone.start)
            self.__end.insert(pos, zone.stop - 1)
            self.__ranges.insert(pos, [(zone, [value])])

    def lookup(self, addr, default='unknown'):
        addr = int(addr)
        pos = bisect.bisect(self.__addr, addr)
        if pos == 0 or self.__end[pos - 1] < addr:
            return (default, range(0, 1 << 64))

        for r, value in self.__ranges[pos - 1]:
            if addr in r:
                return (value[0], r)
        return (None, range(0, 0))

    def lookup_all(self, addr):
        addr = int(addr)
        pos = bisect.bisect(self.__addr, addr)
        if pos == 0 or self.__end[pos - 1] < addr:
            return []
        return [(value, r) for r, value in self.__ranges[pos - 1] if addr in r]

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)

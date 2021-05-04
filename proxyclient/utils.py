#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

from enum import Enum
from construct import Adapter, Int64ul, Int32ul, Int16ul, Int8ul

def align(v, a=16384):
    return (v + a - 1) & ~(a - 1)

class Register:
    def __init__(self, v=None, **kwargs):
        if v is not None:
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

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import inspect, textwrap, json, re, sys, os

from construct import *
from construct.core import evaluate
from construct.lib import HexDisplayedInteger
from .utils import *

g_struct_trace = set()
g_struct_addrmap = {}
g_depth = 0

def ZPadding(size):
    return Const(bytes(size), Bytes(size))

def recusive_reload(obj, token=None):
    global g_depth

    if token is None:
        g_depth = 0
        token = object()

    cur_token = getattr(obj, "_token", None)
    if cur_token is token:
        return

    g_depth += 1
    #print("  " * g_depth + f"> {obj}", id(obj), id(token))
    if isinstance(obj, Construct) and hasattr(obj, 'subcon'):
        # Single subcon types
        if inspect.isclass(obj.subcon):
            #print("> isclass")
            if hasattr(obj.subcon, "_reloadcls"):
                #print("> Recursive (subcon)")
                obj.subcon = obj.subcon._reloadcls(token=token)
        else:
            if isinstance(obj.subcon, Construct):
                recusive_reload(obj.subcon, token)
    if isinstance(obj, Construct) and hasattr(obj, 'subcons'):
        # Construct types that have lists
        new_subcons = []
        for i, item in enumerate(obj.subcons):
            if inspect.isclass(item):
                if hasattr(item, "_reloadcls"):
                    #print("> Recursive (subcons)")
                    item = item._reloadcls()
            else:
                if isinstance(item, Construct):
                    recusive_reload(item, token)
            new_subcons.append(item)
            obj.subcons = new_subcons

    if isinstance(obj, Construct) and hasattr(obj, 'cases'):
        # Construct types that have lists
        for i, item in list(obj.cases.items()):
            if inspect.isclass(item):
                if hasattr(item, "_reloadcls"):
                    #print("> Recursive (cases)")
                    obj.cases[i] = item._reloadcls(token=token)
            else:
                if isinstance(item, Construct):
                    recusive_reload(item, token)

    for field in dir(obj):
        value = getattr(obj, field)
        if inspect.isclass(value):
            if hasattr(value, "_reloadcls"):
                #print("> Recursive (value)")
                setattr(obj, field, value._reloadcls(token=token))
        else:
            if isinstance(value, Construct):
                recusive_reload(value, token)

    obj._token = token

    g_depth -= 1

def str_value(value, repr=False):
    if isinstance(value, bytes) and value == bytes(len(value)):
        return f"bytes({len(value):#x})"
    if isinstance(value, bytes) and repr:
        return f"bytes.fromhex('{value.hex()}')"
    if isinstance(value, DecDisplayedInteger):
        return str(value)
    if isinstance(value, int):
        if value in g_struct_addrmap:
            desc = g_struct_addrmap[value]
            return f"{value:#x} ({desc})"
        else:
            return f"{value:#x}"
    if isinstance(value, ListContainer):
        om = ""
        while len(value) > 1 and not value[-1]:
            value = value[:-1]
            om = " ..."
        if len(value) <= 16:
            return "[" + ", ".join(map(str_value, value)) + f"{om}]"
        else:
            sv = ["[\n"]
            for off in range(0, len(value), 16):
                sv.append("  " + ", ".join(map(str_value, value[off:off+16])) + ",\n")
            sv.append(f"{om}]\n")
            return "".join(sv)

    return str(value)

class DecDisplayedInteger(int):
    @staticmethod
    def new(intvalue):
        obj = DecDisplayedInteger(intvalue)
        return obj

class Dec(Adapter):
    def _decode(self, obj, context, path):
        try:
            if isinstance(obj, int):
                return DecDisplayedInteger.new(obj)
            return obj
        except Exception as e:
            print(e)
            raise

    def _encode(self, obj, context, path):
        return obj

    def _emitparse(self, code):
        return self.subcon._compileparse(code)

    def _emitseq(self, ksy, bitwise):
        return self.subcon._compileseq(ksy, bitwise)

    def _emitprimitivetype(self, ksy, bitwise):
        return self.subcon._compileprimitivetype(ksy, bitwise)

    def _emitfulltype(self, ksy, bitwise):
        return self.subcon._compilefulltype(ksy, bitwise)

class ConstructClassException(Exception):
    pass


# We need to inherrit Construct as a metaclass so things like If and Select will work
class ReloadableConstructMeta(ReloadableMeta, Construct):

    def __new__(cls, name, bases, attrs):
        cls = super().__new__(cls, name, bases, attrs)
        cls.name = name
        if cls.SHORT_NAME is not None:
            cls.short_name = cls.SHORT_NAME
        else:
            cls.short_name = re.sub('[a-z]', '', cls.name)
            if len(cls.short_name) > 5:
                cls.short_name = cls.short_name[:3] + cls.short_name[-2:]

        try:
            cls.flagbuildnone = cls.subcon.flagbuildnone
        except AttributeError:
            cls.flagbuildnone = False

        cls.docs = None

        cls._off = {}
        if "subcon" not in attrs:
            return cls

        subcon = attrs["subcon"]
        if isinstance(subcon, Struct):
            off = 0
            for subcon in subcon.subcons:
                try:
                    sizeof = subcon.sizeof()
                except:
                    sizeof = None
                if isinstance(subcon, Ver):
                    if not subcon._active():
                        cls._off[subcon.name] = -1, 0
                        continue
                    subcon = subcon.subcon
                if isinstance(subcon, Renamed):
                    name = subcon.name
                    subcon = subcon.subcon
                    cls._off[name] = off, sizeof
                if sizeof is None:
                    break
                off += sizeof
        return cls

class ConstructClassBase(Reloadable, metaclass=ReloadableConstructMeta):
    """ Offers two benifits over regular construct

        1. It's reloadable, and can recusrivly reload other refrenced ConstructClasses
        2. It's a class, so you can define methods

        Currently only supports parsing, but could be extended to support building

        Example:
            Instead of:
            MyStruct = Struct(
                "field1" / Int32ul
            )

            class MyClass(ConstructClass):
                subcon = Struct(
                    "field1" / Int32ul
                )

    """
    SHORT_NAME = None

    parsed = None

    def __init__(self):
        self._pointers = set()
        self._addr = None
        self._meta = {}

    def regmap(self):
        return ConstructRegMap(type(self), self._stream.to_accessor(), self._addr)

    @classmethod
    def sizeof(cls, **contextkw):
        context = Container(**contextkw)
        context._parsing = False
        context._building = False
        context._sizing = True
        context._params = context
        return cls._sizeof(context, "(sizeof)")

    def Apply(self, dict=None, **kwargs):
        if dict is None:
            dict = kwargs

        for key in dict:
            if not key.startswith('_'):
                setattr(self, key, dict[key])
                self._keys += [key]

    def set_addr(self, addr=None, stream=None):
        #print("set_addr", type(self), addr)
        if addr is not None:
            self._addr = addr
        self._set_meta(self, stream)

    @classmethod
    def _build(cls, obj, stream, context, path):
        cls._build_prepare(obj)

        addr = stream.tell()
        try:
            new_obj = cls.subcon._build(obj, stream, context, f"{path} -> {cls.name}")
        except ConstructClassException:
            raise
        except ConstructError:
            raise
        except Exception as e:
            raise ConstructClassException(f"at {path} -> {cls.name}") from e

        # if obj is a raw value or Container, instance a proper object for it
        if not isinstance(obj, ConstructClassBase):
            obj = cls.__new__(cls)

        # update the object with anything that build updated (such as defaults)
        obj._apply(new_obj)

        obj._addr = addr
        cls._set_meta(obj, stream)
        return obj

    @classmethod
    def _sizeof(cls, context, path):
        return cls.subcon._sizeof(context, f"{path} -> {cls.name}")

    @classmethod
    def _reloadcls(cls, force=False, token=None):
        #print(f"_reloadcls({cls})", id(cls))
        newcls = Reloadable._reloadcls.__func__(cls, force)
        if hasattr(newcls, "subcon"):
            recusive_reload(newcls.subcon, token)
        return newcls

    def _apply(self, obj):
        raise NotImplementedError()

    @classmethod
    def _set_meta(cls, self, stream=None):
        if stream is not None:
            self._pointers = set()
            self._meta = {}
            self._stream = stream

        if isinstance(cls.subcon, Struct):
            subaddr = int(self._addr)
            for subcon in cls.subcon.subcons:
                try:
                    sizeof = subcon.sizeof()
                except:
                    break
                if isinstance(subcon, Ver):
                    subcon = subcon.subcon
                if isinstance(subcon, Renamed):
                    name = subcon.name
                    #print(name, subcon)
                    subcon = subcon.subcon
                    if stream is not None and getattr(stream, "meta_fn", None):
                        meta = stream.meta_fn(subaddr, sizeof)
                        if meta is not None:
                            self._meta[name] = meta
                    if isinstance(subcon, Pointer):
                        self._pointers.add(name)
                        continue
                    try:
                        #print(name, subcon)
                        val = self[name]
                    except:
                        pass
                    else:
                        if isinstance(val, ConstructClassBase):
                            val.set_addr(subaddr)
                        if isinstance(val, list):
                            for i in val:
                                if isinstance(i, ConstructClassBase):
                                    i.set_addr(subaddr)
                                    subaddr += i.sizeof()

                subaddr += sizeof

    @classmethod
    def _parse(cls, stream, context, path):
        #print(f"parse {cls} @ {stream.tell():#x} {path}")
        addr = stream.tell()
        obj = cls.subcon._parse(stream, context, path)
        size = stream.tell() - addr

        # Don't instance Selects
        if isinstance(cls.subcon, Select):
            return obj

        # Skip calling the __init__ constructor, so that it can be used for building
        # Use parsed instead, if you need a post-parsing constructor
        self = cls.__new__(cls)
        self._addr = addr
        self._path = path
        self._meta = {}
        cls._set_meta(self, stream)

        self._apply(obj)

        if self._addr > 0x10000:
            g_struct_trace.add((self._addr, f"{cls.name} (end: {self._addr + size:#x})"))
            g_struct_addrmap[self._addr] = f"{cls.name}"
        return self

    @classmethod
    def _build_prepare(cls, obj):
        pass

    def build_stream(self, obj=None, stream=None, **contextkw):
        assert stream != None
        if obj is None:
            obj = self

        return Construct.build_stream(self, obj, stream, **contextkw)

    def build(self, obj=None, **contextkw):
        if obj is None:
            obj = self

        return Construct.build(self, obj, **contextkw)

class ROPointer(Pointer):
    def _build(self, obj, stream, context, path):
        return obj

    def _parse(self, stream, context, path):
        recurse = getattr(stream, "recurse", False)
        if not recurse:
            return None

        return Pointer._parse(self, stream, context, path)

class ConstructClass(ConstructClassBase, Container):
    """ Offers two benifits over regular construct

        1. It's reloadable, and can recusrivly reload other refrenced ConstructClasses
        2. It's a class, so you can define methods

        Currently only supports parsing, but could be extended to support building

        Example:
            Instead of:
            MyStruct = Struct(
                "field1" / Int32ul
            )

            class MyClass(ConstructClass):
                subcon = Struct(
                    "field1" / Int32ul
                )
    """

    def diff(self, other, show_all=False):
        return self.__str__(other=other, show_all=show_all)

    def __eq__(self, other):
        return all(self[k] == other[k] for k in self
                   if (not k.startswith("_"))
                   and (k not in self._pointers)
                   and not callable(self[k]))

    def __str__(self, ignore=[], other=None, show_all=False) -> str:

        str = self.__class__.__name__
        if self._addr is not None:
            str += f" @ 0x{self._addr:x}:"

        str += "\n"

        keys = list(self)
        keys.sort(key = lambda x: self._off.get(x, (-1, 0))[0])

        for key in keys:
            if key in self._off:
                offv, sizeof = self._off[key]
                if offv == -1:
                    print(key, offv, sizeof)
                    continue
            if key in ignore or key.startswith('_'):
                continue
            value = getattr(self, key)
            need_diff = False
            if other is not None:
                if key in self._pointers or callable(value):
                    continue
                other_value = getattr(other, key)
                if not show_all and other_value == value:
                    continue
                offv, sizeof = self._off[key]
                if sizeof == 0:
                    continue
                def _valdiff(value, other_value):
                    if hasattr(value, "diff"):
                        return value.diff(other_value)
                    elif isinstance(value, bytes) and isinstance(other_value, bytes):
                        pad = bytes()
                        if len(value) & 3:
                            pad = bytes(4 - (len(value) & 3))
                        return chexdiff32(other_value+pad, value+pad, offset=offv, offset2=0)
                    else:
                        val_repr = str_value(value)
                        if other_value != value:
                            other_repr = str_value(other_value)
                            return f"\x1b[33;1;4m{val_repr}\x1b[m ← \x1b[34m{other_repr}\x1b[m"
                        return val_repr

                if isinstance(value, list):
                    val_repr = "{\n"
                    for i, (a, b) in enumerate(zip(value, other_value)):
                        if a == b:
                            continue
                        val_repr += f"[{i}] = " + textwrap.indent(_valdiff(a, b), "    ") + "\n"
                        offv += sizeof // len(value)
                    val_repr += "}\n"
                else:
                    val_repr = _valdiff(value, other_value)

            else:
                val_repr = str_value(value)
            off = ""
            meta = ""
            if key in self._off:
                offv, sizeof = self._off[key]
                if sizeof is not None:
                    sizeofs = f"{sizeof:3x}"
                else:
                    sizeofs = "  *"
                off = f"\x1b[32m[{offv:3x}.{sizeofs}]\x1b[m "
            if key in self._meta:
                meta = f" \x1b[34m{self._meta[key]}\x1b[m"
            if '\n' in val_repr:
                val_repr = textwrap.indent(val_repr, f'\x1b[90m{self.short_name:>5s}.\x1b[m')
                if not val_repr.endswith('\n'):
                    val_repr += '\n'
                str += f"\x1b[90m{self.short_name:>5s}.{off}\x1b[95m{key}\x1b[m ={meta}\n{val_repr}"
            else:
                str += f"\x1b[90m{self.short_name:>5s}.{off}\x1b[95m{key}\x1b[m = {val_repr}{meta}\n"

        return str

    def _dump(self):
        print(f"# {self.__class__.__name__}")
        if self._addr is not None:
            print(f"#  Address: 0x{self._addr:x}")

        keys = list(self)
        keys.sort(key = lambda x: self._off.get(x, (-1, 0))[0])
        for key in keys:
            if key.startswith('_'):
                continue
            value = getattr(self, key)
            val_repr = str_value(value, repr=True)
            print(f"self.{key} = {val_repr}")


    @classmethod
    def _build_prepare(cls, obj):
        if isinstance(cls.subcon, Struct):
            for subcon in cls.subcon.subcons:
                if isinstance(subcon, Ver):
                    subcon = subcon.subcon
                if not isinstance(subcon, Renamed):
                    continue
                name = subcon.name
                subcon = subcon.subcon
                if isinstance(subcon, Lazy):
                    subcon = subcon.subcon
                if not isinstance(subcon, Pointer):
                    continue
                addr_field = subcon.offset.__getfield__()
                # Ugh.
                parent = subcon.offset._Path__parent(obj)
                if not hasattr(obj, name) and hasattr(parent, addr_field):
                    # No need for building
                    setattr(obj, name, None)
                elif hasattr(obj, name):
                    subobj = getattr(obj, name)
                    try:
                        addr = subobj._addr
                    except (AttributeError, KeyError):
                        addr = None
                    if addr is not None:
                        setattr(parent, addr_field, addr)

    @classmethod
    def _parse(cls, stream, context, path):
        self = ConstructClassBase._parse.__func__(cls, stream, context, path)

        for key in self:
            if key.startswith('_'):
                continue
            try:
                val = int(self[key])
            except:
                continue
            if (0x1000000000 <= val <= 0x1f00000000 or
                0xf8000000000 <= val <= 0xff000000000 or
                0xffffff8000000000 <= val <= 0xfffffff000000000):
                g_struct_trace.add((val, f"{cls.name}.{key}"))
        return self

    def _apply_classful(self, obj):
        obj2 = dict(obj)
        if isinstance(self.__class__.subcon, Struct):
            for subcon in self.__class__.subcon.subcons:
                name = subcon.name
                if name is None:
                    continue
                subcon = subcon.subcon
                if isinstance(subcon, Lazy):
                    continue
                if isinstance(subcon, Pointer):
                    subcon = subcon.subcon
                if isinstance(subcon, Ver):
                    subcon = subcon.subcon
                if isinstance(subcon, Array):
                    subcon = subcon.subcon

                if name not in obj2:
                    continue

                val = obj2[name]
                if not isinstance(subcon, type) or not issubclass(subcon, ConstructClassBase):
                    continue

                def _map(v):
                    if not isinstance(v, subcon):
                        sc = subcon()
                        sc._apply(v)
                        return sc
                    return v

                if isinstance(val, list):
                    obj2[name] = list(map(_map, val))
                else:
                    obj2[name] = _map(val)

        self._apply(obj2)

    def _apply(self, obj):
        self.update(obj)

    def items(self):
        for k in list(self):
            if k.startswith("_"):
                continue
            yield k, self[k]

    def addrof(self, name):
        return self._addr + self._off[name][0]

    @classmethod
    def offsetof(cls, name):
        return cls._off[name][0]

    def clone(self):
        obj = type(self)()
        obj.update(self)
        return obj

    @classmethod
    def from_json(cls, fd):
        d = json.load(fd)
        obj = cls()
        obj._apply_classful(d)
        return obj

    @classmethod
    def is_versioned(cls):
        for subcon in cls.subcon.subcons:
            if isinstance(subcon, Ver):
                return True
            while True:
                try:
                    subcon = subcon.subcon
                    if isinstance(subcon, type) and issubclass(subcon, ConstructClass) and subcon.is_versioned():
                        return True
                except:
                    break
        return False

    @classmethod
    def to_rust(cls):
        assert isinstance(cls.subcon, Struct)
        s = []
        if cls.is_versioned():
            s.append("#[versions(AGX)]"),

        s += [
            "#[derive(Debug, Clone, Copy)]",
            "#[repr(C, packed(4))]",
            f"struct {cls.__name__} {{",
        ]
        pad = 0
        has_ver = False
        for subcon in cls.subcon.subcons:
            if isinstance(subcon, Ver):
                if not has_ver:
                    s.append("")
                s.append(f"    #[ver({subcon.cond})]")
                subcon = subcon.subcon
                has_ver = True
            else:
                has_ver = False

            name = subcon.name
            if name is None:
                name = f"__pad{pad}"
                pad += 1

            array_len = []
            skip = False
            while subcon:
                if isinstance(subcon, Lazy):
                    skip = True
                    break
                elif isinstance(subcon, Pointer):
                    skip = True
                    break
                elif isinstance(subcon, Array):
                    array_len.append(subcon.count)
                elif isinstance(subcon, (HexDump, Default, Renamed, Dec, Hex, Const)):
                    pass
                else:
                    break
                subcon = subcon.subcon

            if isinstance(subcon, Bytes):
                array_len.append(subcon.length)
                subcon = Int8ul

            if skip:
                #s.append(f"    // {name}: {subcon}")
                continue

            TYPE_MAP = {
                Int64ul: "u64",
                Int32ul: "u32",
                Int16ul: "u16",
                Int8ul: "u8",
                Int64sl: "i64",
                Int32sl: "i32",
                Int16sl: "i16",
                Int8sl: "i8",
                Float32l: "f32",
                Float64l: "f64",
            }

            t = TYPE_MAP.get(subcon, repr(subcon))

            if isinstance(subcon, type) and issubclass(subcon, ConstructClass):
                t = subcon.__name__
                if subcon.is_versioned():
                    t += "::ver"

            for n in array_len[::-1]:
                t = f"[{t}; {n:#x}]"

            s.append(f"    {name}: {t},")

            if has_ver:
                s.append("")

        s += ["}"]
        return "\n".join(s)

class ConstructValueClass(ConstructClassBase):
    """ Same as Construct, but for subcons that are single values, rather than containers

        the value is stored as .value
    """

    def __eq__(self, other):
        return self.value == other.value

    def __str__(self) -> str:
        str = f"{self.__class__.__name__} @ 0x{self._addr:x}:"
        str += f"\t{str_value(self.value)}"
        return str

    def __getitem__(self, i):
        if i == "value":
            return self.value
        raise Exception(f"Invalid index {i}")

    @classmethod
    def _build(cls, obj, stream, context, path):
        return super()._build(obj.value, stream, context, path)

    def _apply(self, obj):
        self.value = obj
    _apply_classful = _apply

class ConstructRegMap(BaseRegMap):
    TYPE_MAP = {
        Int8ul: Register8,
        Int16ul: Register16,
        Int32ul: Register32,
        Int64ul: Register64,
    }

    def __init__(self, cls, backend, base):
        self._addrmap = {}
        self._rngmap = SetRangeMap()
        self._namemap = {}
        assert isinstance(cls.subcon, Struct)
        for subcon in cls.subcon.subcons:
            if isinstance(subcon, Ver):
                subcon = subcon.subcon
            if not isinstance(subcon, Renamed):
                continue
            name = subcon.name
            subcon = subcon.subcon
            if subcon not in self.TYPE_MAP:
                continue
            rtype = self.TYPE_MAP[subcon]
            if name not in cls._off:
                continue
            addr, size = cls._off[name]
            self._addrmap[addr] = name, rtype
            self._namemap[name] = addr, rtype
        super().__init__(backend, base)

    def __getattr__(self, k):
        if k.startswith("_"):
            return self.__dict__[k]
        return self._accessor[k]

    def __setattr__(self, k, v):
        if k.startswith("_"):
            self.__dict__[k] = v
            return
        self._accessor[k].val = v

class Ver(Subconstruct):
    # Ugly hack to make this survive across reloads...
    try:
        _version = sys.modules["m1n1.constructutils"].Ver._version
    except (KeyError, AttributeError):
        _version = {"V": os.environ.get("AGX_FWVER", "V12_3"),
                    "G": os.environ.get("AGX_GPU", "G13")}

    MATRIX = {
        "V": ["V12_1", "V12_3", "V12_4", "V13_0B4"],
        "G": ["G13", "G14"],
    }

    def __init__(self, version, subcon):
        self.cond = version
        self.vcheck = self.parse_ver(version)
        self._name = subcon.name
        self.subcon = subcon
        self.flagbuildnone = True
        self.docs = ""
        self.parsed = None

    @property
    def name(self):
        if self._active():
            return self._name
        else:
            return None

    @staticmethod
    def _split_ver(s):
        if not s:
            return None
        parts = re.split(r"[-,. ]", s)
        parts2 = []
        for i in parts:
            try:
                parts2.append(int(i))
            except ValueError:
                parts2.append(i)
        if len(parts2) > 3 and parts2[-2] == "beta":
            parts2[-3] -= 1
            parts2[-2] = 99
        return tuple(parts2)

    @classmethod
    def parse_ver(cls, version):
        expr = version.replace("&&", " and ").replace("||", " or ")

        base_loc = {j: i for row in cls.MATRIX.values() for i, j in enumerate(row)}

        def check_ver(ver):
            loc = dict(base_loc)
            for k, v in ver.items():
                loc[k] = cls.MATRIX[k].index(v)
            return eval(expr, None, loc)

        return check_ver

    @classmethod
    def check(cls, version):
        return cls.parse_ver(version)(cls._version)

    def _active(self):
        return self.vcheck(self._version)

    def _parse(self, stream, context, path):
        if not self._active():
            return None
        obj = self.subcon._parse(stream, context, path)
        return obj

    def _build(self, obj, stream, context, path):
        if not self._active():
            return None
        return self.subcon._build(obj, stream, context, path)

    def _sizeof(self, context, path):
        if not self._active():
            return 0
        return self.subcon._sizeof(context, path)

    @classmethod
    def set_version_key(cls, key, version):
        cls._version[key] = version

    @classmethod
    def set_version(cls, u):
        cls.set_version_key("V", u.version)
        cls.set_version_key("G", u.adt["/arm-io"].soc_generation.replace("H", "G"))

def show_struct_trace(log=print):
    for addr, desc in sorted(list(g_struct_trace)):
        log(f"{addr:>#18x}: {desc}")

__all__ = ["ConstructClass", "ConstructValueClass", "Dec", "ROPointer", "show_struct_trace", "ZPadding", "Ver"]

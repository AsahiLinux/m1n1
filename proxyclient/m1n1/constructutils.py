from construct import *
from construct.core import evaluate
from construct.lib import HexDisplayedInteger
from .utils import Reloadable, ReloadableMeta
import inspect
import textwrap

def recusive_reload(obj):
    if isinstance(obj, Construct) and hasattr(obj, 'subcons'):
        # Construct types that have lists
        for i, item in enumerate(obj.subcons):
            if inspect.isclass(item):
                if issubclass(item, Reloadable):
                    obj.subcons[i] = item._reloadcls()
            else:
                if isinstance(item, Construct):
                    recusive_reload(item)

    if isinstance(obj, Construct) and hasattr(obj, 'cases'):
        # Construct types that have lists
        for i, item in obj.cases.items():
            if inspect.isclass(item):
                if issubclass(item, Reloadable):
                    obj.cases[i] = item._reloadcls()
            else:
                if isinstance(item, Construct):
                    recusive_reload(item)

    for field in dir(obj):
        value = getattr(obj, field)
        if inspect.isclass(value):
            if issubclass(value, Reloadable):
                setattr(obj, field, value._reloadcls())
        else:
            if isinstance(value, Construct):
                recusive_reload(value)

def str_value(value):
    if isinstance(value, DecDisplayedInteger):
        return str(value)
    if isinstance(value, int):
        return f"{value:#x}"
    if isinstance(value, ListContainer):
        if len(value) <= 16:
            return "[" + ", ".join(map(str_value, value)) + "]"
        else:
            sv = ["[\n"]
            for off in range(0, len(value), 16):
                sv.append("  " + ", ".join(map(str_value, value[off:off+16])) + ",\n")
            sv.append("]\n")
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

class ConstructClassException(Exception):
    pass


# We need to inherrit Construct as a metaclass so things like If and Select will work
class ReloadableConstructMeta(ReloadableMeta, Construct):

    def __new__(cls, name, bases, attrs):
        cls = super().__new__(cls, name, bases, attrs)
        cls.name = name
        try:
            cls.flagbuildnone = cls.subcon.flagbuildnone
        except AttributeError:
            cls.flagbuildnone = False

        cls.docs = None

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

    parsed = None

    def Apply(self, dict=None, **kwargs):
        if dict is None:
            dict = kwargs

        for key in dict:
            if not key.startswith('_'):
                setattr(self, key, dict[key])
                self._keys += [key]

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
        return obj

    @classmethod
    def _sizeof(cls, context, path):
        return cls.subcon._sizeof(context, f"{path} -> {cls.name}")

    @classmethod
    def _reloadcls(cls, force=False):
        newcls = super()._reloadcls(force)
        recusive_reload(newcls.subcon)
        return newcls

    def _apply(self, obj):
        raise NotImplementedError()

    @classmethod
    def _parse(cls, stream, context, path):
        addr = stream.tell()
        obj = cls.subcon._parse(stream, context, path)

        # Don't instance Selects
        if isinstance(cls.subcon, Select):
            return obj

        # Skip calling the __init__ constructor, so that it can be used for building
        # Use parsed instead, if you need a post-parsing constructor
        self = cls.__new__(cls)
        self._off = {}
        self._meta = {}

        if isinstance(cls.subcon, Struct):
            subaddr = addr
            for subcon in cls.subcon.subcons:
                try:
                    sizeof = subcon.sizeof()
                except:
                    break
                if isinstance(subcon, Renamed):
                    name = subcon.name
                    subcon = subcon.subcon
                    self._off[name] = subaddr - addr, sizeof
                    if getattr(stream, "meta_fn", None):
                        meta = stream.meta_fn(subaddr, sizeof)
                        if meta is not None:
                            self._meta[name] = meta
                subaddr += sizeof

        # These might be useful later
        self._stream = stream
        self._addr = addr

        self._apply(obj)

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

    def __str__(self, ignore=[]) -> str:

        str = f"{self.__class__.__name__} @ 0x{self._addr:x}:\n"

        for key in self:
            if key in ignore or key.startswith('_'):
                continue
            value = getattr(self, key)
            val_repr = str_value(value)
            off = ""
            meta = ""
            if key in self._off:
                offv, sizeof = self._off[key]
                off = f"\x1b[32m[{offv:3x}.{sizeof:3x}]\x1b[m "
            if key in self._meta:
                meta = f" \x1b[34m{self._meta[key]}\x1b[m"
            if '\n' in val_repr:
                val_repr = textwrap.indent(val_repr, ' ' * 6)
                if not val_repr.endswith('\n'):
                    val_repr += '\n'
                str += f"   {off}\x1b[95m{key}\x1b[m ={meta}\n{val_repr}"
            else:
                str += f"   {off}\x1b[95m{key}\x1b[m = {val_repr}{meta}\n"

        return str

    @classmethod
    def _build_prepare(cls, obj):
        if isinstance(cls.subcon, Struct):
            for subcon in cls.subcon.subcons:
                if not isinstance(subcon, Renamed):
                    continue
                name = subcon.name
                subcon = subcon.subcon
                if not isinstance(subcon, Pointer):
                    continue
                try:
                    addr = getattr(obj, name)._addr
                    if addr is not None:
                        setattr(obj, subcon.offset.__getfield__(), addr)
                except:
                    pass

    def _apply(self, obj):
        self.update(obj)


class ConstructValueClass(ConstructClassBase):
    """ Same as Construct, but for subcons that are single values, rather than containers

        the value is stored as .value
    """

    def __str__(self) -> str:
        str = f"{self.__class__.__name__} @ 0x{self._addr:x}:"
        str += f"\t{str_value(self.value)}"
        return str

    @classmethod
    def _build(cls, obj, stream, context, path):
        return super()._build(cls, obj.value, stream, context, path)

    def _apply(self, obj):
        self.value = obj

__all__ = ["ConstructClass", "ConstructValueClass", "Dec"]

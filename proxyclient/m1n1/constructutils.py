from construct import *
from construct.core import evaluate
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

    for field in dir(obj):
        value = getattr(obj, field)
        if inspect.isclass(value):
            if issubclass(value, Reloadable):
                setattr(obj, field, value._reloadcls())
        else:
            if isinstance(value, Construct):
                recusive_reload(value)

def str_value(value):
    if isinstance(value, int):
        return f"{value:#x}"
    else:
        return str(value)


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

        # These might be useful later
        self._stream = stream
        self._addr = addr

        self._apply(obj)

        return self

    def build_stream(self, obj=None, stream=None, **contextkw):
        assert stream != None
        if obj is None:
            obj = self

        return Construct.build_stream(self, obj, stream, **contextkw)

    def build(self, obj=None, **contextkw):
        if obj is None:
            obj = self

        return Construct.build(self, obj, **contextkw)

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
            if '\n' in val_repr:
                val_repr = textwrap.indent(val_repr, ' ' * 6)
                if not val_repr.endswith('\n'):
                    val_repr += '\n'
                str += f"   {key} =\n{val_repr}"
            else:
                str += f"   {key} = {val_repr}\n"

        return str

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

__all__ = ["ConstructClass", "ConstructValueClass"]

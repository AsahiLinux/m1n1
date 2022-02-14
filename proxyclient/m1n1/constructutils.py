from construct import *
from construct.core import evaluate
from .utils import Reloadable, ReloadableMeta
import inspect


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

def repr_value(value):
    if isinstance(value, int):
        return f"0x{value:x}"
    else:
        return repr(value)

# We need to inherrit Construct as a metaclass so things like If and Select will work
class ReloadableConstructMeta(ReloadableMeta, Construct):

    def __new__(cls, name, bases, attrs):
        cls = super().__new__(cls, name, bases, attrs)
        cls.name = name
        return cls


class ConstructClass(Reloadable, metaclass=ReloadableConstructMeta):
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

    flagbuildnone = True
    parsed = None

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

        # Copy everything across from the constructed container/value
        if isinstance(obj, Container):
            for key in obj:
                setattr(self, key, obj[key])
            self._keys = [k for k in obj.keys() if k != "_io"]
        else:
            self.value = obj

        return self

    @classmethod
    def _reloadcls(cls):
        newcls = super()._reloadcls()
        recusive_reload(newcls.subcon)
        return newcls

    def __repr__(self, ignore=[]) -> str:

        str = f"{self.__class__.__name__} @ 0x{self._addr:x}:"

        if hasattr(self, '_keys'):
            str += "\n"
            for key in self._keys:
                if key in ignore:
                    continue
                value = getattr(self, key)
                str += f"\t{key} = {repr_value(value)}\n"
        else:
            str += f"\t{repr_value(self.value)}"
        return str

__all__ = ["ConstructClass"]
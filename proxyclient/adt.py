# SPDX-License-Identifier: MIT
import itertools
from construct import *

ADTPropertyStruct = Struct(
    "name" / PaddedString(32, "ascii"),
    "size" / Int32ul,
    "value" / Bytes(this.size & 0x7fffffff)
)

ADTNodeStruct = Struct(
    "property_count" / Int32ul,
    "child_count" / Int32ul,
    "properties" / Array(this.property_count, Aligned(4, ADTPropertyStruct)),
    "children" / Array(this.child_count, LazyBound(lambda: ADTNodeStruct))
)

ADTStringList = GreedyRange(CString("ascii"))

ADT2Tuple = Array(2, Hex(Int64ul))
ADT3Tuple = Array(3, Hex(Int64ul))

STD_PROPERTIES = {
    "cpu-impl-reg": GreedyRange(ADT2Tuple),
    "name": CString("ascii"),
    "compatible": ADTStringList,
    "model": CString("ascii"),
    "#size-cells": Int32ul,
    "#address-cells": Int32ul,
}

def parse_prop(node, path, name, v):
    t = None

    if name == "reg":
        n = node._parent
        while n is not None and n._parent is not None:
            if "ranges" not in n._properties:
                break
            n = n._parent
        else:
            try:
                ac, sc = node._parent.addr_cells, node._parent.size_cells
                at = Int64ul if ac == 2 else Array(ac, Int32ul)
                st = Int64ul if sc == 2 else Array(sc, Int32ul)
                t = GreedyRange(Struct("addr" / at, "size" / st))
            except:
                return None, v

    elif name == "ranges":
        try:
            ac, sc = node.addr_cells, node.size_cells
            pac, _ = node._parent.addr_cells, node._parent.size_cells
            at = Int64ul if ac == 2 else Array(ac, Int32ul)
            pat = Int64ul if pac == 2 else Array(pac, Int32ul)
            st = Int64ul if sc == 2 else Array(sc, Int32ul)
            t = GreedyRange(Struct("bus_addr" / pat, "parent_addr" / at, "size" / st))
        except:
            return None, v

    if t is not None:
        v = t.parse(v)
        return t, v

    if name in STD_PROPERTIES:
        t = STD_PROPERTIES[name]
    elif v and v[-1] == 0 and all(0x20 <= i <= 0x7e for i in v[:-1]):
        t = CString("ascii")
    elif len(v) == 4:
        t = Int32ul
    elif len(v) == 8:
        t = Int64ul
    elif len(v) == 16 and all(v[i] == 0 for i in (6, 7, 14, 15)):
        t = ADT2Tuple

    if t is not None:
        v = t.parse(v)

    return t, v

def build_prop(path, name, v, t=None):
    if t is not None:
        return t.build(v)

    if isinstance(v, bytes):
        return v

    if name in STD_PROPERTIES:
        t = STD_PROPERTIES[name]
    elif isinstance(v, str):
        t = CString("ascii")
    elif isinstance(v, int):
        t = Int32ul
    elif isinstance(v, tuple) and all(isinstance(i, int) for i in v):
        t = Array(len(v), Int32ul)

    return t.build(v)

class ADTNode:
    def __init__(self, val=None, path="/", parent=None):
        self._children = []
        self._properties = {}
        self._types = {}
        self._parent_path = path
        self._parent = parent

        if val is not None:
            for p in val.properties:
                if p.name == "name":
                    _name = p.value.decode("ascii").rstrip("\0")
                    break
            else:
                raise ValueError(f"Node in {path} has no name!")

            path = self._parent_path + _name

            for p in val.properties:
                self._types[p.name], self._properties[p.name] = parse_prop(self, path, p.name, p.value)

            # Second pass
            for k, v in self._types.items():
                if v is None:
                    self._types[k], self._properties[k] = parse_prop(self, path, k, self._properties[k])

            for c in val.children:
                node = ADTNode(c, f"{self._path}/", parent=self)
                self._children.append(node)

    @property
    def _path(self):
        return self._parent_path + self.name

    def __getitem__(self, item):
        if isinstance(item, str):
            for i in self._children:
                if i.name == item:
                    return i
            raise KeyError(f"Child node '{item}' not found")
        return self._children[item]

    def __setitem__(self, item, value):
        if isinstance(item, str):
            for i, c in enumerate(self._children):
                if c.name == item:
                    self._children[i] = value
                    break
            else:
                self._children.append(value)
        else:
            self._children[item] = value

    def __delitem__(self, item):
        if isinstance(item, str):
            for i, c in enumerate(self._children):
                if c.name == item:
                    del self._children[i]
                    return
            raise KeyError(f"Child node '{item}' not found")

        del self._children[item]

    def __getattr__(self, attr):
        attr = attr.replace("_", "-")
        return self._properties[attr]

    def __setattr__(self, attr, value):
        if attr[0] == "_":
            self.__dict__[attr] = value
            return
        attr = attr.replace("_", "-")
        self._properties[attr] = value

    def __delattr__(self, attr):
        if attr[0] == "_":
            del self.__dict__[attr]
            return
        del self._properties[attr]

    @property
    def addr_cells(self):
        return self._properties["#addr-cells"]

    @property
    def size_cells(self):
        return self._properties["#size-cells"]

    def _fmt_prop(self, v):
        if isinstance(v, ListContainer):
            return f"[{', '.join(self._fmt_prop(i) for i in v)}]"
        else:
            return str(v)

    def __str__(self, t=""):
        return "\n".join([
            t + f"{self.name} {{",
            *(t + f"    {k} = {self._fmt_prop(v)}" for k, v in self._properties.items() if k != "name"),
            "",
            *(i.__str__(t + "    ") for i in self._children),
            t + "}"
        ])

    def __iter__(self):
        return iter(self._children)

    def get_reg(self, idx):
        reg = self.reg[idx]
        addr = reg.addr
        size = reg.size

        node = self._parent
        while node is not None:
            if "ranges" not in node._properties:
                break
            for r in node.ranges:
                if r.bus_addr <= addr < (r.bus_addr + r.size):
                    addr = addr - r.bus_addr + r.parent_addr
                    break
            node = node._parent

        return addr, size

    def tostruct(self):
        properties = []
        for k,v in itertools.chain(self._properties.items()):
            value = build_prop(self._path, k, v, t=self._types.get(k, None))
            properties.append({
                "name": k,
                "size": len(value),
                "value": value
            })

        data = {
            "property_count": len(self._properties),
            "child_count": len(self._children),
            "properties": properties,
            "children": [c.tostruct() for c in self._children]
        }
        return data

    def build(self):
        return ADTNodeStruct.build(self.tostruct())

def load_adt(data):
    return ADTNode(ADTNodeStruct.parse(data))

if __name__ == "__main__":
    import sys
    adt_data = open(sys.argv[1], "rb").read()
    adt = load_adt(adt_data)
    print(adt)
    new_data = adt.build()
    if len(sys.argv) > 2:
        with open(sys.argv[2], "wb") as fd:
            fd.write(new_data)
    assert new_data == adt_data[:len(new_data)]
    assert adt_data[len(new_data):] == bytes(len(adt_data) - len(new_data))

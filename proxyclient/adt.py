# SPDX-License-Identifier: MIT
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

ADT2Tuple = Array(2, Int64ul)

STD_PROPERTIES = {
    "compatible": ADTStringList,
    "model": CString("ascii"),
    "#size-cells": Int32ul,
    "#address-cells": Int32ul,
}

def parse_prop(path, name, v):
    if name in STD_PROPERTIES:
        return STD_PROPERTIES[name].parse(v)

    if v and v[-1] == 0 and all(0x20 <= i <= 0x7e for i in v[:-1]):
        return CString("ascii").parse(v)

    if len(v) == 4:
        return Int32ul.parse(v)

    if len(v) == 8:
        return Int64ul.parse(v)

    if len(v) == 16 and all(v[i] == 0 for i in (6, 7, 14, 15)):
        return ADT2Tuple.parse(v)

    return v

class ADTNode:
    def __init__(self, val=None, path="/"):
        self.name = None
        self.children = []
        self.properties = {}



        if val is not None:
            for p in val.properties:
                if p.name == "name":
                    self.name = p.value.decode("ascii").rstrip("\0")
                    break
            else:
                raise ValueError(f"Node in {path} has no name!")

            self.path = path + self.name

            for p in val.properties:
                if p.name == "name":
                    continue
                self.properties[p.name] = parse_prop(self.path, p.name, p.value)

            for c in val.children:
                self.children.append(ADTNode(c, f"{self.path}/"))

    def __getitem__(self, item):
        if isinstance(item, str):
            for i in self.children:
                if i.name == item:
                    return i
            raise KeyError(f"Child node '{item}' not found")
        return self.children[item]

    def __getattr__(self, attr):
        attr = attr.replace("_", "-")
        return self.properties[attr]

    def __str__(self, t=""):
        return "\n".join([
            t + f"{self.name} {{",
            *(t + f"    {k} = {repr(v)}" for k, v in self.properties.items()),
            "",
            *(i.__str__(t + "    ") for i in self.children),
            t+ "}"
        ])

    def __iter__(self):
        return iter(self.children)

def load_adt(data):
    return ADTNode(ADTNodeStruct.parse(data))

if __name__ == "__main__":
    import sys
    adt_data = open(sys.argv[1], "rb").read()
    adt = load_adt(adt_data)
    print(adt)

# SPDX-License-Identifier: MIT
import itertools, fnmatch, sys
from construct import *

from .utils import AddrLookup, FourCC, SafeGreedyRange

__all__ = ["load_adt"]

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

ADTStringList = SafeGreedyRange(CString("ascii"))

ADT2Tuple = Array(2, Hex(Int64ul))
ADT3Tuple = Array(3, Hex(Int64ul))

Function = Struct(
    "phandle" / Int32ul,
    "name" / FourCC,
    "args" / SafeGreedyRange(Int32ul),
)

STD_PROPERTIES = {
    "cpu-impl-reg": ADT2Tuple,
    "name": CString("ascii"),
    "compatible": ADTStringList,
    "model": CString("ascii"),
    "#size-cells": Int32ul,
    "#address-cells": Int32ul,
    "clock-ids": SafeGreedyRange(Int32ul),
    "clock-gates": SafeGreedyRange(Int32ul),
    "power-gates": SafeGreedyRange(Int32ul),
}

PMAPIORanges = SafeGreedyRange(Struct(
    "addr" / Hex(Int64ul),
    "size" / Hex(Int64ul),
    "flags" / Hex(Int32ul),
    "name" / FourCC,
))

PMGRPSRegs = SafeGreedyRange(Struct(
    "reg" / Int32ul,
    "offset" / Hex(Int32ul),
    "mask" / Hex(Int32ul),
))

PMGRPerfRegs = SafeGreedyRange(Struct(
    "reg" / Int32ul,
    "offset" / Hex(Int32ul),
    "size" / Hex(Int32ul),
    "unk" / Int32ul,
))

PMGRPWRGateRegs = SafeGreedyRange(Struct(
    "reg" / Int32ul,
    "offset" / Hex(Int32ul),
    "mask" / Hex(Int32ul),
    "unk" / Hex(Int32ul),
))

PMGRDeviceFlags = BitStruct(
    "b7" / Flag,
    "b6" / Flag,
    "perf" / Flag,
    "no_ps" / Flag,
    "critical" / Flag,
    "b2" / Flag,
    "notify_pmp" / Flag,
    "on" / Flag,
)

PMGRDevices = SafeGreedyRange(Struct(
    "flags" / PMGRDeviceFlags,
    "unk1_0" / Int8ul,
    "unk1_1" / Int8ul,
    "unk1_2" / Int8ul,
    "parents" / Array(2, Int16ul),
    "perf_idx" / Int8ul,
    "perf_block" / Int8ul,
    "psidx" / Int8ul,
    "psreg" / Int8ul,
    "unk2_0" / Int16ul,
    "pd" / Int8ul,
    "ps_cfg16" / Int8ul,
    Const(0, Int32ul),
    Const(0, Int32ul),
    "unk2_3" / Int16ul,
    "id" / Int16ul,
    "unk3" / Int32ul,
    "name" / PaddedString(16, "ascii")
))

PMGRClocks = SafeGreedyRange(Struct(
    "perf_idx" / Int8ul,
    "perf_block" / Int8ul,
    "unk" / Int8ul,
    "id" / Int8ul,
    Const(0, Int32ul),
    "name" / PaddedString(16, "ascii"),
))

PMGRPowerDomains = SafeGreedyRange(Struct(
    "unk" / Const(0, Int8ul),
    "perf_idx" / Int8ul,
    "perf_block" / Int8ul,
    "id" / Int8ul,
    Const(0, Int32ul),
    "name" / PaddedString(16, "ascii"),
))

PMGRDeviceBridges = SafeGreedyRange(Struct(
    "idx" / Int32ub,
    "subdevs" / HexDump(Bytes(0x48)),
))

PMGREvents = SafeGreedyRange(Struct(
    "unk1" / Int8ul,
    "unk2" / Int8ul,
    "unk3" / Int8ul,
    "id" / Int8ul,
    "perf2_idx" / Int8ul,
    "perf2_block" / Int8ul,
    "perf_idx" / Int8ul,
    "perf_block" / Int8ul,
    "name" / PaddedString(16, "ascii"),
))

GPUPerfState = Struct(
    "freq" / Int32ul,
    "volt" / Int32ul,
)

SpeakerConfig = Struct(
    "rx_slot" / Int8ul,
    "amp_gain" / Int8ul,
    "vsense_slot" / Int8ul,
    "isense_slot" / Int8ul,
)

DCBlockerConfig = Struct(
    "dc_blk0" / Hex(Int8ul),
    "dc_blk1" / Hex(Int8ul),
    "pad" / Hex(Int16ul),
)

Coef = ExprAdapter(Int32ul,
                   lambda x, ctx: (x - ((x & 0x1000000) << 1)) / 65536,
                   lambda x, ctx: int(round(x * 65536)) & 0x1ffffff)

MTRPolynomFuseAGX = GreedyRange(Struct(
    "id" / Int32ul,
    "data" / Prefixed(Int32ul, GreedyRange(Coef)),
))

DEV_PROPERTIES = {
    "pmgr": {
        "*": {
            "clusters": SafeGreedyRange(Int32ul),
            "devices": PMGRDevices,
            "ps-regs": PMGRPSRegs,
            "perf-regs": PMGRPerfRegs,
            "pwrgate-regs": PMGRPWRGateRegs,
            "power-domains": PMGRPowerDomains,
            "clocks": PMGRClocks,
            "device-bridges": PMGRDeviceBridges,
            "voltage-states*": SafeGreedyRange(Int32ul),
            "events": PMGREvents,
            "mtr-polynom-fuse-agx": MTRPolynomFuseAGX,
        }
    },
    "clpc": {
        "*": {
            "events": SafeGreedyRange(Int32ul),
            "devices": SafeGreedyRange(Int32ul),
        }
    },
    "soc-tuner": {
        "*": {
            "device-set-*": SafeGreedyRange(Int32ul),
            "mcc-configs": SafeGreedyRange(Int32ul),
        }
    },
    "mcc": {
        "*": {
            "dramcfg-data": SafeGreedyRange(Int32ul),
            "config-data": SafeGreedyRange(Int32ul),
        }
    },
    "*pmu*": {
        "*": {
            "info-*name*": CString("ascii"),
            "info-*": SafeGreedyRange(Hex(Int32ul)),
        },
    },
    "stockholm-spmi": {
        "*": {
            "required-functions": ADTStringList,
        },
    },
    "sgx": {
        "*": {
            "perf-states*": SafeGreedyRange(GPUPerfState),
            "*-kp": Float32l,
            "*-ki": Float32l,
            "*-ki-*": Float32l,
            "*-gain*": Float32l,
            "*-scale*": Float32l,
        }
    },
    "arm-io": {
        "*": {
            "clock-frequencies": SafeGreedyRange(Int32ul),
            "clock-frequencies-regs": SafeGreedyRange(Hex(Int64ul)),
            "clock-frequencies-nclk": SafeGreedyRange(Int32ul),
        },
    },
    "defaults": {
        "*": {
            "pmap-io-ranges": PMAPIORanges,
        }
    },
    "audio-*": {
        "*": {
            "speaker-config": SafeGreedyRange(SpeakerConfig),
            "amp-dcblocker-config": DCBlockerConfig,
        },
    },
    "*aop-audio*": {
        "*": {
            "clockSource": FourCC,
            "identifier": FourCC,
        },
    },
    "*alc?/audio-leap-mic*": {
        "*": {
            "audio-stream-formatter": FourCC,
        }
    }
}

def parse_prop(node, path, node_name, name, v, is_template=False):
    t = None

    if is_template:
        t = CString("ascii")

    dev_props = None
    for k, pt in DEV_PROPERTIES.items():
        if fnmatch.fnmatch(path, k):
            dev_props = pt
            break

    if not dev_props:
        for k, pt in DEV_PROPERTIES.items():
            if fnmatch.fnmatch(node_name, k):
                dev_props = pt
                break

    possible_match = False
    if dev_props:
        for compat_match, cprops in dev_props.items():
            for k, pt in cprops.items():
                if fnmatch.fnmatch(name, k):
                    possible_match = True
                    break

    if possible_match:
        try:
            compat = node.compatible[0]
        except AttributeError:
            compat = ""

        for compat_match, cprops in dev_props.items():
            if fnmatch.fnmatch(compat, compat_match):
                for k, pt in cprops.items():
                    if fnmatch.fnmatch(name, k):
                        t = pt
                        break
                else:
                    continue
                break

    if v == b'' or v is None:
        return None, None

    if name.startswith("function-"):
        if len(v) == 4:
            t = FourCC
        else:
            t = Function

    if name == "reg" and path != "/device-tree/memory":
        n = node._parent
        while n is not None and n._parent is not None:
            if "ranges" not in n._properties:
                break
            n = n._parent
        else:
            ac, sc = node._parent.address_cells, node._parent.size_cells
            at = Hex(Int64ul) if ac == 2 else Array(ac, Hex(Int32ul))
            st = Hex(Int64ul) if sc == 2 else Array(sc, Hex(Int32ul))
            t = SafeGreedyRange(Struct("addr" / at, "size" / st))
            if len(v) % ((ac + sc) * 4):
                t = None

    elif name == "ranges":
        try:
            ac, sc = node.address_cells, node.size_cells
        except AttributeError:
            return None, v
        pac, _ = node._parent.address_cells, node._parent.size_cells
        at = Hex(Int64ul) if ac == 2 else Array(ac, Hex(Int32ul))
        pat = Hex(Int64ul) if pac == 2 else Array(pac, Hex(Int32ul))
        st = Hex(Int64ul) if sc == 2 else Array(sc, Hex(Int32ul))
        t = SafeGreedyRange(Struct("bus_addr" / at, "parent_addr" / pat, "size" / st))

    elif name == "interrupts":
        # parse "interrupts" as Array of Int32ul, wrong for nodes whose
        # "interrupt-parent" has "interrupt-cells" = 2
        # parsing this correctly would require a second pass
        t = Array(len(v) // 4, Int32ul)

    if t is not None:
        v = Sequence(t, Terminated).parse(v)[0]
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
        try:
            v = Sequence(t, Terminated).parse(v)[0]
        except:
            print("Failed to parse:", path, name, v.hex())
            raise

    return t, v

def build_prop(path, name, v, t=None):
    if v is None:
        return b''
    if t is not None:
        return t.build(v)

    if isinstance(v, bytes):
        return v

    if name in STD_PROPERTIES:
        t = STD_PROPERTIES[name]
    elif isinstance(v, str):
        t = CString("ascii")
    elif isinstance(v, int):
        if v > 0xffffffff:
            t = Int64ul
        else:
            t = Int32ul
    elif isinstance(v, float):
        t = Float32l
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
                is_template = bool(p.size & 0x80000000)
                try:
                    t, v = parse_prop(self, path, _name, p.name, p.value, is_template)
                    self._types[p.name] = t, is_template
                    self._properties[p.name] = v
                except Exception as e:
                    print(f"Exception parsing {path}.{p.name} value {p.value.hex()}:", file=sys.stderr)
                    raise

            # Second pass
            for k, (t, is_template) in self._types.items():
                if t is None:
                    t, v = parse_prop(self, path, _name, k, self._properties[k], is_template)
                    self._types[k] = t, is_template
                    self._properties[k] = v

            for c in val.children:
                node = ADTNode(c, f"{self._path}/", parent=self)
                self._children.append(node)

    @property
    def _path(self):
        return self._parent_path + self.name

    def __getitem__(self, item):
        if isinstance(item, str):
            while item.startswith("/"):
                item = item[1:]
            if "/" in item:
                a, b = item.split("/", 1)
                return self[a][b]
            for i in self._children:
                if i.name == item:
                    return i
            raise KeyError(f"Child node '{item}' not found")
        return self._children[item]

    def __setitem__(self, item, value):
        if isinstance(item, str):
            while item.startswith("/"):
                item = item[1:]
            if "/" in item:
                a, b = item.split("/", 1)
                self[a][b] = value
                return
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
            while item.startswith("/"):
                item = item[1:]
            if "/" in item:
                a, b = item.split("/", 1)
                del self[a][b]
                return
            for i, c in enumerate(self._children):
                if c.name == item:
                    del self._children[i]
                    return
            raise KeyError(f"Child node '{item}' not found")

        del self._children[item]

    def __getattr__(self, attr):
        attr = attr.replace("_", "-")
        attr = attr.replace("--", "_")
        if attr in self._properties:
            return self._properties[attr]
        raise AttributeError(attr)

    def __setattr__(self, attr, value):
        if attr[0] == "_":
            self.__dict__[attr] = value
            return
        attr = attr.replace("_", "-")
        attr = attr.replace("--", "_")
        self._properties[attr] = value

    def __delattr__(self, attr):
        if attr[0] == "_":
            del self.__dict__[attr]
            return
        del self._properties[attr]

    def getprop(self, name, default=None):
        return self._properties.get(name, default)

    @property
    def address_cells(self):
        try:
            return self._properties["#address-cells"]
        except KeyError:
            raise AttributeError("#address-cells")

    @property
    def size_cells(self):
        try:
            return self._properties["#size-cells"]
        except KeyError:
            raise AttributeError("#size-cells")

    @property
    def interrupt_cells(self):
        try:
            return self._properties["#interrupt-cells"]
        except KeyError:
            raise AttributeError("#interrupt-cells")

    def _fmt_prop(self, k, v):
        t, is_template = self._types.get(k, (None, False))
        if is_template:
            return f"<< {v} >>"
        elif isinstance(v, ListContainer):
            return f"[{', '.join(self._fmt_prop(k, i) for i in v)}]"
        elif isinstance(v, bytes):
            if all(i == 0 for i in v):
                return f"zeroes({len(v):#x})"
            else:
                return v.hex()
        elif k.startswith("function-"):
            if isinstance(v, str):
                return f"{v}()"
            elif v is None:
                return f"None"
            else:
                args = []
                for arg in v.args:
                    b = arg.to_bytes(4, "big")
                    is_ascii = all(0x20 <= c <= 0x7e for c in b)
                    args.append(f"{arg:#x}" if not is_ascii else f"'{b.decode('ascii')}'")
                return f"{v.phandle}:{v.name}({', '.join(args)})"
            name.startswith("function-")
        else:
            return str(v)

    def __str__(self, t=""):
        return "\n".join([
            t + f"{self.name} {{",
            *(t + f"    {k} = {self._fmt_prop(k, v)}" for k, v in self._properties.items() if k != "name"),
            "",
            *(i.__str__(t + "    ") for i in self._children),
            t + "}"
        ])

    def __repr__(self):
        return f"<ADTNode {self.name}>"

    def __iter__(self):
        return iter(self._children)

    def get_reg(self, idx):
        reg = self.reg[idx]
        addr = reg.addr
        size = reg.size

        return self._parent.translate(addr), size

    def translate(self, addr):
        node = self
        while node is not None:
            if "ranges" not in node._properties:
                break
            for r in node.ranges:
                ba = r.bus_addr
                # PCIe special case, because Apple really broke
                # the spec here with their little endian antics
                if isinstance(ba, list) and len(ba) == 3:
                    ba = (ba[0] << 64) | (ba[2] << 32) | ba[1]
                if ba <= addr < (ba + r.size):
                    addr = addr - ba + r.parent_addr
                    break
            node = node._parent

        return addr

    def tostruct(self):
        properties = []
        for k,v in itertools.chain(self._properties.items()):
            t, is_template = self._types.get(k, (None, False))
            value = build_prop(self._path, k, v, t=t)
            properties.append({
                "name": k,
                "size": len(value) | (0x80000000 if is_template else 0),
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

    def walk_tree(self):
        yield self
        for child in self:
            yield from child

    def build_addr_lookup(self):
        lookup = AddrLookup()
        for node in self.walk_tree():
            reg = getattr(node, 'reg', None)
            if not isinstance(reg, list):
                continue

            for index in range(len(reg)):
                try:
                    addr, size = node.get_reg(index)
                except AttributeError:
                    continue
                if size == 0:
                    continue
                lookup.add(range(addr, addr + size), node.name + f"[{index}]")

        return lookup

def load_adt(data):
    return ADTNode(ADTNodeStruct.parse(data))

if __name__ == "__main__":
    import sys, argparse, pathlib

    parser = argparse.ArgumentParser(description='ADT test for m1n1')
    parser.add_argument('input', type=pathlib.Path)
    parser.add_argument('output', nargs='?', type=pathlib.Path)
    parser.add_argument('-r', '--retrieve', help='retrieve and store the adt from m1n1', action='store_true')
    parser.add_argument('-a', '--dump-addr', help='dump address lookup table', action='store_true')
    args = parser.parse_args()

    if args.retrieve:
        if args.input.exists():
            print('Error "{}" exists!'.format(args.input))
            sys.exit()

        from .setup import *
        adt_data = u.get_adt()
        args.input.write_bytes(adt_data)
    else:
        adt_data = args.input.read_bytes()

    adt = load_adt(adt_data)
    print(adt)
    new_data = adt.build()
    if args.output is not None:
        args.output.write_bytes(new_data)
    assert new_data == adt_data[:len(new_data)]
    assert adt_data[len(new_data):] == bytes(len(adt_data) - len(new_data))

    if args.dump_addr:
        print("Address lookup table:")
        print(adt.build_addr_lookup())

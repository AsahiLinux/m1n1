# SPDX-License-Identifier: MIT
import re
from construct import *

__all__ = []

DebuggerState = Struct(
    "panic_options"             / Hex(Int64ul),
    "current_op"                / Hex(Int32ul),
    "proceed_on_sync_failre"    / Int32ul,
    "message"                   / Hex(Int64ul),
    "panic_str"                 / Hex(Int64ul),
    "panic_args"                / Hex(Int64ul),
    "panic_data_ptr"            / Hex(Int64ul),
    "panic_caller"              / Hex(Int64ul),
    "entry_count"               / Hex(Int32ul),
    "kern_return"               / Hex(Int32sl)
)

# Darwin va_list is just a stack pointer...
VaList = Struct(
    "stack" / Hex(Int64ul),
)

def decode_debugger_state(u, ctx):
    p = u.proxy
    iface = u.iface

    def hv_readmem(addr, size):
        addr = p.hv_translate(addr, False, False)
        assert addr != 0
        return iface.readmem(addr, size)

    p_state = p.hv_translate(ctx.regs[25], False, False)
    assert p_state != 0
    di = iface.readstruct(p_state, DebuggerState)
    print(di)

    message = hv_readmem(di.message, 1024).split(b"\x00")[0].decode("ascii")
    print()
    print(f"Message: {message}")

    print("===== Panic string =====")
    decode_panic(u, di.panic_str, di.panic_args)
    print("========================")

def decode_panic_call(u, ctx):
    decode_panic(u, ctx.regs[0], ctx.regs[1])

def decode_panic(u, p_string, p_args):
    p = u.proxy
    iface = u.iface

    def hv_readmem(addr, size):
        addr = p.hv_translate(addr, False, False)
        assert addr != 0
        return iface.readmem(addr, size)

    string = hv_readmem(p_string, 1024).split(b"\x00")[0].decode("ascii")
    p_args = p.hv_translate(p_args, False, False)

    args = iface.readstruct(p_args, VaList)

    stack = hv_readmem(args.stack, 504)

    def va_arg(t):
        nonlocal stack
        d, stack = stack[:8], stack[8:]
        return t.parse(d)

    utypes = {
        "hh": Int8ul,
        "h": Int16ul,
        None: Int32ul,
        "l": Int64ul,
        "ll": Int64ul,
        "q": Int64ul,
        "s": Int64ul,
        "t": Int64ul,
    }

    stypes = {
        "hh": Int8sl,
        "h": Int16sl,
        None: Int32sl,
        "l": Int64sl,
        "ll": Int64sl,
        "q": Int64sl,
        "s": Int64sl,
        "t": Int64sl,
    }

    #print(string)

    def format_arg(match):
        pat, flags, width, mod, conv = match.group(0, 1, 2, 3, 4)
        if conv == "%":
            return "%"
        elif conv == "s":
            return hv_readmem(va_arg(Int64ul), 1024).split(b"\x00")[0].decode("ascii")
        elif conv in "di":
            v = va_arg(stypes[mod])
            return f"%{flags or ''}{width or ''}{conv or ''}" % v
        elif conv in "ouxX":
            v = va_arg(utypes[mod])
            return f"%{flags or ''}{width or ''}{conv or ''}" % v
        elif conv in "p":
            return f"0x{va_arg(Int64ul):x}"
        else:
            return f"[{pat!r}:{va_arg(Int64ul):x}]"

    string = re.sub('%([-#0 +]*)([1-9][0-9]*)?(hh|h|l|ll|q|L|j|z|Z|t)?([diouxXeEfFgGaAcsCSpnm%])',
                    format_arg, string)
    print(string + "\n", end="")

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)

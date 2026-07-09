# SPDX-License-Identifier: MIT
import pathlib
import re
import struct
import time
from construct import *

from .macho import MachOLoadCmdType

__all__ = []

DebuggerState = Struct(
    "panic_options"             / Hex(Int64ul),
    "current_op"                / Hex(Int32ul),
    "proceed_on_sync_failure"   / Int32ul,
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

_msgbuf_va_cache = {}
_msgbuf_dump_seq = 0
MAX_MSGBUF_DUMP_SIZE = 8 * 1024 * 1024


def _macho_bytes(macho):
    pos = macho.io.tell()
    try:
        macho.io.seek(macho.off)
        return macho.io.read(macho.size)
    finally:
        macho.io.seek(pos)


def _macho_fileoff_to_va(macho, fileoff):
    for image in [macho] + list(getattr(macho, "subfiles", {}).values()):
        for cmd in image.get_cmds(MachOLoadCmdType.SEGMENT_64):
            start = image.off + cmd.args.fileoff
            end = start + cmd.args.filesize
            if start <= fileoff < end:
                return cmd.args.vmaddr + (fileoff - start)
    return None


def find_msgbuf_va(macho):
    cached = _msgbuf_va_cache.get(id(macho), False)
    if cached is not False:
        return cached

    data = _macho_bytes(macho)
    magic = struct.pack("<I", 0x063061)
    hits = []
    pos = 0
    while True:
        pos = data.find(magic, pos)
        if pos < 0:
            break
        if pos + 24 <= len(data):
            msg_size, msg_bufx, msg_bufr = struct.unpack_from("<iii", data, pos + 4)
            if (0 < msg_size <= 1024 * 1024 and
                    msg_size % 0x1000 == 0 and msg_bufx == 0 and msg_bufr == 0):
                va = _macho_fileoff_to_va(macho, macho.off + pos)
                if va is not None and va not in hits:
                    hits.append(va)
        pos += 1

    if len(hits) != 1:
        print("[host] XNU-MSGBUF: could not derive unique msgbuf VA "
              f"(hits={','.join(hex(h) for h in hits) or 'none'})",
              flush=True)
        _msgbuf_va_cache[id(macho)] = None
        return None

    _msgbuf_va_cache[id(macho)] = hits[0]
    print(f"[host] XNU-MSGBUF: derived msgbuf VA 0x{hits[0]:x}", flush=True)
    return hits[0]


def _read_kernel_va(u, va, size):
    p = u.proxy
    iface = u.iface
    out = bytearray()
    cur = int(va)
    left = int(size)
    while left:
        page_off = cur & 0x3fff
        chunk = min(left, 0x4000 - page_off)
        pa = p.hv_translate(cur, False, False)
        # hv_translate returns the input VA unchanged when the guest MMU is off
        # (SCTLR_EL12.M == 0). A real guest PA is not a kernel VA, so a kernel-VA
        # result means "untranslatable"; bail instead of reading it at EL2
        # (which data-aborts m1n1).
        if not pa or _is_kernel_va(pa):
            return None
        try:
            out += iface.readmem(pa, chunk)
        except Exception:
            return None
        cur += chunk
        left -= chunk
    return bytes(out)


def _is_kernel_va(va):
    return (int(va) >> 56) == 0xff


def _strip_pac(va):
    va = int(va)
    if (va & 0xffffff00_00000000) == 0xfffffe00_00000000:
        return va
    return (va & 0x000000ff_ffffffff) | 0xfffffe00_00000000


def _decode_msgbuf(raw, msg_bufx, msg_bufr):
    size = len(raw)
    if size == 0:
        return b""

    def printable_score(blob):
        if not blob:
            return 0.0
        keep = sum(1 for b in blob if b in (9, 10, 13) or 0x20 <= b < 0x7f)
        return keep / max(1, len(blob))

    ordered = raw[:msg_bufx] if 0 <= msg_bufx <= size else raw
    if 0 <= msg_bufx < size and any(raw[msg_bufx:]):
        ring = raw[msg_bufx:] + raw[:msg_bufx]
        if printable_score(ring.replace(b"\x00", b"")) >= 0.70:
            ordered = ring
    if 0 <= msg_bufr < size and 0 <= msg_bufx < size and msg_bufr != msg_bufx:
        unread = raw[msg_bufr:msg_bufx] if msg_bufr < msg_bufx else raw[msg_bufr:] + raw[:msg_bufx]
        if printable_score(unread.replace(b"\x00", b"")) >= 0.70:
            ordered = unread

    return ordered.replace(b"\x00", b"")


def dump_msgbuf(u, macho, dump_dir="logs", tail_lines=80):
    global _msgbuf_dump_seq

    msgbuf_va = find_msgbuf_va(macho)
    if msgbuf_va is None:
        return None

    hdr = _read_kernel_va(u, msgbuf_va, 24)
    if hdr is None or len(hdr) < 24:
        print(f"[host] XNU-MSGBUF: header read failed at 0x{msgbuf_va:x}",
              flush=True)
        return None

    magic, msg_size, msg_bufx, msg_bufr, msg_bufc = struct.unpack("<iiiiQ", hdr)
    if magic != 0x063061 or msg_size <= 0 or msg_size > MAX_MSGBUF_DUMP_SIZE:
        print(f"[host] XNU-MSGBUF: invalid header magic=0x{magic:x} "
              f"size={msg_size} bufx={msg_bufx} bufr={msg_bufr} "
              f"bufc=0x{msg_bufc:x}", flush=True)
        return None

    if not _is_kernel_va(msg_bufc):
        msg_bufc = _strip_pac(msg_bufc)
    if not _is_kernel_va(msg_bufc):
        print(f"[host] XNU-MSGBUF: non-kernel msg_bufc=0x{msg_bufc:x}",
              flush=True)
        return None

    raw = _read_kernel_va(u, msg_bufc, msg_size)
    if raw is None:
        print(f"[host] XNU-MSGBUF: buffer read failed at 0x{msg_bufc:x} "
              f"size=0x{msg_size:x}", flush=True)
        return None

    text_bytes = _decode_msgbuf(raw, msg_bufx, msg_bufr)
    text = text_bytes.decode("utf-8", errors="replace")
    if text and not text.endswith("\n"):
        text += "\n"

    dump_dir = pathlib.Path(dump_dir)
    dump_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    _msgbuf_dump_seq += 1
    stem = f"xnu_msgbuf_{stamp}_{_msgbuf_dump_seq:02d}"
    raw_path = dump_dir / f"{stem}.raw"
    txt_path = dump_dir / f"{stem}.txt"
    raw_path.write_bytes(raw)
    txt_path.write_text(text, encoding="utf-8", errors="replace")

    print(f"[host] XNU-MSGBUF: dumped {len(text_bytes)} text bytes "
          f"(raw {msg_size} bytes) msgbuf=0x{msgbuf_va:x} "
          f"bufc=0x{msg_bufc:x} bufx={msg_bufx} bufr={msg_bufr} "
          f"path={txt_path}", flush=True)
    tail = [line for line in text.splitlines() if line.strip()]
    if tail and tail_lines:
        print(f"[host] XNU-MSGBUF tail ({min(tail_lines, len(tail))}/{len(tail)} lines):",
              flush=True)
        for line in tail[-tail_lines:]:
            print(f"[xnu-log] {line}", flush=True)
    return txt_path


__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)

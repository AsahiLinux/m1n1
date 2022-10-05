# SPDX-License-Identifier: MIT

import struct
from io import BytesIO
from construct import *
from ..common import *
from ...utils import *
from ..asc import StandardASC
from ..asc.base import *
from .rbep import AFKRingBufEndpoint

EPICType = "EPICType" / Enum(Int32ul,
    NOTIFY = 0,
    COMMAND = 3,
    REPLY = 4,
    NOTIFY_ACK = 8,
)

EPICCategory = "EPICCategory" / Enum(Int8ul,
    REPORT = 0x00,
    NOTIFY = 0x10,
    REPLY = 0x20,
    COMMAND = 0x30,
)

EPICHeader = Struct(
    "channel" / Int32ul,
    "type" / EPICType,
    "version" / Const(2, Int8ul),
    "seq" / Int16ul,
    "pad" / Const(0, Int8ul),
    "unk" / Const(0, Int32ul),
    "timestamp" / Default(Int64ul, 0),
)

EPICSubHeader = Struct(
    "length" / Int32ul,
    "version" / Default(Int8ul, 4),
    "category" / EPICCategory,
    "type" / Hex(Int16ul),
    "timestamp" / Default(Int64ul, 0),
    "seq" / Int16ul,
    "unk" / Default(Hex(Int16ul), 0),
    "inline_len" / Hex(Int32ul),
)

EPICAnnounce = Struct(
    "name" / Padded(32, CString("utf8")),
    "props" / Optional(OSSerialize())
)

EPICSetProp = Struct(
    "name_len" / Int32ul,
    "name" / Aligned(4, CString("utf8")),
    "value" / OSSerialize()
)

EPICCmd = Struct(
    "retcode" / Default(Hex(Int32ul), 0),
    "rxbuf" / Hex(Int64ul),
    "txbuf" / Hex(Int64ul),
    "rxlen" / Hex(Int32ul),
    "txlen" / Hex(Int32ul),
    "rxcookie" / Optional(Default(Bool(Int8ul), False)),
    "txcookie" / Optional(Default(Bool(Int8ul), False)),
)


class EPICError(Exception):
    pass


class EPICService:
    RX_BUFSIZE = 0x4000
    TX_BUFSIZE = 0x4000

    def __init__(self, ep):
        self.iface = ep.asc.iface
        self.ep = ep
        self.ready = False
        self.chan = None
        self.seq = 0
    
    def log(self, msg):
        print(f"[{self.ep.name}.{self.SHORT}] {msg}")
    
    def init(self, props):
        self.log(f"Init: {props}")
        self.props = props
        self.rxbuf, self.rxbuf_dva = self.ep.asc.ioalloc(self.RX_BUFSIZE)
        self.txbuf, self.txbuf_dva = self.ep.asc.ioalloc(self.TX_BUFSIZE)
        self.ready = True
    
    def wait(self):
        while not self.ready:
            self.ep.asc.work()

    def handle_report(self, category, type, seq, fd):
        self.log(f"Report {category}/{type} #{seq}")
        chexdump(fd.read())

    def handle_notify(self, category, type, seq, fd):
        retcode = struct.unpack("<I", fd.read(4))[0]
        self.log(f"Notify {category}/{type} #{seq} ({retcode})")
        data = fd.read()
        chexdump(data)
        print("Send ACK")

        data = data[:0x50] + b"\x01\x00\x00\x00" + data[0x54:]

        pkt = struct.pack("<I", 0) + data
        self.ep.send_epic(self.chan, EPICType.NOTIFY_ACK, EPICCategory.REPLY, type, seq, pkt, len(data))

    def handle_reply(self, category, type, seq, fd):
        off = fd.tell()
        data = fd.read()
        if len(data) == 4:
            retcode = struct.unpack("<I", data)[0]
            if retcode:
                raise EPICError(f"IOP returned errcode {retcode:#x}")
            else:
                self.reply = retcode
                return
        fd.seek(off)
        cmd = EPICCmd.parse_stream(fd)
        payload = fd.read()
        self.log(f"Response {type:#x} #{seq}: {cmd.retcode:#x}")
        if cmd.retcode != 0:
            raise EPICError(f"IOP returned errcode {cmd.retcode:#x}")
        if payload:
            self.log("Inline payload:")
            chexdump(payload)
        assert cmd.rxbuf == self.rxbuf_dva
        self.reply = self.iface.readmem(self.rxbuf, cmd.rxlen)

    def handle_cmd(self, category, type, seq, fd):
        cmd = EPICCmd.parse_stream(fd)
        self.log(f"Command {type:#x} #{seq}: {cmd.retcode:#x}")

    def send_cmd(self, type, data, retlen=None):
        if retlen is None:
            retlen = len(data)
        cmd = Container()
        cmd.rxbuf = self.rxbuf_dva
        cmd.txbuf = self.txbuf_dva
        cmd.txlen = len(data)
        cmd.rxlen = retlen
        self.iface.writemem(self.txbuf, data)
        self.reply = None
        pkt = EPICCmd.build(cmd)
        self.ep.send_epic(self.chan, EPICType.COMMAND, EPICCategory.COMMAND, type, self.seq, pkt)
        self.seq += 1
        while self.reply is None:
            self.ep.asc.work()
        return self.reply

class EPICStandardService(EPICService):
    def call(self, group, cmd, data=b'', replen=None):
        msg = struct.pack("<2xHIII48x", group, cmd, len(data), 0x69706378) + data
        if replen is not None:
            replen += 64
        resp = self.send_cmd(0xc0, msg, replen)
        if not resp:
            return
        rgroup, rcmd, rlen, rmagic = struct.unpack("<2xHIII", resp[:16])
        assert rmagic == 0x69706378
        assert rgroup == group
        assert rcmd == cmd
        return resp[64:64+rlen]

    def getLocation(self, unk=0):
        return struct.unpack("<16xI12x", self.call(4, 4, bytes(32)))

    def getUnit(self, unk=0):
        return struct.unpack("<16xI12x", self.call(4, 5, bytes(32)))

    def open(self, unk=0):
        self.call(4, 6, struct.pack("<16xI12x", unk))

    def close(self):
        self.call(4, 7, bytes(16))

class AFKSystemService(EPICService):
    NAME = "system"
    SHORT = "system"

    def getProperty(self, prop, val):
        pass
        #self.send_cmd(0x40, msg, 0)

    def setProperty(self, prop, val):
        msg = {
            "name_len": (len(prop) + 3) & ~3,
            "name": prop,
            "value": val,
        }
        msg = EPICSetProp.build(msg)
        self.send_cmd(0x43, msg, 0)

class EPICEndpoint(AFKRingBufEndpoint):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.serv_map = {}
        self.chan_map = {}
        self.serv_names = {}
        self.hseq = 0

        for i in self.SERVICES:
            self.serv_names[i.NAME] = i

    def handle_ipc(self, data):
        fd = BytesIO(data)
        hdr = EPICHeader.parse_stream(fd)
        sub = EPICSubHeader.parse_stream(fd)

        if self.verbose > 2:
            self.log(f"Ch {hdr.channel} Type {hdr.type} Ver {hdr.version} Seq {hdr.seq}")
            self.log(f"  Len {sub.length} Ver {sub.version} Cat {sub.category} Type {sub.type:#x} Seq {sub.seq}")

        if sub.category == EPICCategory.REPORT:
            self.handle_report(hdr, sub, fd)
        if sub.category == EPICCategory.NOTIFY:
            self.handle_notify(hdr, sub, fd)
        elif sub.category == EPICCategory.REPLY:
            self.handle_reply(hdr, sub, fd)
        elif sub.category == EPICCategory.COMMAND:
            self.handle_cmd(hdr, sub, fd)

    def wait_for(self, name):
        while True:
            srv = getattr(self, name, None)
            if srv is not None and srv.ready:
                break
            self.asc.work()

    def handle_report(self, hdr, sub, fd):
        if sub.type == 0x30:
            init = EPICAnnounce.parse_stream(fd)
            if init.props is None:
                init.props = {}
            name = init.name
            if "EPICName" in init.props:
                name = init.props["EPICName"]
            key = name + str(init.props.get("EPICUnit", ""))
            if name in self.serv_names:
                srv = self.serv_names[name](self)
                short = srv.SHORT + str(init.props.get("EPICUnit", ""))
                setattr(self, short, srv)
                srv.init(init.props)
                srv.chan = hdr.channel
                self.chan_map[hdr.channel] = srv
                self.serv_map[key] = srv
                self.log(f"New service: {key} on channel {hdr.channel} (short name: {short})")
            else:
                self.log(f"Unknown service {key} on channel {hdr.channel}")
        else:
            if hdr.channel not in self.chan_map:
                self.log(f"Ignoring report on channel {hdr.channel}")
            else:
                self.chan_map[hdr.channel].handle_report(sub.category, sub.type, sub.seq, fd)

    def handle_notify(self, hdr, sub, fd):
        self.chan_map[hdr.channel].handle_notify(sub.category, sub.type, sub.seq, fd)

    def handle_reply(self, hdr, sub, fd):
        self.chan_map[hdr.channel].handle_reply(sub.category, sub.type, sub.seq, fd)

    def handle_cmd(self, hdr, sub, fd):
        self.chan_map[hdr.channel].handle_cmd(sub.category, sub.type, sub.seq, fd)
    
    def send_epic(self, chan, ptype, category, type, seq, data, inline_len=0):
        hdr = Container()
        hdr.channel = chan
        hdr.type = ptype
        hdr.seq = self.hseq
        self.hseq += 1

        sub = Container()
        sub.length = len(data)
        sub.category = category
        sub.type = type
        sub.seq = seq
        sub.inline_len = inline_len
        pkt = EPICHeader.build(hdr) + EPICSubHeader.build(sub) + data
        super().send_ipc(pkt)

class AFKSystemEndpoint(EPICEndpoint):
    SHORT = "system"

    SERVICES = [
        AFKSystemService,
    ]

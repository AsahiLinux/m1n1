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
    "unk2" / Default(Hex(Int32ul), 0),
)

EPICAnnounce = Struct(
    "name" / Padded(32, CString("utf8")),
    "props" / Optional(OSSerialize())
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
        self.txbuf, self.txbuf_dva = self.ep.asc.ioalloc(self.RX_BUFSIZE)
        self.ready = True
    
    def wait(self):
        while not self.ready:
            self.ep.asc.work()

    def handle_report(self, category, type, seq, fd):
        self.log(f"Report {category:#x}/{type:#x} #{seq}")
        chexdump(fd.read())

    def handle_notify(self, category, type, seq, fd):
        self.log(f"Notify {category:#x}/{type:#x} #{seq}")
        chexdump(fd.read())

    def handle_reply(self, category, type, seq, fd):
        off = fd.tell()
        if len(fd.read()) == 4:
            retcode = struct.unpack("<I", data)[0]
            raise EPICError(f"IOP returned errcode {retcode:#x}")
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

class EPICEndpoint(AFKRingBufEndpoint):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.serv_map = {}
        self.chan_map = {}

        for i in self.SERVICES:
            srv = i(self)
            setattr(self, srv.SHORT, srv)
            self.serv_map[srv.NAME] = srv

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

    def handle_report(self, hdr, sub, fd):
        if sub.type == 0x30:
            init = EPICAnnounce.parse_stream(fd)
            if init.name in self.serv_map:
                self.serv_map[init.name].init(init.props)
                self.serv_map[init.name].chan = hdr.channel
                self.chan_map[hdr.channel] = self.serv_map[init.name]
            else:
                self.log("Unknown service {init.name}")
        else:
            self.chan_map[hdr.channel].handle_report(sub.category, sub.type, fd)

    def handle_notify(self, hdr, sub, fd):
        self.chan_map[hdr.channel].handle_notify(sub.category, sub.type, sub.seq, fd)

    def handle_reply(self, hdr, sub, fd):
        self.chan_map[hdr.channel].handle_reply(sub.category, sub.type, sub.seq, fd)

    def handle_cmd(self, hdr, sub, fd):
        self.chan_map[hdr.channel].handle_cmd(sub.category, sub.type, sub.seq, fd)
    
    def send_epic(self, chan, ptype, category, type, seq, data):
        hdr = Container()
        hdr.channel = chan
        hdr.type = ptype
        hdr.seq = 0
        sub = Container()
        sub.length = len(data)
        sub.category = category
        sub.type = type
        sub.seq = seq
        pkt = EPICHeader.build(hdr) + EPICSubHeader.build(sub) + data
        super().send_ipc(pkt)

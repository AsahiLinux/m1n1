# SPDX-License-Identifier: MIT
from ..common import *
from ...utils import align
import construct
import struct

ISPIPCBootArgs = Struct(
    "pad" / Default(Int64ul, 0),
    "ipc_iova" / Hex(Int64ul),  # 0x1804000

    "unk0" / Hex(Int64ul),  # 0x1800000
    "unk1" / Hex(Int64ul),  # 0xe800000

    "extra_iova" / Hex(Int64ul),  # 0x1824000
    "extra_size" / Hex(Int64ul),  # 0x2200000

    "unk4" / Hex(Int32ul),  # 0x1
    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),

    "pad" / Padding(0x10),

    "ipc_size" / Hex(Int32ul),  # 0x1c000
    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),

    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),
    "unk5" / Hex(Int32ul),  # 0x40
    "pad" / Default(Int32ul, 0),

    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),
    "unk6" / Hex(Int32ul),  # 0x0 or 0x4b4c000
    "pad" / Default(Int32ul, 0),

    "pad" / Padding(0x20),

    "pad" / Default(Int32ul, 0),
    "unk7" / Hex(Int32ul),  # 0x1
    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),

    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),
    "unk_iova" / Hex(Int32ul),  # 0x18130f4

    "pad" / Padding(0xb0),

    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),
    "unk9" / Hex(Int32ul),  # 0x3
)
assert((ISPIPCBootArgs.sizeof() == 0x180))

ISPIPCChanTableDescEntry = Struct(
    "name" / PaddedString(0x40, "utf8"),
    "type" / Int32ul,
    "src" / Int32ul,
    "num" / Int32ul,
    "pad" / Int32ul,
    "iova" / Hex(Int32ul),
    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),
    "pad" / Default(Int32ul, 0),
    "pad" / Padding(0xa0),
)
assert((ISPIPCChanTableDescEntry.sizeof() == 0x100))

class ISPChannelMessage:
    def __init__(self, arg0=0x0, arg1=0x0, arg2=0x0, arg3=0x0, arg4=0x0, arg5=0x0, arg6=0x0, arg7=0x0):
        self.count = 8
        self.arg0 = arg0; self.arg1 = arg1; self.arg2 = arg2; self.arg3 = arg3; self.arg4 = arg4; self.arg5 = arg5; self.arg6 = arg6; self.arg7 = arg7
        self.args = [self.arg0, self.arg1, self.arg2, self.arg3, self.arg4, self.arg5, self.arg6, self.arg7]
        self.data = None

    @classmethod
    def build(cls, arg0=0x0, arg1=0x0, arg2=0x0, arg3=0x0, arg4=0x0, arg5=0x0, arg6=0x0, arg7=0x0):
            return cls(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7)

    @classmethod
    def new(cls): return cls.build()

    @classmethod
    def parse(cls, buf, index=0):
        arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7 = struct.unpack("<8q", buf)
        out = cls(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7)
        out.data = buf
        out.index = index
        return out

    def encode(self):
            return struct.pack("<8q", *(self.arg0, self.arg1, self.arg2, self.arg3, self.arg4, self.arg5, self.arg6, self.arg7))

    def __str__(self, max_count=3):
        s = "ISP Message ["
        for n in range(max_count):
            s += "0x%x" % (getattr(self, f"arg{n}"))
            if (n < max_count-1):
                        s += ", "
        s += "]"
        return s

    def valid(self):  # rough check used for dumps
        return (self.arg0 != 0x1) and (self.arg0 != 0x3) and (not (all(arg == 0x0 for arg in self.args)))

class ISPChannel:
    """
    Ring buffers used for CPU <-> ASC communication.

    TM: TERMINAL     | src = 0, type = 2, num = 768, size = 0xc000, iova = 0x1804700
    IO: IO           | src = 1, type = 0, num =   8, size = 0x0200, iova = 0x1810700
    DG: DEBUG        | src = 1, type = 0, num =   8, size = 0x0200, iova = 0x1810900
    BR: BUF_H2T      | src = 2, type = 0, num =  64, size = 0x1000, iova = 0x1810b00
    BT: BUF_T2H      | src = 3, type = 1, num =  64, size = 0x1000, iova = 0x1811b00
    SM: SHAREDMALLOC | src = 3, type = 1, num =   8, size = 0x0200, iova = 0x1812b00
    IT: IO_T2H       | src = 3, type = 1, num =   8, size = 0x0200, iova = 0x1812d00

    There's a sticky note on my machine that says, "Host is Me, Target is Firmware".

    TM: Logs from firmware. arg0 is pointer & arg1 is the message size of log line.
    IO: To dispatch CISP_CMD_* ioctls to the firmware.
    DG: Unused.
    BR: New RX buffer pushed.
    BT: New TX buffer pushed.
    SM: Firmware requests to allocate OR free a shared mem region.
    IT: Mcache stuff when RPC is enabled. Basically unused.
    """

    def __init__(self, isp, name, _type, src, num, iova, abbrev=""):
        self.isp = isp
        self.name = name
        self.src = src
        self.type = _type
        self.num = num
        self.entry_size = 64
        self.size = self.num * self.entry_size
        self.iova = iova
        self.doorbell = 1 << self.src

        self.cursor = 0
        self.abbrev = abbrev if abbrev else self.name
        self._stfu = False

    @property
    def stfu(self): self._stfu = True

    def log(self, *args):
        if (not self._stfu):
            if (args): print("ISP: %s:" % (self.abbrev.upper()), *args)
            else: print()

    def get_iova(self, index):
            assert((index < self.num))
            return self.iova + (index * self.entry_size)

    def read_msg(self, index):
            assert((index < self.num))
            return ISPChannelMessage.parse(self.isp.ioread(self.get_iova(index), self.entry_size))

    def write_msg(self, msg, index):
            assert((index < self.num))
            self.isp.iowrite(self.get_iova(index), msg.encode())

    def read_all_msgs(self):
        ring = self.isp.ioread(self.iova, self.size)
        return [ISPChannelMessage.parse(ring[n*self.entry_size:(n+1)*self.entry_size]) for n in range(self.num)]

    def update_cursor(self):
        if (self.cursor >= (self.num - 1)):
            self.cursor = 0
        else:
            self.cursor += 1

    def dump(self):
        self.log(f'---------------- START OF {self.name} TABLE ----------------')
        for n, msg in enumerate(self.read_all_msgs()):
            if (msg.valid()):
                self.log(f'{n}: {msg}')
        self.log(f'---------------- END OF {self.name} TABLE ----------------')

    def _irq_wrap(f):
        def wrap(self, **kwargs):
            self.log()
            self.log(f'---------------- START OF {self.name} IRQ ----------------')
            x = f(self, **kwargs)
            self.log(f'---------------- END OF {self.name} IRQ ------------------')
            self.log()
            return x
        return wrap

    @_irq_wrap
    def handle_once(self, req):
        rsp = self._handle(req=req)
        if (rsp == None): return None
        self.write_msg(rsp, self.cursor)
        self.isp.regs.ISP_IRQ_DOORBELL.val = self.doorbell
        self.update_cursor()
        return rsp

    def handler(self):
        while True:
            req = self.read_msg(self.cursor)
            if ((req.arg0 & 0xf) == 0x1): break  # ack flag
            rsp = self.handle_once(req=req)
            if (rsp == None): raise RuntimeError("IRQ stuck")

    @_irq_wrap
    def send_once(self, req):
        self.log(f'TX: REQ: {req}')
        self.write_msg(req, self.cursor)

        rsp = None
        self.isp.regs.ISP_IRQ_DOORBELL.val = self.doorbell
        while True:
            rsp = self.read_msg(self.cursor)
            if (rsp.arg0 == (req.arg0 | 0x1)): break  # ack flag
            self.isp.table.sharedmalloc.handler()
        if (rsp == None): return None

        self.log(f'RX: RSP: {rsp}')
        self.isp.regs.ISP_IRQ_ACK.val = self.isp.regs.ISP_IRQ_INTERRUPT.val
        self.update_cursor()
        return rsp

    def send(self, req):
        rsp = self.send_once(req=req)
        if (rsp == None): raise RuntimeError("ASC never acked. IRQ stuck.")
        return rsp

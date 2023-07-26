# SPDX-License-Identifier: MIT
from . import ADTDevTracer
from .dart import DARTTracer
from ..hv import TraceMode
from ..utils import *

from ..hw.isp import *
from ..fw.isp import *
from ..fw.isp.isp_opcodes import *

class ISPCommandDirection(IntEnum):
    RX = 0
    TX = 1

def opcode2name(opcode):
    if opcode_dict and (opcode in opcode_dict): return opcode_dict[opcode]
    return "CISP_CMD_UNK_%04x" % (opcode)

class ISPCommand:
    def __init__(self, chan, msg, direction):
        self.arg0, self.arg1, self.arg2, self.arg3, self.arg4, self.arg5, self.arg6, self.arg7 = struct.unpack("<8q", msg.data)
        self.iova = self.arg0 & ~3
        self.msg = msg
        self.chan = chan
        self.direction = direction
        self.tracer = chan.tracer

    def dump(self):
        self.log(f"[CMD arg0: {hex(self.arg0)}, arg1: {hex(self.arg1)}, arg2: {hex(self.arg2)}]")

    def read_iova(self, iova, size):
        return self.tracer.dart.ioread(0, iova, size)

    def log(self, msg):
        if self.direction == ISPCommandDirection.RX:
            self.tracer.log(f"<== [{self.chan.name}]({self.msg.index}): {msg}")
        else:
            self.tracer.log(f"==> [{self.chan.name}]({self.msg.index}): {msg}")

class ISPTerminalCommand(ISPCommand):
    # Broken as of 13.5.2
    def __init__(self, chan, msg, direction):
        super().__init__(chan, msg, direction)

    def dump(self):
        super().dump()

class ISPIOCommand(ISPCommand):
    def __init__(self, chan, msg, direction):
        super().__init__(chan, msg, direction)
        self.contents = self.read_iova(self.iova, self.arg1)

    def dump(self):
        if self.iova:
            opcode = struct.unpack("<Q", self.contents[:0x8])[0] >> 32
            self.log(f"[IO iova: {hex(self.iova)}, insize: {hex(self.arg1)}, outsize: {hex(self.arg2)} -> opcode: {hex(opcode)} {opcode2name(opcode)}]")
            self.log("IO struct: ")
            try:
                chexdump32(self.contents)
            except struct.error:
                print(chexdump(self.contents))

class ISPT2HBufferCommand(ISPCommand):
    def __init__(self, chan, msg, direction):
        super().__init__(chan, msg, direction)
        #self.contents = self.read_iova(0x1013140, 0x4000)
        self.contents = None

    def dump(self):
        super().dump()
        if self.contents:
            self.log("BUF_T2H struct:")
            chexdump32(self.contents)

class ISPH2TBufferCommand(ISPCommand):
    def __init__(self, chan, msg, direction):
        super().__init__(chan, msg, direction)
        #self.contents = self.read_iova(0x1013140, 0x4000)
        self.contents = None

    def dump(self):
        super().dump()
        if self.contents:
            self.log("BUF_H2T struct:")
            chexdump32(self.contents)

class ISPT2HIOCommand(ISPCommand):
    def __init__(self, chan, msg, direction):
        super().__init__(chan, msg, direction)

    def dump(self):
        super().dump()

class ISPSharedMallocCommand(ISPCommand):
    def __init__(self, chan, msg, direction):
        super().__init__(chan, msg, direction)

    def dump(self):
        if not self.arg0:
            try:
                name = struct.pack(">Q", self.arg2).decode()
            except UnicodeDecodeError:
                name = "UNICODE-GARBAGE-%08x" % (self.arg2)
            self.log("[Malloc REQ: size: 0x%x, name: %s]" % (self.arg1, name))
        else:
            self.log("[Free REQ: iova: 0x%x, index: 0x%x]" % (self.arg0, self.arg2))

class ISPChannelTable:
    def __init__(self, tracer, num_chans, table_iova):
        self.tracer = tracer
        self.table_iova = table_iova
        self.num_chans = num_chans
        self.desc_size = ISPIPCChanTableDescEntry.sizeof()

        chans = []
        table_data = self.tracer.ioread(table_iova, num_chans*self.desc_size)
        for n in range(num_chans):
            entry = table_data[n*self.desc_size:(n+1)*self.desc_size]
            x = ISPIPCChanTableDescEntry.parse(entry)
            chan = ISPTracerChannel(self.tracer, x.name, x.type, x.src, x.num, x.iova)
            chans.append(chan)
        self.chans = chans

    def get_last_rx_commands(self, val):
        for chan in self.chans:
            if (chan.type == 1):
                chan.get_last_commands(ISPCommandDirection.RX)

    def get_last_tx_commands(self, doorbell):
        for chan in self.chans:
            if (chan.doorbell == doorbell):
                chan.get_last_commands(ISPCommandDirection.TX)

class ISPTracerChannel(ISPChannel):
    def __init__(self, isp, name, _type, src, num, iova):
        super().__init__(isp, name, _type, src, num, iova) # init as 'tracer'
        self.tracer = isp

    def __convert2command__(self, msg, direction):
        if self.name == "TERMINAL":
            return ISPTerminalCommand(self, msg, direction)
        elif self.name == "IO" or self.name == "DEBUG":
            return ISPIOCommand(self, msg, direction)
        elif self.name == "SHAREDMALLOC":
            return ISPSharedMallocCommand(self, msg, direction)
        elif self.name == "BUF_T2H":
            return ISPT2HBufferCommand(self, msg, direction)
        elif self.name == "BUF_H2T":
            return ISPH2TBufferCommand(self, msg, direction)
        elif self.name == "IO_T2H":
            return ISPT2HIOCommand(self, msg, direction)
        else:
            return ISPCommand(self, msg, direction)

    def get_last_commands(self, direction):
        cmds = []  # collect asap
        for n in range(self.num):
            pos = (self.cursor + n) % self.num
            dat = self.tracer.ioread(self.iova + (self.entry_size * pos), self.entry_size)
            msg = ISPChannelMessage.parse(dat, index=pos)
            if (not msg.valid()):
                self.cursor = pos
                break
            else:
                cmd = self.__convert2command__(msg, direction)
                cmds.append(cmd)
        for cmd in cmds:
            cmd.dump()

    def __str__(self):
        return f"[{str(self.name)}: src={self.src!s} type={self.type!s} num={self.num!s} iova={hex(self.iova)!s})"

class ISPTracer(ADTDevTracer):

    DEFAULT_MODE = TraceMode.SYNC
    REGMAPS = [ISPRegs]
    NAMES = ["isp"]

    def __init__(self, hv, dev_path, dart_dev_path, verbose):
        super().__init__(hv, dev_path, verbose)
        hv.p.pmgr_adt_clocks_enable(dart_dev_path)
        self.dart_tracer = DARTTracer(hv, dart_dev_path, verbose=0)
        self.dart_tracer.start()
        self.dart = self.dart_tracer.dart

        self.ignored_ranges = [
            (0x22c0e8000, 0x4000), # dart 1
            (0x22c0f4000, 0x4000), # dart 2
            (0x22c0fc000, 0x4000), # dart 3
        ]

        self.table = None
        self.num_chans = 0

    def r_ISP_GPIO_0(self, val):
        self.log("ISP_GPIO_0 r32: 0x%x" % (val.value))
        if val.value == 0x8042006:
            self.log(f"ISP_GPIO0 = ACK")
        elif val.value < 64: 
            self.log(f"ISP_IPC_CHANNELS = {val!s}")
            self.num_chans = val.value
        elif val.value > 0:
            self.log(f"IPC BASE IOVA: {val!s}")
            self.ipc_iova = val.value
            self.table = ISPChannelTable(self, self.num_chans, val.value)
            self.log("======== CHANNEL TABLE ========")
            for chan in self.table.chans:
                self.log(f"ISPIPC: {str(chan)}")
            self.log("======== END OF CHANNEL TABLE ========")

    def r_ISP_IRQ_INTERRUPT(self, val):
        #self.log("ISP_IRQ_INTERRUPT r32: 0x%x" % (val.value))
        #self.log(f"======== BEGIN IRQ ========")
        self.table.get_last_rx_commands(int(val.value))
        #self.log(f"========  END IRQ  ========")

    def w_ISP_IRQ_DOORBELL(self, val):
        #self.log("ISP_IRQ_DOORBELL w32: 0x%x" % (val.value))
        #self.log(f"======== BEGIN DOORBELL ========")
        self.table.get_last_tx_commands(int(val.value))
        #self.log(f"========  END DOORBELL  ========")

    def w_ISP_GPIO_0(self, val):
        self.log("ISP_GPIO_0 w32: 0x%x" % (val.value))
        if (val.value >= 0xe00000) and (val.value <= 0x1100000): # dunno
            self.log("ISP bootargs at 0x%x:" % val.value)
            bootargs = self.dart.ioread(0, val.value, 0x200) # justt in case
            chexdump32(bootargs)
            x = ISPIPCBootArgs.parse(bootargs[:ISPIPCBootArgs.sizeof()])
            self.log(x)

    def ioread(self, iova, size):
        return self.dart.ioread(0, iova, size)

    def iowrite(self, iova, data):
        return self.dart.iowrite(0, iova, data)

    def start(self):
        super().start()
        for addr, size in self.ignored_ranges:
            self.trace(addr, size, TraceMode.OFF)

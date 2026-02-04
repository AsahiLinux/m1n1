# SPDX-License-Identifier: MIT

from ..utils import *
from . import ADTDevTracer
from ..hw.spmi import SPMIRegs
from ..hv import TraceMode

# see docs/hw/soc/spmi.md and docs/hw/peripherals/ace3.md

spmi_cmds = {
    0x10: 'RESET',
    0x11: 'SLEEP',
    0x12: 'SHUTDOWN',
    0x13: 'WAKEUP',
    0x1C: 'SLAVE_DESC',

    0x00: 'EXT_WRITE',
    0x20: 'EXT_READ',
    0x30: 'EXT_WRITEL',
    0x38: 'EXT_READL',
    0x40: 'WRITE',
    0x60: 'READ',
    0x80: 'ZERO_WRITE'
}

class SPMIState:
    def __init__(self):
        self.data = b""
        self.opcode = None
        self.summary = ""
        self.register = None # only valid for READ/WRITE/ZERO_WRITE
        self.notes = ""
        self.device_id = 0

class SPMITracer(ADTDevTracer):
    DEFAULT_MODE = TraceMode.ASYNC
    REGMAPS = [SPMIRegs]
    NAMES = ["spmi"]

    # I2CTracer-ish interface
    def __init__(self, hv, devpath, verbose=False):
        super().__init__(hv, devpath, verbose=verbose)
        self.default_dev = SPMIDevTracer(None)
        self.default_dev.spmi_tracer = self

    def init_state(self):
        # number of CMD payload bytes we're waiting for
        self.state.cmd_pending = 0
        # list of number of bytes we're expecting for each pending reply
        self.state.reply_pending = []
        # did we already see the first part of a reply, and just waiting for the payload?
        self.state.reply_started = False

        self.state.cmd_info = SPMIState()
        self.state.reply_info = SPMIState()

        self.state.sent_cmds = []
        self.state.devices = {}

    def device_name(self, device_id):
        if device_id in self.state.devices and self.state.devices[device_id].name:
            return self.state.devices[device_id].name + f" (0x{device_id:x})"
        return f"0x{device_id:x}"

    def opcode_name(self, opcode):
        # ext_write, ext_read
        if (opcode & 0xf0) in [0x0, 0x20]:
            return spmi_cmds[opcode & 0xf0]
        # write, read
        if (opcode & 0xe0) in [0x40, 0x60]:
            return spmi_cmds[opcode & 0xe0]
        # zero_write
        if (opcode & 0x80) in [0x80]:
            return spmi_cmds[opcode & 0x80]
        # writel, readl
        if (opcode & 0xf8) in [0x30, 0x38]:
            return spmi_cmds[opcode & 0xf8]
        if opcode in spmi_cmds:
            return spmi_cmds[opcode]
        return f"0x{opcode:x}?"

    def w_CMD(self, val):
        if self.state.cmd_pending:
            # payload for a previous command
            value = val.value
            for n in range(4):
                if self.state.cmd_pending:
                    self.state.cmd_pending -= 1
                    self.state.cmd_info.data += bytes((value & 0xff,))
                    value = value >> 8
            if self.verbose >= 2:
                self.log(f"CMD payload {val.value:08x}")
            if self.state.cmd_pending == 0:
                self.finalize_cmd()
            return

        # new command
        opcode = self.opcode_name(val.OPCODE)
        device = self.device_name(val.SLAVE_ID)

        notes = ""
        self.state.cmd_info.register = None
        self.state.cmd_info.opcode = opcode
        self.state.cmd_info.data = b""

        if opcode == 'EXT_WRITE':
            self.state.cmd_pending = (val.OPCODE & 0xf) + 1
            self.state.reply_pending.append(0)
            self.state.cmd_info.register = val.EXTRA
        elif opcode == 'EXT_READ':
            self.state.reply_pending.append((val.OPCODE & 0xf) + 1)
            self.state.cmd_info.register = val.EXTRA
        elif opcode == 'EXT_WRITEL':
            self.state.cmd_pending = (val.OPCODE & 0x7) + 1
            self.state.reply_pending.append(0)
            self.state.cmd_info.register = val.EXTRA
        elif opcode == 'EXT_READL':
            self.state.reply_pending.append((val.OPCODE & 0x7) + 1)
            self.state.cmd_info.register = val.EXTRA
        elif opcode == 'WRITE':
            self.state.cmd_pending = 1
            self.state.reply_pending.append(0)
            self.state.cmd_info.register = val.EXTRA & 0xff
            self.state.cmd_info.data = bytes((val.EXTRA >> 8,))
        elif opcode == 'READ':
            self.state.reply_pending.append(1)
            self.state.cmd_info.register = val.EXTRA
        elif opcode == 'ZERO_WRITE':
            self.state.reply_pending.append(0)
            self.state.cmd_info.data = bytes((val.EXTRA >> 8,))
            self.state.cmd_info.register = val.EXTRA & 0xf
        else:
            self.state.reply_pending.append(0)
            if val.EXTRA:
                notes = notes + f" (extra 0x{val.EXTRA})"

        if opcode in ['WRITE', 'READ', 'ZERO_WRITE']:
            # we don't expect to see the value in the opcode in the CMD
            mask = 0x1f
            if opcode == 'ZERO_WRITE':
                mask = 0x7f
            if val.OPCODE & mask:
                notes = notes + f" (didn't expect 0x{val.OPCODE & mask:x} in opcode)"
        if self.state.cmd_info.register != None:
            notes = notes + f" (reg 0x{self.state.cmd_info.register:x})"
        if not val.ALERT:
            notes = notes + " (queueing)"

        self.state.cmd_info.notes = notes
        self.state.cmd_info.summary = f"{opcode} -> {device}"
        self.state.cmd_info.device_id = val.SLAVE_ID

        if self.verbose >= 2:
            self.log(f"CMD {opcode} -> {device}{notes} ({val})")
        if self.state.cmd_pending == 0:
            self.finalize_cmd()

    def r_REPLY(self, val):
        notes = ""
        if not len(self.state.reply_pending):
            notes = " (unexpected!)"
            self.state.reply_pending = [0]

        if self.state.reply_started:
            # This is a payload.
            value = val.value
            for n in range(4):
                if self.state.reply_pending[0]:
                    self.state.reply_pending[0] -= 1
                    self.state.reply_info.data += bytes((value & 0xff,))
                    value = value >> 8
            if self.verbose >= 2:
                self.log(f"REPLY payload {val.value:08x}")
            if self.state.reply_pending[0] == 0:
                self.finalize_reply()
                self.state.reply_pending = self.state.reply_pending[1:]
                self.state.reply_started = False
            return

        # this is a new reply
        opcode = self.opcode_name(val.OPCODE)
        device = self.device_name(val.SLAVE_ID)

        # check the length matches what we expect
        if val.FRAME_PARITY != (1 << self.state.reply_pending[0]) - 1:
            notes = notes + " (length mismatch)"
        if self.state.reply_pending[0] == 0:
            # Zero-length reply.
            self.state.reply_pending = self.state.reply_pending[1:]
            if val.ACK == 0:
                notes = notes + " (missing ACK)"
        else:
            # We're expecting a payload.
            self.state.reply_started = True

        # reply should be consistent with the cmd
        cmd = self.state.sent_cmds[0]
        if cmd.opcode != opcode:
            notes = notes + " *** opcodes mismatch ***"
        if opcode in ['WRITE', 'READ']:
            reg = val.OPCODE & 0x1f
            if reg != cmd.register:
                notes = notes + f" *** register 0x{reg:x} doesn't match CMD ***"
        if opcode == 'ZERO_WRITE':
            data = val.OPCODE & 0x7f
            if data != cmd.data[0]:
                notes = notes + f" *** data 0x{data:x} doesn't match CMD ***"

        self.state.reply_info.summary = f"{opcode} <- {device}"
        self.state.reply_info.data = b""
        self.state.reply_info.notes = notes
        self.state.reply_info.device_id = val.SLAVE_ID

        if self.verbose >= 2:
            self.log(f"REPLY {opcode} <- {device}{notes} ({val})")
        if not self.state.reply_started:
            self.finalize_reply()

    def finalize_cmd(self):
        self.state.sent_cmds.append(self.state.cmd_info)

        if self.verbose >= 1:
            data = ""
            if len(self.state.cmd_info.data):
                data = f": {self.state.cmd_info.data.hex()}"
            self.log(f"CMD: {self.state.cmd_info.summary}{self.state.cmd_info.notes}{data}")

        self.state.cmd_info = SPMIState()

    def finalize_reply(self):
        reply_info = self.state.reply_info
        cmd_info = self.state.sent_cmds[0]

        if self.verbose >= 1:
            data = ""
            if len(reply_info.data):
                data = f": {reply_info.data.hex()}"
            self.log(f"REPLY: {reply_info.summary}{reply_info.notes}{data}")

        if reply_info.device_id in self.state.devices:
            device = self.state.devices[reply_info.device_id]
            device.traffic(cmd_info, reply_info)
            if not len(self.state.reply_pending):
                device.flush()

        self.state.sent_cmds = self.state.sent_cmds[1:]

    def add_device(self, addr, device):
        device.hv = self.hv
        device.spmi_tracer = self
        self.state.devices[addr] = device

class SPMIDevTracer(Reloadable):
    def __init__(self, addr, name=None, verbose=True):
        self.addr = addr
        self.name = name
        self.verbose = verbose
        self.spmi_tracer = None

    # CMD/REPLY pair is finished
    def traffic(self, cmd, reply):
        pass
    def flush(self):
        pass

    def log(self, msg, *args, **kwargs):
        if self.name:
            msg = f"[{self.name}] {msg}"
        self.spmi_tracer.log(msg, *args, **kwargs)

tps6598x_regs = {
    0x0f: 'VERSION?',
    0x08: 'CMD1',
    0x09: 'DATA1',
    0x14: 'INT_EVENT1',
    0x16: 'INT_MASK1',
    0x18: 'INT_CLEAR1',
    0x1a: 'STATUS',
    0x20: 'POWER_STATE',
    0x3f: 'POWER_STATUS',
    0x5f: 'DATA_STATUS'
}

class ACE3SPMIDevTracer(SPMIDevTracer):
    def __init__(self, addr, name=None, verbose=True):
        super().__init__(addr, name, verbose)
        self.reg = None
        self.state = 'idle'
        self.last_opcode = None
        self.data = b""

    def flush(self):
        if self.last_opcode:
            reg = f"0x{self.reg:02x}"
            if self.reg in tps6598x_regs:
                reg = reg + f" ({tps6598x_regs[self.reg]})"

            data = self.data.hex()
            if self.reg == 0x08:
                if self.data == b"\x00\x00\x00\x00":
                    data = data + " (idle)"
                else:
                    data = data + f" ({self.data.decode()})"

            self.log(f"{reg} {self.last_opcode}: {data}")
            self.data = b""
            self.state = 'idle'
            self.last_opcode = None

    def traffic(self, cmd, reply):
        if cmd.opcode in ['SLEEP', 'WAKEUP']:
            self.flush()
            self.log(cmd.opcode)
            self.state = 'idle'
            self.reg = None
            return

        # very incomplete 'state machine'
        if cmd.opcode == 'ZERO_WRITE' and cmd.register == 0x0:
            if self.state not in ['idle', 'getlen', 'ready']:
                self.log(f"desynced? {cmd.opcode} in state {self.state}")
            self.flush()
            self.reg = cmd.data[0]
            self.state = 'start'
        elif cmd.opcode == 'READ' and cmd.register == 0x0:
            if self.reg == None:
                self.log(f"{cmd.opcode} in state {self.state} without ZERO_WRITE first")
                self.reg = reply.data[0] & 0x7f
            if self.reg != reply.data[0]:
                if (self.reg | 0x80) == reply.data[0]:
                    # waiting
                    self.state = 'start'
                    return
            if self.state != 'start' or self.reg != reply.data[0]:
                self.log(f"desynced? {cmd.opcode} 0x{self.reg:x} in state {self.state}; reply had 0x{reply.data[0]:x}")
            self.flush()
            self.state = 'getlen'
        elif cmd.opcode == 'READ' and cmd.register == 0x1f:
            if self.state != 'getlen':
                self.log(f"desynced? {cmd.opcode} in state {self.state}")
            self.flush()
            self.state = 'ready'
            # note that we don't track length because we often get overreads
        elif cmd.opcode == 'EXT_WRITE' or cmd.opcode == 'EXT_READ':
            if not self.last_opcode:
                self.last_opcode = cmd.opcode
            if self.state == 'getlen':
                self.state = 'ready'
            if self.state != 'ready' or self.last_opcode != cmd.opcode:
                self.log(f"desynced? {cmd.opcode} in state {self.state}, expected {self.last_opcode}")
                self.state = 'ready'

            # check all reads/writes are linear
            if cmd.opcode == 'EXT_WRITE':
                data = cmd.data
                expected_offset = 0xa0
            else:
                data = reply.data
                expected_offset = 0x20
            expected_offset = expected_offset + len(self.data)
            if cmd.register != expected_offset:
                self.log(f"{cmd.opcode} at offset 0x{cmd.register} but expected 0x{expected_offset}")

            self.data += data
        else:
            self.flush()
            if cmd.opcode == 'READ':
                self.log(f"unexpected {cmd.opcode} from 0x{cmd.register:02x}: {reply.data.hex()}")
            elif cmd.opcode == 'WRITE':
                self.log(f"unexpected {cmd.opcode} to 0x{cmd.register:02x}: {cmd.data.hex()}")
            else:
                self.log(f"unexpected opcode {cmd.opcode}")


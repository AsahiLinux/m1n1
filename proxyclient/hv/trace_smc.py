# SPDX-License-Identifier: MIT

import struct

from enum import IntEnum

from m1n1.proxyutils import RegMonitor
from m1n1.utils import *
from m1n1.trace.dart import DARTTracer
from m1n1.trace.asc import ASCTracer, EP, EPState, msg, msg_log, DIR
from m1n1.fw.smc import *

ASCTracer = ASCTracer._reloadcls()

class SMCEpTracer(EP):
    BASE_MESSAGE = SMCMessage

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)
        self.state.sram_addr = None
        self.state.verbose = 1
        self.state.rb = {}

    Initialize = msg_log(SMC_INITIALIZE, DIR.TX, SMCInitialize)
    Notification = msg_log(SMC_NOTIFICATION, DIR.RX)

    @msg(SMC_WRITE_KEY, DIR.TX, SMCWriteKey)
    def WriteKey(self, msg):
        key = msg.KEY.to_bytes(4, byteorder="big").decode("ascii")
        self.state.rb[msg.ID] = msg.TYPE, key, msg.SIZE
        data = self.hv.iface.readmem(self.state.sram_addr, msg.SIZE)
        self.log(f"[{msg.ID:x}] >W: <{key}> = {data.hex()} ({msg.SIZE})")
        return True

    @msg(SMC_READ_KEY, DIR.TX, SMCReadKey)
    def ReadKey(self, msg):
        key = msg.KEY.to_bytes(4, byteorder="big").decode("ascii")
        self.state.rb[msg.ID] = msg.TYPE, key, msg.SIZE
        self.log(f"[{msg.ID:x}] >R: <{key}> = ... ({msg.SIZE})")
        return True

    @msg(SMC_RW_KEY, DIR.TX, SMCReadWriteKey)
    def ReadKeyPayload(self, msg):
        key = msg.KEY.to_bytes(4, byteorder="big").decode("ascii")
        self.state.rb[msg.ID] = msg.TYPE, key, msg.RSIZE
        data = self.hv.iface.readmem(self.state.sram_addr, msg.WSIZE)
        self.log(f"[{msg.ID:x}] >RP: <{key}> = {data.hex()} ({msg.WSIZE, msg.RSIZE})")
        return True

    @msg(SMC_GET_KEY_INFO, DIR.TX, SMCGetKeyInfo)
    def GetInfo(self, msg):
        key = msg.KEY.to_bytes(4, byteorder="big").decode("ascii")
        self.state.rb[msg.ID] = msg.TYPE, key, None
        self.log(f"[{msg.ID:x}] >KInfo: <{key}>")
        return True

    @msg(SMC_GET_KEY_BY_INDEX, DIR.TX, SMCGetKeyByIndex)
    def GetKeyByIndex(self, msg):
        self.state.rb[msg.ID] = msg.TYPE, msg.INDEX, None
        self.log(f"[{msg.ID:x}] >KIdx: <{msg.INDEX}>")
        return True

    @msg(None, DIR.RX, Register64)
    def RXMsg(self, msg):
        if self.state.sram_addr is None:
            self.log(f"SRAM address: {msg.value:#x}")
            self.state.sram_addr = msg.value
            return True

        msg = SMCResult(msg.value)
        if msg.RESULT != 0:
            self.log(f"[{msg.ID:x}] <Err: 0x{msg.RESULT:02x}")
            return True

        if msg.ID in self.state.rb:
            msgtype, key, size = self.state.rb.pop(msg.ID)
            if msgtype in (SMC_READ_KEY, SMC_RW_KEY):
                if size <= 4:
                    data = hex(msg.VALUE)
                else:
                    data = self.hv.iface.readmem(self.state.sram_addr, msg.SIZE).hex()
                self.log(f"[{msg.ID:x}] <R: <{key}> = {data}")
                return True

            elif msgtype == SMC_GET_KEY_INFO:
                data = self.hv.iface.readmem(self.state.sram_addr, 6)
                size, type, flags = struct.unpack("B4sB", data)
                self.log(f"[{msg.ID:x}] <Info: <{key}>: size={size} type={type.decode('ascii')} flags={flags:#x}")
                return True

            elif msgtype == SMC_GET_KEY_BY_INDEX:
                kname = msg.VALUE.to_bytes(4, byteorder="little").decode("ascii")
                self.log(f"[{msg.ID:x}] <Key @{key}: <{kname}>")
                return True

        self.log(f"[{msg.ID:x}] <OK {msg!r}")
        return True

class SMCTracer(ASCTracer):
    ENDPOINTS = {
        0x20: SMCEpTracer
    }

    def handle_msg(self, direction, r0, r1):
        super().handle_msg(direction, r0, r1)

smc_tracer = SMCTracer(hv, "/arm-io/smc", verbose=1)
smc_tracer.start()

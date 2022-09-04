# SPDX-License-Identifier: MIT
import os, sys, struct, serial, time
from construct import *
from enum import IntEnum, IntFlag
from serial.tools.miniterm import Miniterm

from .utils import *
from .sysreg import *

__all__ = ["REGION_RWX_EL0", "REGION_RW_EL0", "REGION_RX_EL1"]

# Hack to disable input buffer flushing
class Serial(serial.Serial):
    def _reset_input_buffer(self):
        return

    def reset_input_buffer(self):
        return

class UartError(RuntimeError):
    pass

class UartTimeout(UartError):
    pass

class UartCMDError(UartError):
    pass

class UartChecksumError(UartError):
    pass

class UartRemoteError(UartError):
    pass

class Feature(IntFlag):
    DISABLE_DATA_CSUMS = 0x01  # Data transfers don't use checksums

    @classmethod
    def get_all(cls):
        return cls.DISABLE_DATA_CSUMS

    def __str__(self):
        return ", ".join(feature.name for feature in self.__class__
            if feature & self) or "<none>"


class START(IntEnum):
    BOOT = 0
    EXCEPTION = 1
    EXCEPTION_LOWER = 2
    HV = 3

class EXC(IntEnum):
    SYNC = 0
    IRQ = 1
    FIQ = 2
    SERROR = 3

class EVENT(IntEnum):
    MMIOTRACE = 1
    IRQTRACE = 2

class EXC_RET(IntEnum):
    UNHANDLED = 1
    HANDLED = 2
    EXIT_GUEST = 3
    STEP = 4

class DCP_SHUTDOWN_MODE(IntEnum):
    QUIESCED = 0
    SLEEP_IF_EXTERNAL = 1
    SLEEP = 2

class PIX_FMT(IntEnum):
    XRGB = 0
    XBGR = 1

class DART(IntEnum):
    T8020 = 0
    T8110 = 1
    T6000 = 2

ExcInfo = Struct(
    "regs" / Array(32, Int64ul),
    "spsr" / RegAdapter(SPSR),
    "elr" / Int64ul,
    "esr" / RegAdapter(ESR),
    "far" / Int64ul,
    "afsr1" / Int64ul,
    "sp" / Array(3, Int64ul),
    "cpu_id" / Int64ul,
    "mpidr" / Int64ul,
    "elr_phys" / Int64ul,
    "far_phys" / Int64ul,
    "sp_phys" / Int64ul,
    "data" / Int64ul,
)
# Sends 56+ byte Commands and Expects 36 Byte Responses
# Commands are format <I48sI
#   4 byte command, 48 byte null padded data + 4 byte checksum
# Responses are of the format: struct format <Ii24sI
#   4byte Response , 4 byte status, 24 byte string,  4 byte Checksum
#    Response must start 0xff55aaXX where XX distiguishes between them
#    In little endian mode these numbers as listed as REQ_* constants
# defined under UartInterface
#
#  Event Response REQ_EVENT passed to registered Event Handler
#  Boot Response REQ_BOOT passed to handle_boot() which may
#       pass to a matching registered handler based on reason, code values
#  If the status is ST_OK returns the data field to caller
#     Otherwise reports a remote Error

class UartInterface(Reloadable):
    REQ_NOP = 0x00AA55FF
    REQ_PROXY = 0x01AA55FF
    REQ_MEMREAD = 0x02AA55FF
    REQ_MEMWRITE = 0x03AA55FF
    REQ_BOOT = 0x04AA55FF
    REQ_EVENT = 0x05AA55FF

    CHECKSUM_SENTINEL = 0xD0DECADE
    DATA_END_SENTINEL = 0xB0CACC10

    ST_OK = 0
    ST_BADCMD = -1
    ST_INVAL = -2
    ST_XFERERR = -3
    ST_CSUMERR = -4

    CMD_LEN = 56
    REPLY_LEN = 36
    EVENT_HDR_LEN = 8

    def __init__(self, device=None, debug=False):
        self.debug = debug
        self.devpath = None
        if device is None:
            device = os.environ.get("M1N1DEVICE", "/dev/m1n1:115200")
        if isinstance(device, str):
            baud = 115200
            if ":" in device:
                device, baud = device.rsplit(":", 1)
                baud = int(baud)
            self.devpath = device
            self.baudrate = baud

            device = Serial(self.devpath, baud)

        self.dev = device
        self.dev.timeout = 0
        self.dev.flushOutput()
        self.dev.flushInput()
        self.pted = False
        #d = self.dev.read(1)
        #while d != "":
            #d = self.dev.read(1)
        self.dev.timeout = int(os.environ.get("M1N1TIMEOUT", "3"))
        self.tty_enable = True
        self.handlers = {}
        self.evt_handlers = {}
        self.enabled_features = Feature(0)

    def checksum(self, data):
        sum = 0xDEADBEEF;
        for c in data:
            sum *= 31337
            sum += c ^ 0x5a
            sum &= 0xFFFFFFFF

        return (sum ^ 0xADDEDBAD) & 0xFFFFFFFF

    def data_checksum(self, data):
        if self.enabled_features & Feature.DISABLE_DATA_CSUMS:
            return self.CHECKSUM_SENTINEL

        return self.checksum(data)

    def readfull(self, size):
        d = b''
        while len(d) < size:
            block = self.dev.read(size - len(d))
            if not block:
                raise UartTimeout("Expected %d bytes, got %d bytes"%(size,len(d)))
            d += block
        return d

    def cmd(self, cmd, payload=b""):
        if len(payload) > self.CMD_LEN:
            raise ValueError("Incorrect payload size %d"%len(payload))

        payload = payload.ljust(self.CMD_LEN, b"\x00")
        command = struct.pack("<I", cmd) + payload
        command += struct.pack("<I", self.checksum(command))
        if self.debug:
            print("<<", hexdump(command))
        self.dev.write(command)

    def unkhandler(self, s):
        if not self.tty_enable:
            return
        for c in s:
            if not self.pted:
                sys.stdout.write("TTY> ")
                self.pted = True
            if c == 10:
                self.pted = False
            sys.stdout.write(chr(c))
            sys.stdout.flush()

    def ttymode(self, dev=None):
        if dev is None:
            dev = self.dev

        tout = dev.timeout
        self.tty_enable = True
        dev.timeout = None

        term = Miniterm(dev, eol='cr')
        term.exit_character = chr(0x1d)  # GS/CTRL+]
        term.menu_character = chr(0x14)  # Menu: CTRL+T
        term.raw = True
        term.set_rx_encoding('UTF-8')
        term.set_tx_encoding('UTF-8')

        print('--- TTY mode | Quit: CTRL+] | Menu: CTRL+T ---')
        term.start()
        try:
            term.join(True)
        except KeyboardInterrupt:
            pass

        print('--- Exit TTY mode ---')
        term.join()
        term.close()

        dev.timeout = tout
        self.tty_enable = False

    def reply(self, cmd):
        reply = b''
        while True:
            if not reply or reply[-1] != 255:
                reply = b''
                reply += self.readfull(1)
                if reply != b"\xff":
                    self.unkhandler(reply)
                    continue
            else:
                reply = b'\xff'
            reply += self.readfull(1)
            if reply != b"\xff\x55":
                self.unkhandler(reply)
                continue
            reply += self.readfull(1)
            if reply != b"\xff\x55\xaa":
                self.unkhandler(reply)
                continue
            reply += self.readfull(1)
            cmdin = struct.unpack("<I", reply)[0]
            if cmdin == self.REQ_EVENT:
                reply += self.readfull(self.EVENT_HDR_LEN - 4)
                data_len, event_type = struct.unpack("<HH", reply[4:])
                reply += self.readfull(data_len + 4)
                if self.debug:
                    print(">>", hexdump(reply))
                checksum = struct.unpack("<I", reply[-4:])[0]
                ccsum = self.data_checksum(reply[:-4])
                if checksum != ccsum:
                    print("Event checksum error: Expected 0x%08x, got 0x%08x"%(checksum, ccsum))
                    raise UartChecksumError()
                self.handle_event(EVENT(event_type), reply[self.EVENT_HDR_LEN:-4])
                reply = b''
                continue

            reply += self.readfull(self.REPLY_LEN - 4)
            if self.debug:
                print(">>", hexdump(reply))
            status, data, checksum = struct.unpack("<i24sI", reply[4:])
            ccsum = self.checksum(reply[:-4])
            if checksum != ccsum:
                print("Reply checksum error: Expected 0x%08x, got 0x%08x"%(checksum, ccsum))
                raise UartChecksumError()

            if cmdin != cmd:
                if cmdin == self.REQ_BOOT and status == self.ST_OK:
                    self.handle_boot(data)
                    reply = b''
                    continue
                raise UartCMDError("Reply command mismatch: Expected 0x%08x, got 0x%08x"%(cmd, cmdin))
            if status != self.ST_OK:
                if status == self.ST_BADCMD:
                    raise UartRemoteError("Reply error: Bad Command")
                elif status == self.ST_INVAL:
                    raise UartRemoteError("Reply error: Invalid argument")
                elif status == self.ST_XFERERR:
                    raise UartRemoteError("Reply error: Data transfer failed")
                elif status == self.ST_CSUMERR:
                    raise UartRemoteError("Reply error: Data checksum failed")
                else:
                    raise UartRemoteError("Reply error: Unknown error (%d)"%status)
            return data

    def handle_boot(self, data):
        reason, code, info = struct.unpack("<IIQ", data[:16])
        reason = START(reason)
        if reason in (START.EXCEPTION, START.EXCEPTION_LOWER):
            code = EXC(code)
        if (reason, code) in self.handlers:
            self.handlers[(reason, code)](reason, code, info)
        elif reason != START.BOOT:
            print(f"Proxy callback without handler: {reason}, {code}")

    def set_handler(self, reason, code, handler):
        self.handlers[(reason, code)] = handler

    def handle_event(self, event_id, data):
        if event_id in self.evt_handlers:
            self.evt_handlers[event_id](data)

    def set_event_handler(self, event_id, handler):
        self.evt_handlers[event_id] = handler

    def wait_boot(self):
        try:
            return self.reply(self.REQ_BOOT)
        except:
            # Over USB, reboots cause a reconnect
            self.dev.close()
            print("Waiting for reconnection... ", end="")
            sys.stdout.flush()
            for i in range(100):
                print(".", end="")
                sys.stdout.flush()
                try:
                    self.dev.open()
                except serial.serialutil.SerialException:
                    time.sleep(0.1)
                else:
                    break
            else:
                raise UartTimeout("Reconnection timed out")
            print(" Connected")

    def wait_and_handle_boot(self):
        self.handle_boot(self.wait_boot())

    def nop(self):
        features = Feature.get_all()

        # Send the supported feature flags in the NOP message (has no effect
        # if the target does not support it)
        self.cmd(self.REQ_NOP, struct.pack("<Q", features.value))
        result = self.reply(self.REQ_NOP)

        # Get the enabled feature flags from the message response (returns
        # 0 if the target does not support it)
        features = Feature(struct.unpack("<QQQ", result)[0])

        if self.debug:
            print(f"Enabled features: {features}")

        self.enabled_features = features

    def proxyreq(self, req, reboot=False, no_reply=False, pre_reply=None):
        self.cmd(self.REQ_PROXY, req)
        if pre_reply:
            pre_reply()
        if no_reply:
            return
        elif reboot:
            return self.wait_boot()
        else:
            return self.reply(self.REQ_PROXY)

    def writemem(self, addr, data, progress=False):
        checksum = self.data_checksum(data)
        size = len(data)
        req = struct.pack("<QQI", addr, size, checksum)
        self.cmd(self.REQ_MEMWRITE, req)
        if self.debug:
            print("<< DATA:")
            chexdump(data)
        for i in range(0, len(data), 8192):
            self.dev.write(data[i:i + 8192])
            if progress:
                sys.stdout.write(".")
                sys.stdout.flush()
        if progress:
            print()
        if self.enabled_features & Feature.DISABLE_DATA_CSUMS:
            # Extra sentinel after the data to make sure no data is lost
            self.dev.write(struct.pack("<I", self.DATA_END_SENTINEL))

        # should automatically report a CRC failure
        self.reply(self.REQ_MEMWRITE)

    def readmem(self, addr, size):
        if size == 0:
            return b""

        req = struct.pack("<QQ", addr, size)
        self.cmd(self.REQ_MEMREAD, req)
        reply = self.reply(self.REQ_MEMREAD)
        checksum = struct.unpack("<I",reply[:4])[0]
        data = self.readfull(size)
        if self.debug:
            print(">> DATA:")
            chexdump(data)
        ccsum = self.data_checksum(data)
        if checksum != ccsum:
            raise UartChecksumError("Reply data checksum error: Expected 0x%08x, got 0x%08x"%(checksum, ccsum))

        if self.enabled_features & Feature.DISABLE_DATA_CSUMS:
            # Extra sentinel after the data to make sure no data was lost
            sentinel = struct.unpack("<I", self.readfull(4))[0]
            if sentinel != self.DATA_END_SENTINEL:
                raise UartChecksumError(f"Reply data sentinel error: Expected "
                    f"{self.DATA_END_SENTINEL:#x}, got {sentinel:#x}")

        return data

    def readstruct(self, addr, stype):
        return stype.parse(self.readmem(addr, stype.sizeof()))

class ProxyError(RuntimeError):
    pass

class ProxyReplyError(ProxyError):
    pass

class ProxyRemoteError(ProxyError):
    pass

class ProxyCommandError(ProxyRemoteError):
    pass

class AlignmentError(Exception):
    pass

class IODEV(IntEnum):
    UART = 0
    FB = 1
    USB_VUART = 2
    USB0 = 3
    USB1 = 4
    USB2 = 5
    USB3 = 6
    USB4 = 7
    USB5 = 8
    USB6 = 9
    USB7 = 10

class USAGE(IntFlag):
    CONSOLE = (1 << 0)
    UARTPROXY = (1 << 1)

class GUARD(IntFlag):
    OFF = 0
    SKIP = 1
    MARK = 2
    RETURN = 3
    SILENT = 0x100

REGION_RWX_EL0 = 0x80000000000
REGION_RW_EL0 = 0xa0000000000
REGION_RX_EL1 = 0xc0000000000

# Uses UartInterface.proxyreq() to send requests to M1N1 and process
# reponses sent back.
class M1N1Proxy(Reloadable):
    S_OK = 0
    S_BADCMD = -1

    P_NOP = 0x000
    P_EXIT = 0x001
    P_CALL = 0x002
    P_GET_BOOTARGS = 0x003
    P_GET_BASE = 0x004
    P_SET_BAUD = 0x005
    P_UDELAY = 0x006
    P_SET_EXC_GUARD = 0x007
    P_GET_EXC_COUNT = 0x008
    P_EL0_CALL = 0x009
    P_EL1_CALL = 0x00a
    P_VECTOR = 0x00b
    P_GL1_CALL = 0x00c
    P_GL2_CALL = 0x00d
    P_GET_SIMD_STATE = 0x00e
    P_PUT_SIMD_STATE = 0x00f
    P_REBOOT = 0x010

    P_WRITE64 = 0x100
    P_WRITE32 = 0x101
    P_WRITE16 = 0x102
    P_WRITE8 = 0x103
    P_READ64 = 0x104
    P_READ32 = 0x105
    P_READ16 = 0x106
    P_READ8 = 0x107
    P_SET64 = 0x108
    P_SET32 = 0x109
    P_SET16 = 0x10a
    P_SET8 = 0x10b
    P_CLEAR64 = 0x10c
    P_CLEAR32 = 0x10d
    P_CLEAR16 = 0x10e
    P_CLEAR8 = 0x10f
    P_MASK64 = 0x110
    P_MASK32 = 0x111
    P_MASK16 = 0x112
    P_MASK8 = 0x113
    P_WRITEREAD64 = 0x114
    P_WRITEREAD32 = 0x115
    P_WRITEREAD16 = 0x116
    P_WRITEREAD8 = 0x117

    P_MEMCPY64 = 0x200
    P_MEMCPY32 = 0x201
    P_MEMCPY16 = 0x202
    P_MEMCPY8 = 0x203
    P_MEMSET64 = 0x204
    P_MEMSET32 = 0x205
    P_MEMSET16 = 0x206
    P_MEMSET8 = 0x207

    P_IC_IALLUIS = 0x300
    P_IC_IALLU = 0x301
    P_IC_IVAU = 0x302
    P_DC_IVAC = 0x303
    P_DC_ISW = 0x304
    P_DC_CSW = 0x305
    P_DC_CISW = 0x306
    P_DC_ZVA = 0x307
    P_DC_CVAC = 0x308
    P_DC_CVAU = 0x309
    P_DC_CIVAC = 0x30a
    P_MMU_SHUTDOWN = 0x30b
    P_MMU_INIT = 0x30c
    P_MMU_DISABLE = 0x30d
    P_MMU_RESTORE = 0x30e
    P_MMU_INIT_SECONDARY = 0x30f

    P_XZDEC = 0x400
    P_GZDEC = 0x401

    P_SMP_START_SECONDARIES = 0x500
    P_SMP_CALL = 0x501
    P_SMP_CALL_SYNC = 0x502
    P_SMP_WAIT = 0x503
    P_SMP_SET_WFE_MODE = 0x504

    P_HEAPBLOCK_ALLOC = 0x600
    P_MALLOC = 0x601
    P_MEMALIGN = 0x602
    P_FREE = 0x602

    P_KBOOT_BOOT = 0x700
    P_KBOOT_SET_CHOSEN = 0x701
    P_KBOOT_SET_INITRD = 0x702
    P_KBOOT_PREPARE_DT = 0x703

    P_PMGR_CLOCK_ENABLE = 0x800
    P_PMGR_CLOCK_DISABLE = 0x801
    P_PMGR_ADT_CLOCKS_ENABLE = 0x802
    P_PMGR_ADT_CLOCKS_DISABLE = 0x803
    P_PMGR_RESET = 0x804

    P_IODEV_SET_USAGE = 0x900
    P_IODEV_CAN_READ = 0x901
    P_IODEV_CAN_WRITE = 0x902
    P_IODEV_READ = 0x903
    P_IODEV_WRITE = 0x904
    P_IODEV_WHOAMI = 0x905
    P_USB_IODEV_VUART_SETUP = 0x906

    P_TUNABLES_APPLY_GLOBAL = 0xa00
    P_TUNABLES_APPLY_LOCAL = 0xa01

    P_DART_INIT = 0xb00
    P_DART_SHUTDOWN = 0xb01
    P_DART_MAP = 0xb02
    P_DART_UNMAP = 0xb03

    P_HV_INIT = 0xc00
    P_HV_MAP = 0xc01
    P_HV_START = 0xc02
    P_HV_TRANSLATE = 0xc03
    P_HV_PT_WALK = 0xc04
    P_HV_MAP_VUART = 0xc05
    P_HV_TRACE_IRQ = 0xc06
    P_HV_WDT_START = 0xc07
    P_HV_START_SECONDARY = 0xc08
    P_HV_SWITCH_CPU = 0xc09
    P_HV_SET_TIME_STEALING = 0xc0a
    P_HV_PIN_CPU = 0xc0b
    P_HV_WRITE_HCR = 0xc0c

    P_FB_INIT = 0xd00
    P_FB_SHUTDOWN = 0xd01
    P_FB_BLIT = 0xd02
    P_FB_UNBLIT = 0xd03
    P_FB_FILL = 0xd04
    P_FB_CLEAR = 0xd05
    P_FB_DISPLAY_LOGO = 0xd06
    P_FB_RESTORE_LOGO = 0xd07
    P_FB_IMPROVE_LOGO = 0xd08

    P_PCIE_INIT = 0xe00
    P_PCIE_SHUTDOWN = 0xe01

    P_NVME_INIT = 0xf00
    P_NVME_SHUTDOWN = 0xf01
    P_NVME_READ = 0xf02
    P_NVME_FLUSH = 0xf03

    P_MCC_GET_CARVEOUTS = 0x1000

    P_DISPLAY_INIT = 0x1100
    P_DISPLAY_CONFIGURE = 0x1101
    P_DISPLAY_SHUTDOWN = 0x1102

    P_DAPF_INIT_ALL = 0x1200
    P_DAPF_INIT = 0x1201

    def __init__(self, iface, debug=False):
        self.debug = debug
        self.iface = iface
        self.heap = None

    def _request(self, opcode, *args, reboot=False, signed=False, no_reply=False, pre_reply=None):
        if len(args) > 6:
            raise ValueError("Too many arguments")
        args = list(args) + [0] * (6 - len(args))
        req = struct.pack("<7Q", opcode, *args)
        if self.debug:
            print("<<<< %08x: %08x %08x %08x %08x %08x %08x"%tuple([opcode] + args))
        reply = self.iface.proxyreq(req, reboot=reboot, no_reply=no_reply, pre_reply=None)
        if no_reply or reboot and reply is None:
            return
        ret_fmt = "q" if signed else "Q"
        rop, status, retval = struct.unpack("<Qq" + ret_fmt, reply)
        if self.debug:
            print(">>>> %08x: %d %08x"%(rop, status, retval))
        if reboot:
            return
        if rop != opcode:
            raise ProxyReplyError("Reply opcode mismatch: Expected 0x%08x, got 0x%08x"%(opcode,rop))
        if status != self.S_OK:
            if status == self.S_BADCMD:
                raise ProxyCommandError("Reply error: Bad Command")
            else:
                raise ProxyRemoteError("Reply error: Unknown error (%d)"%status)
        return retval

    def request(self, opcode, *args, **kwargs):
        free = []
        args = list(args)
        args2 = []
        for i, arg in enumerate(args):
            if isinstance(arg, str):
                arg = arg.encode("utf-8") + b"\0"
            if isinstance(arg, bytes) and self.heap:
                p = self.heap.malloc(len(arg))
                free.append(p)
                self.iface.writemem(p, arg)
                if (i < (len(args) - 1)) and args[i + 1] is None:
                    args[i + 1] = len(arg)
                arg = p
            args2.append(arg)
        try:
            return self._request(opcode, *args2, **kwargs)
        finally:
            for i in free:
                self.heap.free(i)

    def nop(self):
        self.request(self.P_NOP)
    def exit(self, retval=0):
        self.request(self.P_EXIT, retval)
    def call(self, addr, *args, reboot=False):
        if len(args) > 5:
            raise ValueError("Too many arguments")
        return self.request(self.P_CALL, addr, *args, reboot=reboot)
    def reload(self, addr, *args, el1=False):
        if len(args) > 4:
            raise ValueError("Too many arguments")
        if el1:
            self.request(self.P_EL1_CALL, addr, *args, no_reply=True)
        else:
            try:
                self.request(self.P_VECTOR, addr, *args)
                self.iface.wait_boot()
            except ProxyCommandError: # old m1n1 does not support P_VECTOR
                try:
                    self.mmu_shutdown()
                except ProxyCommandError: # older m1n1 does not support MMU
                    pass
                self.request(self.P_CALL, addr, *args, reboot=True)
    def get_bootargs(self):
        return self.request(self.P_GET_BOOTARGS)
    def get_base(self):
        return self.request(self.P_GET_BASE)
    def set_baud(self, baudrate):
        self.iface.tty_enable = False
        def change():
            self.iface.dev.baudrate = baudrate
        try:
            self.request(self.P_SET_BAUD, baudrate, 16, 0x005aa5f0, pre_reply=change)
        finally:
            self.iface.tty_enable = True
    def udelay(self, usec):
        self.request(self.P_UDELAY, usec)
    def set_exc_guard(self, mode):
        self.request(self.P_SET_EXC_GUARD, mode)
    def get_exc_count(self):
        return self.request(self.P_GET_EXC_COUNT)
    def el0_call(self, addr, *args):
        if len(args) > 4:
            raise ValueError("Too many arguments")
        return self.request(self.P_EL0_CALL, addr, *args)
    def el1_call(self, addr, *args):
        if len(args) > 4:
            raise ValueError("Too many arguments")
        return self.request(self.P_EL1_CALL, addr, *args)
    def gl1_call(self, addr, *args):
        if len(args) > 4:
            raise ValueError("Too many arguments")
        return self.request(self.P_GL1_CALL, addr, *args)
    def gl2_call(self, addr, *args):
        if len(args) > 4:
            raise ValueError("Too many arguments")
        return self.request(self.P_GL2_CALL, addr, *args)
    def get_simd_state(self, buf):
        self.request(self.P_GET_SIMD_STATE, buf)
    def put_simd_state(self, buf):
        self.request(self.P_PUT_SIMD_STATE, buf)
    def reboot(self):
        self.request(self.P_REBOOT, no_reply=True)

    def write64(self, addr, data):
        '''write 8 byte value to given address'''
        if addr & 7:
            raise AlignmentError()
        self.request(self.P_WRITE64, addr, data)
    def write32(self, addr, data):
        '''write 4 byte value to given address'''
        if addr & 3:
            raise AlignmentError()
        self.request(self.P_WRITE32, addr, data)
    def write16(self, addr, data):
        '''write 2 byte value to given address'''
        if addr & 1:
            raise AlignmentError()
        self.request(self.P_WRITE16, addr, data)
    def write8(self, addr, data):
        '''write 1 byte value to given address'''
        self.request(self.P_WRITE8, addr, data)

    def read64(self, addr):
        '''return 8 byte value from given address'''
        if addr & 7:
            raise AlignmentError()
        return self.request(self.P_READ64, addr)
    def read32(self, addr):
        '''return 4 byte value given address'''
        if addr & 3:
            raise AlignmentError()
        return self.request(self.P_READ32, addr)
    def read16(self, addr):
        '''return 2 byte value from given address'''
        if addr & 1:
            raise AlignmentError()
        return self.request(self.P_READ16, addr)
    def read8(self, addr):
        '''return 1 byte value from given address'''
        return self.request(self.P_READ8, addr)

    def set64(self, addr, data):
        '''Or 64 bit value of data into memory at addr and return result'''
        if addr & 7:
            raise AlignmentError()
        return self.request(self.P_SET64, addr, data)
    def set32(self, addr, data):
        '''Or 32 bit value of data into memory at addr and return result'''
        if addr & 3:
            raise AlignmentError()
        return self.request(self.P_SET32, addr, data)
    def set16(self, addr, data):
        '''Or 16 bit value of data into memory at addr and return result'''
        if addr & 1:
            raise AlignmentError()
        return self.request(self.P_SET16, addr, data)
    def set8(self, addr, data):
        '''Or byte value of data into memory at addr and return result'''
        return self.request(self.P_SET8, addr, data)

    def clear64(self, addr, data):
        '''Clear bits in 64 bit memory at address addr that are set
    in parameter data and return result'''
        if addr & 7:
            raise AlignmentError()
        return self.request(self.P_CLEAR64, addr, data)
    def clear32(self, addr, data):
        '''Clear bits in 32 bit memory at address addr that are set
    in parameter data and return result'''
        if addr & 3:
            raise AlignmentError()
        return self.request(self.P_CLEAR32, addr, data)
    def clear16(self, addr, data):
        '''Clear bits in 16 bit memory at address addr that are set
    in parameter data and return result'''
        if addr & 1:
            raise AlignmentError()
        return self.request(self.P_CLEAR16, addr, data)
    def clear8(self, addr, data):
        '''Clear bits in 8 bit memory at addr that are set in data
    and return result'''
        return self.request(self.P_CLEAR8, addr, data)

    def mask64(self, addr, clear, set):
        '''Clear bits in 64 bit memory at address addr that are
 set in clear, then set the bits in set and return result'''
        if addr & 7:
            raise AlignmentError()
        return self.request(self.P_MASK64, addr, clear, set)
    def mask32(self, addr, clear, set):
        '''Clear bits in 32 bit memory at address addr that are
 set in clear, then set the bits in set and return result'''
        if addr & 3:
            raise AlignmentError()
        return self.request(self.P_MASK32, addr, clear, set)
    def mask16(self, addr, clear, set):
        '''Clear select bits in 16 bit memory addr that are set
 in clear parameter, then set the bits in set parameter and return result'''
        if addr & 1:
            raise AlignmentError()
        return self.request(self.P_MASK16, addr, clear, set)
    def mask8(self, addr, clear, set):
        '''Clear bits in 1 byte memory at addr that are set
 in clear parameter, then set the bits in set parameter
 and return the result'''
        return self.request(self.P_MASK8, addr, clear, set)

    def writeread64(self, addr, data):
        return self.request(self.P_WRITEREAD64, addr, data)
    def writeread32(self, addr, data):
        return self.request(self.P_WRITEREAD32, addr, data)
    def writeread16(self, addr, data):
        return self.request(self.P_WRITEREAD16, addr, data)
    def writeread8(self, addr, data):
        return self.request(self.P_WRITEREAD8, addr, data)

    def memcpy64(self, dst, src, size):
        if src & 7 or dst & 7:
            raise AlignmentError()
        self.request(self.P_MEMCPY64, dst, src, size)
    def memcpy32(self, dst, src, size):
        if src & 3 or dst & 3:
            raise AlignmentError()
        self.request(self.P_MEMCPY32, dst, src, size)
    def memcpy16(self, dst, src, size):
        if src & 1 or dst & 1:
            raise AlignmentError()
        self.request(self.P_MEMCPY16, dst, src, size)
    def memcpy8(self, dst, src, size):
        self.request(self.P_MEMCPY8, dst, src, size)

    def memset64(self, dst, src, size):
        if dst & 7:
            raise AlignmentError()
        self.request(self.P_MEMSET64, dst, src, size)
    def memset32(self, dst, src, size):
        if dst & 3:
            raise AlignmentError()
        self.request(self.P_MEMSET32, dst, src, size)
    def memset16(self, dst, src, size):
        if dst & 1:
            raise AlignmentError()
        self.request(self.P_MEMSET16, dst, src, size)
    def memset8(self, dst, src, size):
        self.request(self.P_MEMSET8, dst, src, size)

    def ic_ialluis(self):
        self.request(self.P_IC_IALLUIS)
    def ic_iallu(self):
        self.request(self.P_IC_IALLU)
    def ic_ivau(self, addr, size):
        self.request(self.P_IC_IVAU, addr, size)
    def dc_ivac(self, addr, size):
        self.request(self.P_DC_IVAC, addr, size)
    def dc_isw(self, sw):
        self.request(self.P_DC_ISW, sw)
    def dc_csw(self, sw):
        self.request(self.P_DC_CSW, sw)
    def dc_cisw(self, sw):
        self.request(self.P_DC_CISW, sw)
    def dc_zva(self, addr, size):
        self.request(self.P_DC_ZVA, addr, size)
    def dc_cvac(self, addr, size):
        self.request(self.P_DC_CVAC, addr, size)
    def dc_cvau(self, addr, size):
        self.request(self.P_DC_CVAU, addr, size)
    def dc_civac(self, addr, size):
        self.request(self.P_DC_CIVAC, addr, size)
    def mmu_shutdown(self):
        self.request(self.P_MMU_SHUTDOWN)
    def mmu_init(self):
        self.request(self.P_MMU_INIT)
    def mmu_disable(self):
        return self.request(self.P_MMU_DISABLE)
    def mmu_restore(self, flags):
        self.request(self.P_MMU_RESTORE, flags)
    def mmu_init_secondary(self, cpu):
        self.request(self.P_MMU_INIT_SECONDARY, cpu)


    def xzdec(self, inbuf, insize, outbuf=0, outsize=0):
        return self.request(self.P_XZDEC, inbuf, insize, outbuf,
                            outsize, signed=True)

    def gzdec(self, inbuf, insize, outbuf, outsize):
        return self.request(self.P_GZDEC, inbuf, insize, outbuf,
                            outsize, signed=True)

    def smp_start_secondaries(self):
        self.request(self.P_SMP_START_SECONDARIES)
    def smp_call(self, cpu, addr, *args):
        if len(args) > 4:
            raise ValueError("Too many arguments")
        self.request(self.P_SMP_CALL, cpu, addr, *args)
    def smp_call_sync(self, cpu, addr, *args):
        if len(args) > 4:
            raise ValueError("Too many arguments")
        return self.request(self.P_SMP_CALL_SYNC, cpu, addr, *args)
    def smp_wait(self, cpu):
        return self.request(self.P_SMP_WAIT, cpu)
    def smp_set_wfe_mode(self, mode):
        return self.request(self.P_SMP_SET_WFE_MODE, mode)

    def heapblock_alloc(self, size):
        return self.request(self.P_HEAPBLOCK_ALLOC, size)
    def malloc(self, size):
        return self.request(self.P_MALLOC, size)
    def memalign(self, align, size):
        return self.request(self.P_MEMALIGN, align, size)
    def free(self, ptr):
        self.request(self.P_FREE, ptr)

    def kboot_boot(self, kernel):
        self.request(self.P_KBOOT_BOOT, kernel)
    def kboot_set_chosen(self, name, value):
        self.request(self.P_KBOOT_SET_CHOSEN, name, value)
    def kboot_set_initrd(self, base, size):
        self.request(self.P_KBOOT_SET_INITRD, base, size)
    def kboot_prepare_dt(self, dt_addr):
        return self.request(self.P_KBOOT_PREPARE_DT, dt_addr)

    def pmgr_clock_enable(self, clkid):
        return self.request(self.P_PMGR_CLOCK_ENABLE, clkid)
    def pmgr_clock_disable(self, clkid):
        return self.request(self.P_PMGR_CLOCK_DISABLE, clkid)
    def pmgr_adt_clocks_enable(self, path):
        return self.request(self.P_PMGR_ADT_CLOCKS_ENABLE, path)
    def pmgr_adt_clocks_disable(self, path):
        return self.request(self.P_PMGR_ADT_CLOCKS_DISABLE, path)
    def pmgr_reset(self, die, name):
        return self.request(self.P_PMGR_RESET, die, name)

    def iodev_set_usage(self, iodev, usage):
        return self.request(self.P_IODEV_SET_USAGE, iodev, usage)
    def iodev_can_read(self, iodev):
        return self.request(self.P_IODEV_CAN_READ, iodev)
    def iodev_can_write(self, iodev):
        return self.request(self.P_IODEV_CAN_WRITE, iodev)
    def iodev_read(self, iodev, buf, size=None):
        return self.request(self.P_IODEV_READ, iodev, buf, size)
    def iodev_write(self, iodev, buf, size=None):
        return self.request(self.P_IODEV_WRITE, iodev, buf, size)
    def iodev_whoami(self):
        return IODEV(self.request(self.P_IODEV_WHOAMI))
    def usb_iodev_vuart_setup(self, iodev):
        return self.request(self.P_USB_IODEV_VUART_SETUP, iodev)

    def tunables_apply_global(self, path, prop):
        return self.request(self.P_TUNABLES_APPLY_GLOBAL, path, prop)
    def tunables_apply_local(self, path, prop, reg_offset):
        return self.request(self.P_TUNABLES_APPLY_LOCAL, path, prop, reg_offset)
    def tunables_apply_local_addr(self, path, prop, base):
        return self.request(self.P_TUNABLES_APPLY_LOCAL, path, prop, base)

    def dart_init(self, base, sid, dart_type=DART.T8020):
        return self.request(self.P_DART_INIT, base, sid, dart_type)
    def dart_shutdown(self, dart):
        return self.request(self.P_DART_SHUTDOWN, dart)
    def dart_map(self, dart, iova, bfr, len):
        return self.request(self.P_DART_MAP, dart, iova, bfr, len)
    def dart_unmap(self, dart, iova, len):
        return self.request(self.P_DART_UNMAP, dart, iova, len)

    def hv_init(self):
        return self.request(self.P_HV_INIT)
    def hv_map(self, from_, to, size, incr):
        return self.request(self.P_HV_MAP, from_, to, size, incr)
    def hv_start(self, entry, *args):
        return self.request(self.P_HV_START, entry, *args)
    def hv_translate(self, addr, s1=False, w=False):
        '''Translate virtual address
 stage 1 only if s1, for write if w'''
        return self.request(self.P_HV_TRANSLATE, addr, s1, w)
    def hv_pt_walk(self, addr):
        return self.request(self.P_HV_PT_WALK, addr)
    def hv_map_vuart(self, base, irq, iodev):
        return self.request(self.P_HV_MAP_VUART, base, irq, iodev)
    def hv_trace_irq(self, evt_type, num, count, flags):
        return self.request(self.P_HV_TRACE_IRQ, evt_type, num, count, flags)
    def hv_wdt_start(self, cpu):
        return self.request(self.P_HV_WDT_START, cpu)
    def hv_start_secondary(self, cpu, entry, *args):
        return self.request(self.P_HV_START_SECONDARY, cpu, entry, *args)
    def hv_switch_cpu(self, cpu):
        return self.request(self.P_HV_SWITCH_CPU, cpu)
    def hv_set_time_stealing(self, enabled, reset):
        return self.request(self.P_HV_SET_TIME_STEALING, int(bool(enabled)), int(bool(reset)))
    def hv_pin_cpu(self, cpu):
        return self.request(self.P_HV_PIN_CPU, cpu)
    def hv_write_hcr(self, hcr):
        return self.request(self.P_HV_WRITE_HCR, hcr)

    def fb_init(self):
        return self.request(self.P_FB_INIT)
    def fb_shutdown(self, restore_logo=True):
        return self.request(self.P_FB_SHUTDOWN, restore_logo)
    def fb_blit(self, x, y, w, h, ptr, stride, pix_fmt=PIX_FMT.XRGB):
        return self.request(self.P_FB_BLIT, x, y, w, h, ptr, stride | pix_fmt << 32)
    def fb_unblit(self, x, y, w, h, ptr, stride):
        return self.request(self.P_FB_UNBLIT, x, y, w, h, ptr, stride)
    def fb_fill(self, x, y, w, h, color):
        return self.request(self.P_FB_FILL, x, y, w, h, color)
    def fb_clear(self, color):
        return self.request(self.P_FB_CLEAR, color)
    def fb_display_logo(self):
        return self.request(self.P_FB_DISPLAY_LOGO)
    def fb_restore_logo(self):
        return self.request(self.P_FB_RESTORE_LOGO)
    def fb_improve_logo(self):
        return self.request(self.P_FB_IMPROVE_LOGO)

    def pcie_init(self):
        return self.request(self.P_PCIE_INIT)
    def pcie_shutdown(self):
        return self.request(self.P_PCIE_SHUTDOWN)

    def nvme_init(self):
        return self.request(self.P_NVME_INIT)
    def nvme_shutdown(self):
        return self.request(self.P_NVME_SHUTDOWN)
    def nvme_read(self, nsid, lba, bfr):
        return self.request(self.P_NVME_READ, nsid, lba, bfr)
    def nvme_flush(self, nsid):
        return self.request(self.P_NVME_FLUSH, nsid)

    def mcc_get_carveouts(self):
        return self.request(self.P_MCC_GET_CARVEOUTS)

    def display_init(self):
        return self.request(self.P_DISPLAY_INIT)
    def display_configure(self, cfg):
        return self.request(self.P_DISPLAY_CONFIGURE, cfg)
    def display_shutdown(self, mode):
        return self.request(self.P_DISPLAY_SHUTDOWN, mode)

    def dapf_init_all(self):
        return self.request(self.P_DAPF_INIT_ALL)
    def dapf_init(self, path):
        return self.request(self.P_DAPF_INIT, path)

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)

if __name__ == "__main__":
    import serial
    uartdev = os.environ.get("M1N1DEVICE", "/dev/m1n1")
    usbuart = serial.Serial(uartdev, 115200)
    uartif = UartInterface(usbuart, debug=True)
    print("Sending NOP...", end=' ')
    uartif.nop()
    print("OK")
    proxy = M1N1Proxy(uartif, debug=True)
    print("Sending Proxy NOP...", end=' ')
    proxy.nop()
    print("OK")
    print("Boot args: 0x%x" % proxy.get_bootargs())

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import os, sys, struct

def hexdump(s, sep=" "):
    return sep.join(["%02x"%x for x in s])

def hexdump32(s, sep=" "):
    vals = struct.unpack("<%dI" % (len(s)//4), s)
    return sep.join(["%08x"%x for x in vals])

def ascii(s):
    s2 = ""
    for c in s:
        if c < 0x20 or c > 0x7e:
            s2 += "."
        else:
            s2 += chr(c)
    return s2

def pad(s,c,l):
    if len(s) < l:
        s += c * (l - len(s))
    return s

def chexdump(s,st=0):
    for i in range(0,len(s),16):
        print("%08x  %s  %s  |%s|" % (
            i + st,
            hexdump(s[i:i+8], ' ').rjust(23),
            hexdump(s[i+8:i+16], ' ').rjust(23),
            ascii(s[i:i+16]).rjust(16)))

def chexdump32(s, st=0, abbreviate=True):
    last = None
    skip = False
    for i in range(0,len(s),32):
        val = s[i:i+32]
        if val == last and abbreviate:
            if not skip:
                print("%08x  *" % (i + st))
                skip = True
        else:
            print("%08x  %s" % (
                i + st,
                hexdump32(val, ' ')))
            last = val
            skip = False

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

class UartInterface:
    REQ_NOP = 0x00AA55FF
    REQ_PROXY = 0x01AA55FF
    REQ_MEMREAD = 0x02AA55FF
    REQ_MEMWRITE = 0x03AA55FF
    REQ_BOOT = 0x04AA55FF

    ST_OK = 0
    ST_BADCMD = -1
    ST_INVAL = -2
    ST_XFERERR = -3
    ST_CRCERR = -4

    CMD_LEN = 56
    REPLY_LEN = 36

    def __init__(self, device, debug=False):
        self.debug = debug
        self.dev = device
        self.dev.timeout = 0
        self.dev.flushOutput()
        self.dev.flushInput()
        self.pted = False
        #d = self.dev.read(1)
        #while d != "":
            #d = self.dev.read(1)
        self.dev.timeout = 3
        self.tty_enable = True

    def checksum(self, data):
        sum = 0xDEADBEEF;
        for c in data:
            sum *= 31337
            sum += c ^ 0x5a
            sum &= 0xFFFFFFFF

        return (sum ^ 0xADDEDBAD) & 0xFFFFFFFF

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

    def ttymode(self):
        self.tty_enable = True
        self.dev.timeout = None
        while True:
            sys.stdout.buffer.write(self.readfull(1))
            sys.stdout.buffer.flush()

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
            reply += self.readfull(self.REPLY_LEN - 3)
            if self.debug:
                print(">>", hexdump(reply))
            cmdin, status, data, checksum = struct.unpack("<Ii24sI", reply)
            ccsum = self.checksum(reply[:-4])
            if checksum != ccsum:
                print("Reply checksum error: Expected 0x%08x, got 0x%08x"%(checksum, ccsum))
                raise UartChecksumError()

            if cmdin != cmd:
                if cmdin == self.REQ_BOOT:
                    # Proxy rebooted in the meantime, try again
                    return self.reply(cmd)
                raise UartCMDError("Reply command mismatch: Expected 0x%08x, got 0x%08x"%(cmd, cmdin))
            if status != self.ST_OK:
                if status == self.ST_BADCMD:
                    raise UartRemoteError("Reply error: Bad Command")
                elif status == self.ST_INVAL:
                    raise UartRemoteError("Reply error: Invalid argument")
                elif status == self.ST_XFERERR:
                    raise UartRemoteError("Reply error: Data transfer failed")
                elif status == self.ST_CRCERR:
                    raise UartRemoteError("Reply error: Data checksum failed")
                else:
                    raise UartRemoteError("Reply error: Unknown error (%d)"%status)
            return data

    def nop(self):
        self.cmd(self.REQ_NOP)
        self.reply(self.REQ_NOP)

    def proxyreq(self, req, reboot=False, no_reply=False, pre_reply=None):
        self.cmd(self.REQ_PROXY, req)
        if pre_reply:
            pre_reply()
        if no_reply:
            return
        elif reboot:
            return self.reply(self.REQ_BOOT)
        else:
            return self.reply(self.REQ_PROXY)

    def writemem(self, addr, data, progress=False):
        checksum = self.checksum(data)
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
        # should automatically report a CRC failure
        self.reply(self.REQ_MEMWRITE)

    def readmem(self, addr, size):
        req = struct.pack("<QQ", addr, size)
        self.cmd(self.REQ_MEMREAD, req)
        reply = self.reply(self.REQ_MEMREAD)
        checksum = struct.unpack("<I",reply[:4])[0]
        data = self.readfull(size)
        if self.debug:
            print(">> DATA:")
            chexdump(data)
        ccsum = self.checksum(data)
        if checksum != ccsum:
            raise UartCRCError("Reply data checksum error: Expected 0x%08x, got 0x%08x"%(checksum, ccsum))
        return data

    def readstruct(self, addr, stype):
        return stype.parse(self.readmem(addr, stype.sizeof()))

class ProxyError(RuntimeError):
    pass

class ProxyCMDError(ProxyError):
    pass

class ProxyRemoteError(ProxyError):
    pass

class AlignmentError(Exception):
    pass

class M1N1Proxy:
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

    GUARD_OFF = 0
    GUARD_SKIP = 1
    GUARD_MARK = 2
    GUARD_RETURN = 3
    GUARD_SILENT = 0x100

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

    P_XZDEC = 0x400
    P_GZDEC = 0x401

    P_SMP_START_SECONDARIES = 0x500
    P_SMP_CALL = 0x501
    P_SMP_CALL_SYNC = 0x502

    P_HEAPBLOCK_ALLOC = 0x600
    P_MALLOC = 0x601
    P_MEMALIGN = 0x602
    P_FREE = 0x602

    P_KBOOT_BOOT = 0x700
    P_KBOOT_SET_BOOTARGS = 0x701
    P_KBOOT_SET_INITRD = 0x702
    P_KBOOT_PREPARE_DT = 0x703

    def __init__(self, iface, debug=False):
        self.debug = debug
        self.iface = iface

    def request(self, opcode, *args, reboot=False, signed=False, no_reply=False, pre_reply=None):
        if len(args) > 6:
            raise ValueError("Too many arguments")
        args = list(args) + [0] * (6 - len(args))
        req = struct.pack("<7Q", opcode, *args)
        if self.debug:
            print("<<<< %08x: %08x %08x %08x %08x %08x %08x"%tuple([opcode] + args))
        reply = self.iface.proxyreq(req, reboot=reboot, no_reply=no_reply, pre_reply=None)
        if no_reply:
            return
        ret_fmt = "q" if signed else "Q"
        rop, status, retval = struct.unpack("<Qq" + ret_fmt, reply)
        if self.debug:
            print(">>>> %08x: %d %08x"%(rop, status, retval))
        if reboot:
            return
        if rop != opcode:
            raise ProxyCMDError("Reply opcode mismatch: Expected 0x%08x, got 0x%08x"%(opcode,rop))
        if status != self.S_OK:
            if status == self.S_BADCMD:
                raise ProxyRemoteError("Reply error: Bad Command")
            else:
                raise ProxyRemoteError("Reply error: Unknown error (%d)"%status)
        return retval

    def nop(self):
        self.request(self.P_NOP)
    def exit(self):
        self.request(self.P_EXIT)
    def call(self, addr, *args):
        if len(args) > 4:
            raise ValueError("Too many arguments")
        return self.request(self.P_CALL, addr, *args)
    def reboot(self, addr, *args):
        if len(args) > 4:
            raise ValueError("Too many arguments")
        self.request(self.P_CALL, addr, *args, reboot=True)
    def vector(self, addr, *args):
        if len(args) > 4:
            raise ValueError("Too many arguments")
        self.request(self.P_CALL, addr, *args, no_reply=True)
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

    def write64(self, addr, data):
        if addr & 7:
            raise AlignmentError()
        self.request(self.P_WRITE64, addr, data)
    def write32(self, addr, data):
        if addr & 3:
            raise AlignmentError()
        self.request(self.P_WRITE32, addr, data)
    def write16(self, addr, data):
        if addr & 1:
            raise AlignmentError()
        self.request(self.P_WRITE16, addr, data)
    def write8(self, addr, data):
        self.request(self.P_WRITE8, addr, data)

    def read64(self, addr):
        if addr & 7:
            raise AlignmentError()
        return self.request(self.P_READ64, addr)
    def read32(self, addr):
        if addr & 3:
            raise AlignmentError()
        return self.request(self.P_READ32, addr)
    def read16(self, addr):
        if addr & 1:
            raise AlignmentError()
        return self.request(self.P_READ16, addr)
    def read8(self, addr):
        return self.request(self.P_READ8, addr)

    def set64(self, addr, data):
        if addr & 7:
            raise AlignmentError()
        self.request(self.P_SET64, addr, data)
    def set32(self, addr, data):
        if addr & 3:
            raise AlignmentError()
        self.request(self.P_SET32, addr, data)
    def set16(self, addr, data):
        if addr & 1:
            raise AlignmentError()
        self.request(self.P_SET16, addr, data)
    def set8(self, addr, data):
        self.request(self.P_SET8, addr, data)

    def clear64(self, addr, data):
        if addr & 7:
            raise AlignmentError()
        self.request(self.P_CLEAR64, addr, data)
    def clear32(self, addr, data):
        if addr & 3:
            raise AlignmentError()
        self.request(self.P_CLEAR32, addr, data)
    def clear16(self, addr, data):
        if addr & 1:
            raise AlignmentError()
        self.request(self.P_CLEAR16, addr, data)
    def clear8(self, addr, data):
        self.request(self.P_CLEAR8, addr, data)

    def mask64(self, addr, clear, set):
        if addr & 7:
            raise AlignmentError()
        self.request(self.P_MASK64, addr, clear, set)
    def mask32(self, addr, clear, set):
        if addr & 3:
            raise AlignmentError()
        self.request(self.P_MASK32, addr, clear, set)
    def mask16(self, addr, clear, set):
        if addr & 1:
            raise AlignmentError()
        self.request(self.P_MASK16, addr, clear, set)
    def mask8(self, addr, clear, set):
        self.request(self.P_MASK8, addr, clear, set)

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
    def ic_ivac(self, addr, size):
        self.request(self.P_IC_IVAC, addr, size)
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

    def heapblock_alloc(self, size):
        return self.request(self.P_HEAPBLOCK_ALLOC, size)
    def malloc(self, size):
        return self.request(self.P_MALLOC, size)
    def memalign(self, align, size):
        return self.request(self.P_MEMALIGN, align, size)
    def free(self, ptr):
        self.request(self.P_FREE, ptr)

    def kboot_boot(self, kernel):
        self.request(self.P_KBOOT_BOOT, kernel, no_reply=True)
    def kboot_set_bootargs(self, ba_p):
        self.request(self.P_KBOOT_SET_BOOTARGS, ba_p)
    def kboot_set_initrd(self, base, size):
        self.request(self.P_KBOOT_SET_INITRD, base, size)
    def kboot_prepare_dt(self, dt_addr):
        return self.request(self.P_KBOOT_PREPARE_DT, dt_addr)

if __name__ == "__main__":
    import serial
    uartdev = os.environ.get("M1N1DEVICE", "/dev/ttyUSB0")
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

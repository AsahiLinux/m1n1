# SPDX-License-Identifier: MIT
import errno, io, os, pkgutil, re, selectors, socketserver, threading, traceback
from construct import Array, BytesInteger, Container, Int32ul, Int64ul, Struct

from ...proxy import *
from ...sysreg import *
from ...utils import *

from ..types import *

__all__ = ["GDBServer"]

class GDBServer:
    __g = Struct(
        "regs" / Array(32, Int64ul),
        "pc" / Int64ul,
        "spsr" / Int32ul,
        "q" / Array(32, BytesInteger(16, swapped=True)),
        "fpsr" / Int32ul,
        "fpcr" / Int32ul,
    )
    __seperator = re.compile("[,;:]")

    def __init__(self, hv, address, log):
        self.__hc = None
        self.__hg = None
        self.__hv = hv
        self.__interrupt_eventfd = os.eventfd(0, flags=os.EFD_CLOEXEC | os.EFD_NONBLOCK)
        self.__interrupt_selector = selectors.DefaultSelector()
        self.__request = None
        self.log = log

        self.__interrupt_selector.register(self.__interrupt_eventfd, selectors.EVENT_READ)

        handle = self.__handle

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                handle(self.request)

        self.__server = socketserver.UnixStreamServer(address, Handler, False)
        self.__thread = threading.Thread(target=self.__server.serve_forever,)

    def __add_wp(self, addr, kind, lsc):
        start = addr & 7
        if start + kind > 8:
            return b"E01"

        self.__hv.add_hw_wp(addr & ~7, ((1 << kind) - 1) << start, lsc)
        return b"OK"

    def __remove_wp(self, addr):
        self.__hv.remove_hw_wp(addr & ~7)
        return b"OK"

    def __cpu(self, cpu):
        if cpu is None:
            return

        self.__hv.cpu(cpu)

    def __stop_reply(self):
        self.__hc = None
        self.__hg = None

        prefix = b"T05thread:"

        if self.__hv.exc_reason == START.EXCEPTION_LOWER:
            if self.__hv.exc_code == EXC.SYNC:
                if self.__hv.ctx.esr.EC == ESR_EC.BKPT_LOWER:
                    prefix = b"T05hwbreak:;thread:"
                elif self.__hv.ctx.esr.EC == ESR_EC.WATCH_LOWER:
                    bas = self.__hv.get_wp_bas(self.__hv.ctx.far)
                    if not bas is None and bas != 0:
                        offset = 0
                        while (bas & (1 << offset)) == 0:
                            offset += 1
                        addr = self.__hv.ctx.far + offset
                        formatted_addr = bytes(format(addr, "x"), "utf-8")
                        prefix = b"T05watch:" + formatted_addr + b";thread:"
        elif self.__hv.exc_reason == START.HV:
            if self.__hv.exc_code == HV_EVENT.USER_INTERRUPT:
                prefix = b"T02thread:"

        return prefix + bytes(format(self.__hv.ctx.cpu_id, "x"), "utf-8") + b";"

    def __wait_shell(self):
        try:
            os.eventfd_read(self.__interrupt_eventfd)
        except BlockingIOError:
            pass

        while not self.__interrupt_eventfd in (key.fileobj for key, mask in self.__interrupt_selector.select()):
            recv = self.__request.recv(1)
            if not recv:
                break

            for byte in recv:
                if byte in b"\1\3":
                    self.__hv.interrupt()
                    break

    def __eval(self, data):
        if self.log:
            self.log(f"eval: {data}")

        if len(data) < 1:
            return b""

        if data[0] in b"?":
            return self.__stop_reply()

        if data[0] in b"c":
            if len(data) != 1:
                self.__cpu(self.__hc)
                self.__hv.ctx.elr = int(data[1:].decode(), 16)

            self.__hv.cont()
            self.__wait_shell()
            return self.__stop_reply()

        if data[0] in b"g":
            self.__cpu(self.__hg)
            g = Container()
            g.regs = self.__hv.ctx.regs.copy()
            g.regs[31] = self.__hv.ctx.sp[1]
            g.pc = self.__hv.ctx.elr
            g.spsr = self.__hv.ctx.spsr.value
            g.q = self.__hv.u.q
            g.fpsr = self.__hv.u.mrs(FPSR)
            g.fpcr = self.__hv.u.mrs(FPCR)

            return bytes(GDBServer.__g.build(g).hex(), "utf-8")

        if data[0] in b"G":
            g = GDBServer.__g.parse(bytes.fromhex(data[1:].decode()))
            self.__cpu(self.__hg)

            for index in range(31):
                self.__hv.ctx.regs[index] = g.regs[index]

            self.__hv.ctx.sp[1] = g.regs[31]
            self.__hv.ctx.elr = g.pc
            self.__hv.ctx.spsr = g.spsr.value

            q = self.__hv.u.q
            for index, value in enumerate(g.q):
                q[index] = value
            self.__hv.u.push_simd()

            self.__hv.u.msr(FPSR, g.fpsr, silent=True)
            self.__hv.u.msr(FPCR, g.fpsr, silent=True)

            return b"OK"

        if data[0] in b"H":
            if len(data) > 1:
                if data[1] in b"c":
                    cpu_id = int(data[2:].decode(), 16)
                    if cpu_id in self.__hv.started_cpus:
                        self.__hc = cpu_id
                        return b"OK"

                    return b"E01"

                if data[1] in b"g":
                    cpu_id = int(data[2:].decode(), 16)
                    if cpu_id in self.__hv.started_cpus:
                        self.__hg = cpu_id
                        return b"OK"

                    return b"E01"

            return b""

        if data[0] in b"krR":
            self.__hv.reboot()

        if data[0] in b"m":
            split = GDBServer.__seperator.split(data[1:].decode(), maxsplit=1)
            fields = [int(field, 16) for field in split]
            return bytes(self.__hv.readmem(fields[0], fields[1]).hex(), "utf-8")

        if data[0] in b"M":
            split = GDBServer.__seperator.split(data[1:].decode(), maxsplit=2)
            mem = bytes.fromhex(split[2])[:int(split[1], 16)]
            if self.__hv.writemem(int(split[0], 16), mem) < len(mem):
                return "E22"

            return b"OK"

        if data[0] in b"p":
            number = int(data[1:].decode(), 16)
            self.__cpu(self.__hg)
            if number < 31:
                reg = GDBServer.__g.regs.subcon.subcon.build(self.__hv.ctx.regs[number])
            elif number == 31:
                reg = GDBServer.__g.regs.subcon.subcon.build(self.__hv.ctx.sp[1])
            elif number == 32:
                reg = GDBServer.__g.pc.build(self.__hv.ctx.elr)
            elif number == 33:
                reg = GDBServer.__g.spsr.build(self.__hv.ctx.spsr.value)
            elif number < 66:
                reg = GDBServer.__g.q.subcon.subcon.build(self.__hv.u.q[number - 34])
            elif number == 66:
                reg = GDBServer.__g.fpsr.build(self.__hv.u.mrs(FPSR))
            elif number == 67:
                reg = GDBServer.__g.fpcr.build(self.__hv.u.mrs(FPCR))
            else:
                return b"E01"

            return bytes(reg.hex(), "utf-8")

        if data[0] in b"P":
            partition = data[1:].partition(b"=")
            number = int(partition[0].decode(), 16)
            reg = bytes.fromhex(partition[2].decode())
            self.__cpu(self.__hg)
            if number < 31:
                self.__hv.ctx.regs[number] = GDBServer.__g.regs.subcon.subcon.unpack(reg)
            elif number == 31:
                self.__hv.ctx.regs[1] = GDBServer.__g.regs.subcon.subcon.unpack(reg)
            elif number == 32:
                self.__hv.ctx.elr = GDBServer.__g.pc.parse(reg)
            elif number == 33:
                self.__hv.ctx.spsr.value = GDBServer.__g.spsr.parse(reg)
            elif number < 66:
                self.__hv.u.q[number - 34] = GDBServer.__g.q.subcon.subcon.parse(reg)
                self.__hv.u.push_simd()
            elif number == 66:
                self.__hv.u.msr(FPSR, GDBServer.__g.fpsr.parse(reg), silent=True)
            elif number == 67:
                self.__hv.u.msr(FPCR, GDBServer.__g.fpcr.parse(reg), silent=True)
            else:
                return b"E01"

            return b"OK"

        if data[0] in b"q":
            split = GDBServer.__seperator.split(data[1:].decode(), maxsplit=1)
            if split[0] == "C":
                cpu_id = self.__hg or self.__hv.ctx.cpu_id
                return b"QC" + bytes(format(cpu_id, "x"), "utf-8")

            if split[0] == "fThreadInfo":
                cpu_ids = b",".join(bytes(format(cpu.cpu_id, "x"), "utf-8") for cpu in self.__hv.adt["cpus"])
                return b"m" + cpu_ids

            if split[0] == "sThreadInfo":
                return b"l"

            if split[0] == "Rcmd":
                self.__cpu(self.__hg)
                self.__hv.run_code(split[1])
                return b"OK"

            if split[0] == "Supported":
                return b"PacketSize=65536;qXfer:features:read+;hwbreak+"

            if split[0] == "ThreadExtraInfo":
                thread_id = int(split[1], 16)
                for node in self.__hv.adt["cpus"]:
                    if node.cpu_id == thread_id:
                        return bytes(bytes(str(node), "utf-8").hex(), "utf-8")

                return b""

            if split[0] == "Xfer":
                xfer = GDBServer.__seperator.split(split[1], maxsplit=4)
                if xfer[0] == "features" and xfer[1] == "read":
                    resource = os.path.join("features", xfer[2])
                    annex = pkgutil.get_data(__name__, resource)
                    if annex is None:
                        return b"E00"

                    request_offset = int(xfer[3], 16)
                    request_len = int(xfer[4], 16)
                    read = annex[request_offset:request_offset + request_len]
                    return (b"l" if len(read) < request_len else b"m") + read

                return b""

            if split[0] == "HostInfo":
                addressing_bits = bytes(str(64 - self.__hv.pac_mask.bit_count()), "utf-8")
                return b"cputype:16777228;cpusubtype:2;endian:little;ptrsize:64;watchpoint_exceptions_received:before;addressing_bits:" + addressing_bits + b";"

            return b""

        if data[0] in b"s":
            self.__cpu(self.__hc)

            if len(data) != 1:
                self.__hv.ctx.elr = int(data[1:].decode(), 16)

            self.__hv.step()
            return self.__stop_reply()

        if data[0] in b"T":
            if int(data[1:].decode(), 16) in self.__hv.started_cpus:
                return b"OK"

            return b"E01"

        if data[0] in b"X":
            partition = data[1:].partition(b":")
            split = GDBServer.__seperator.split(partition[0].decode(), maxsplit=1)
            mem = partition[2][:int(split[1], 16)]
            if self.__hv.writemem(int(split[0], 16), mem) < len(mem):
                return b"E22"

            return b"OK"

        if data[0] in b"z":
            split = GDBServer.__seperator.split(data[1:].decode(), maxsplit=2)
            if split[0] == "1":
                self.__hv.remove_hw_bp(int(split[1], 16))
                return b"OK"

            if split[0] == "2":
                return self.__remove_wp(int(split[1], 16))

            if split[0] == "3":
                return self.__remove_wp(int(split[1], 16))

            if split[0] == "4":
                return self.__remove_wp(int(split[1], 16))

            return b""

        if data[0] in b"Z":
            split = GDBServer.__seperator.split(data[1:].decode(), maxsplit=2)
            if split[0] == "1":
                self.__hv.add_hw_bp(int(split[1], 16))
                return b"OK"

            if split[0] == "2":
                addr = int(split[1], 16)
                kind = int(split[2], 16)
                return self.__add_wp(addr, kind, DBGWCR_LSC.S)

            if split[0] == "3":
                addr = int(split[1], 16)
                kind = int(split[2], 16)
                return self.__add_wp(addr, kind, DBGWCR_LSC.L)

            if split[0] == "4":
                addr = int(split[1], 16)
                kind = int(split[2], 16)
                return self.__add_wp(addr, kind, DBGWCR_LSC.S | DBGWCR_LSC.L)

            return b""

        return b""

    def __send(self, prefix, data):
        with io.BytesIO(prefix) as buffer:
            buffer.write(prefix)

            last = 0
            for index, byte in enumerate(data):
                if not byte in b"#$}*":
                    continue

                buffer.write(data[last:index])
                buffer.write(b"}")
                buffer.write(bytes([byte ^ 0x20]))
                last = index + 1

            buffer.write(data[last:])
            checksum = (sum(buffer.getvalue()) - sum(prefix)) % 256

            buffer.write(b"#")
            buffer.write(bytes(format(checksum, "02x"), "utf-8"))

            value = buffer.getvalue()

            if self.log:
                self.log(f"send: {value}")

            self.__request.send(value)

    def __handle(self, request):
        self.__request = request
        input_buffer = b""

        if not self.__hv.in_shell:
            self.__hv.interrupt()
            self.__wait_shell()

        self.__interrupt_selector.register(self.__request, selectors.EVENT_READ)
        try:
            while True:
                recv = self.__request.recv(65536)
                if not recv:
                    break

                input_buffer += recv

                while True:
                    dollar = input_buffer.find(b"$")
                    if dollar < 0:
                        input_buffer = b""
                        break

                    sharp = input_buffer.find(b"#", dollar)
                    if sharp < 0 or len(input_buffer) < sharp + 3:
                        input_buffer = input_buffer[dollar:]
                        break

                    input_data = input_buffer[dollar + 1:sharp]
                    input_checksum = input_buffer[sharp + 1:sharp + 3]
                    input_buffer = input_buffer[sharp + 3:]

                    try:
                        parsed_input_checksum = int(input_checksum.decode(), 16)
                    except ValueError as error:
                        print(error)
                        continue

                    if (sum(input_data) % 256) != parsed_input_checksum:
                        self.__request.send(b"-")
                        continue

                    self.__request.send(b"+")

                    with io.BytesIO() as input_decoded:
                        input_index = 0
                        input_last = 0
                        while input_index < len(input_data):
                            if input_data[input_index] == b"*":
                                input_decoded.write(input_data[input_last:input_index])
                                instance = input_decoded.getvalue()[-1]
                                input_index += 1
                                input_run_len = input_data[input_index] - 29
                                input_run = bytes([instance]) * input_run_len
                                input_decoded.write(input_run)
                                input_index += 1
                                input_last = input_index
                            elif input_data[input_index] == b"}":
                                input_decoded.write(input_data[input_last:input_index])
                                input_index += 1
                                input_decoded.write(bytes([input_data[input_index] ^ 0x20]))
                                input_index += 1
                                input_last = input_index
                            else:
                                input_index += 1

                        input_decoded.write(input_data[input_last:])

                        try:
                            output_decoded = self.__eval(input_decoded.getvalue())
                        except Exception:
                            output_decoded = b"E." + bytes(traceback.format_exc(), "utf-8")

                    self.__send(b"$", output_decoded)
        finally:
            self.__interrupt_selector.unregister(self.__request)

    def notify_in_shell(self):
        os.eventfd_write(self.__interrupt_eventfd, 1)

    def activate(self):
        try:
            self.__server.server_bind()
        except OSError as error:
            if error.errno != errno.EADDRINUSE:
                raise

            os.remove(self.__server.server_address)
            self.__server.server_bind()

        self.__server.server_activate()
        self.__thread.start()

    def shutdown(self):
        os.close(self.__interrupt_eventfd)
        self.__interrupt_selector.close()
        self.__server.shutdown()
        self.__server.server_close()
        self.__thread.join()

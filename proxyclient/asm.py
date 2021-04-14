#!/usr/bin/env python3

import os, tempfile, shutil, subprocess

class AsmException(Exception):
    pass

class BaseAsm(object):
    def __init__(self, source, addr = 0):
        self.source = source
        self._tmp = tempfile.mkdtemp() + os.sep
        self.addr = addr
        self.compile(source)

    def compile(self, source):
        self.sfile = self._tmp + "b.S"
        with open(self.sfile, "w") as fd:
            fd.write(self.HEADER + "\n")
            fd.write(source + "\n")
            fd.write(self.FOOTER + "\n")

        self.elffile = self._tmp + "b.elf"
        self.bfile = self._tmp + "b.b"
        self.nfile = self._tmp + "b.n"

        subprocess.check_call("%sgcc %s -Ttext=0x%x -o %s %s" % (self.PREFIX, self.CFLAGS, self.addr, self.elffile, self.sfile), shell=True)
        subprocess.check_call("%sobjcopy -j.text -O binary %s %s" % (self.PREFIX, self.elffile, self.bfile), shell=True)
        subprocess.check_call("%snm %s > %s" % (self.PREFIX, self.elffile, self.nfile), shell=True)

        with open(self.bfile, "rb") as fd:
            self.data = fd.read()

        with open(self.nfile) as fd:
            for line in fd:
                line = line.replace("\n", "")
                addr, type, name = line.split()
                addr = int(addr, 16)
                setattr(self, name, addr)
        self.start = self._start
        self.len = len(self.data)
        self.end = self.start + self.len

    def objdump(self):
        subprocess.check_call("%sobjdump -rd %s" % (self.PREFIX, self.elffile), shell=True)

    def __del__(self):
        if self._tmp:
            shutil.rmtree(self._tmp)
            self._tmp = None

class ARMAsm(BaseAsm):
    PREFIX = os.path.join(os.environ.get("ARCH", "aarch64-linux-gnu-"))
    CFLAGS = "-pipe -Wall -nostartfiles -nodefaultlibs -march=armv8.2-a"
    HEADER = """
    .text
    .globl _start
_start:
    """
    FOOTER = """
    .pool
    """

if __name__ == "__main__":
    import sys
    code = """
    ldr x0, =0xDEADBEEF
    b test
    mrs x0, spsel
    svc 1
    %s
test:
    b test
    ret
""" % (" ".join(sys.argv[1:]))
    c = ARMAsm(code, 0x1234)
    c.objdump()
    assert c.start == 0x1234
    assert c.test == 0x1240


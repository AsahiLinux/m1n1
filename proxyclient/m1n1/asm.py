# SPDX-License-Identifier: MIT
import os, tempfile, shutil, subprocess, re
from . import sysreg

__all__ = ["AsmException", "ARMAsm"]

uname = os.uname()

if uname.sysname == "Darwin":
    DEFAULT_ARCH = "aarch64-linux-gnu-"
    if uname.machine == "arm64":
        TOOLCHAIN = "/opt/homebrew/opt/llvm/bin/"
    else:
        TOOLCHAIN = "/usr/local/opt/llvm/bin/"
    USE_CLANG = "1"
else:
    if uname.machine == "aarch64":
        DEFAULT_ARCH = ""
    else:
        DEFAULT_ARCH = "aarch64-linux-gnu-"
    USE_CLANG = "0"
    TOOLCHAIN = ""

use_clang = os.environ.get("USE_CLANG", USE_CLANG).strip() == "1"
toolchain = os.environ.get("TOOLCHAIN", TOOLCHAIN)

if use_clang:
    CC = toolchain + "clang --target=%ARCH"
    LD = toolchain + "ld.lld"
    OBJCOPY = toolchain + "llvm-objcopy"
    OBJDUMP = toolchain + "llvm-objdump"
    NM = toolchain + "llvm-nm"
else:
    CC = toolchain + "%ARCHgcc"
    LD = toolchain + "%ARCHld"
    OBJCOPY = toolchain + "%ARCHobjcopy"
    OBJDUMP = toolchain + "%ARCHobjdump"
    NM = toolchain + "%ARCHnm"

class AsmException(Exception):
    pass

class BaseAsm(object):
    def __init__(self, source, addr = 0):
        self.source = source
        self._tmp = tempfile.mkdtemp() + os.sep
        self.addr = addr
        self.compile(source)

    def _call(self, program, args):
        subprocess.check_call(program.replace("%ARCH", self.ARCH) + " " + args, shell=True)

    def _get(self, program, args):
        return subprocess.check_output(program.replace("%ARCH", self.ARCH) + " " + args, shell=True).decode("ascii")

    def compile(self, source):
        for name, enc in sysreg.sysreg_fwd.items():
            source = re.sub("\\b" + name + "\\b", f"s{enc[0]}_{enc[1]}_c{enc[2]}_c{enc[3]}_{enc[4]}", source)

        self.sfile = self._tmp + "b.S"
        with open(self.sfile, "w") as fd:
            fd.write(self.HEADER + "\n")
            fd.write(source + "\n")
            fd.write(self.FOOTER + "\n")

        self.ofile = self._tmp + "b.o"
        self.elffile = self._tmp + "b.elf"
        self.bfile = self._tmp + "b.b"
        self.nfile = self._tmp + "b.n"

        self._call(CC, f"{self.CFLAGS} -c -o {self.ofile} {self.sfile}")
        self._call(LD, f"{self.LDFLAGS} --Ttext={self.addr:#x} -o {self.elffile} {self.ofile}")
        self._call(OBJCOPY, f"-j.text -O binary {self.elffile} {self.bfile}")
        self._call(NM, f"{self.elffile} > {self.nfile}")

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
        self._call(OBJDUMP, f"-rd {self.elffile}")

    def disassemble(self):
        output = self._get(OBJDUMP, f"-zd {self.elffile}")

        for line in output.split("\n"):
            if not line or line.startswith("/"):
                continue
            sl = line.split()
            if not sl or sl[0][-1] != ":":
                continue
            yield line

    def __del__(self):
        if self._tmp:
            shutil.rmtree(self._tmp)
            self._tmp = None

class ARMAsm(BaseAsm):
    ARCH = os.path.join(os.environ.get("ARCH", DEFAULT_ARCH))
    CFLAGS = "-pipe -Wall -march=armv8.4-a"
    LDFLAGS = "-maarch64elf"
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
    c = ARMAsm(code, 0x1238)
    c.objdump()
    assert c.start == 0x1238
    if not sys.argv[1:]:
        assert c.test == 0x1248

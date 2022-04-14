# SPDX-License-Identifier: MIT
from contextlib import contextmanager, ExitStack
import sys, pathlib, os
import subprocess
import tempfile
import bisect

from .asm import NM, LD, OBJCOPY, ARMAsm

__all__ = ["LinkedProgram"]


def tool_output_lines(progname, *args):
    with subprocess.Popen([progname.replace("%ARCH", ARMAsm.ARCH)] + list(args),
            stdout=subprocess.PIPE) as proc:
        for line in proc.stdout:
            yield line.decode("ascii")
        proc.wait()
        if proc.returncode:
            raise Exception(f"{progname} (args: {args}) exited with status {proc.returncode}")

def run_tool(progname, *args, silent=False):
    subprocess.check_call([progname.replace("%ARCH", ARMAsm.ARCH)] + list(args),
                        stdout=subprocess.DEVNULL if silent else None)


class LinkedProgram:
    SOURCE_ROOT = str(pathlib.Path(__file__).resolve().parents[2])

    def __init__(self, u, base_object=None):
        self.u = u
        self.symbols = []
        self.symaddrs = dict()
        self.base_object = base_object
        self._alloced_bases = []
        self._attrs_to_clear = []
        self._load_base_symbols()

    def _load_base_symbols(self):
        if self.base_object is None:
            suffix = "-raw" if not self.m1n1_is_macho() else ""
            self.base_object = f"build/m1n1{suffix}.elf"

        addrs = self._load_elf_symbols(self.base_object, self.u.proxy.get_base())

        # sanity check: compare the .rela table between ELF and m1n1 image on target
        rela_base = addrs["_rela_start"]
        rela_length = addrs["_rela_end"] - rela_base
        rela_target = self.u.iface.readmem(rela_base, rela_length)

        tmp = os.path.join(tempfile.mkdtemp(), "bin")
        path = os.path.join(self.SOURCE_ROOT, self.base_object)
        run_tool(OBJCOPY, "-O", "binary", path, tmp, "--only-section=.rela.dyn")
        rela_objfile = open(tmp, "rb").read()

        if rela_objfile[:len(rela_target)] != rela_target:
            raise Exception(f"Mismatch between {self.base_object} and image on target")

    def m1n1_is_macho(self):
        p = self.u.proxy
        return p.read32(p.get_base()) == 0xfeedfacf

    def _load_elf_symbols(self, relpath, offset=0,
                            objname=None, ignore=""):
        path = pathlib.Path(self.SOURCE_ROOT, relpath)
        symaddrs = dict()

        for line in tool_output_lines(NM, "-g", path):
            addr_str, t, name = line.split()
            addr = int(addr_str, 16) + offset
            if t in ignore:
                continue
            self.symbols.append((addr, name, objname))
            symaddrs[name] = addr
            if t in "T" and not hasattr(self, name):
                setattr(self, name, self._wrap_call_to(addr))
                if relpath != self.base_object:
                    self._attrs_to_clear.append(name)
        self.symbols.sort()
        return symaddrs

    def load_obj(self, objfile, base=None):
        ALLOC_SIZE = 16*4096

        if base is None:
            base = self.u.heap.memalign(0x4000, ALLOC_SIZE)
            self._alloced_bases.append(base)

        objfile = os.path.join(self.SOURCE_ROOT, objfile)
        tmp = tempfile.mkdtemp() + os.sep
        elffile = tmp + "elf"
        ld_script = tmp + "ld"
        binfile = tmp + "bin"
        with open(ld_script, "w") as f:
            f.write("SECTIONS {\n")
            f.write(f". = 0x{base:x};\n")
            f.write(".text : { *(.text .text.*) }\n")
            f.write(".data : { *(.got .data .data.* .rodata .rodata.* .bss .bss.*) }\n")
            f.write("}\n")
            for sym in self.symbols:
                f.write(f"{sym[1]} = 0x{sym[0]:x};\n")
        run_tool(LD, "-EL", "-maarch64elf", "-T", ld_script, "-o", elffile, objfile)
        run_tool(OBJCOPY, "-O", "binary", elffile, binfile)
        #run_tool("objdump", "-d", elffile)
        self._load_elf_symbols(elffile, ignore="A")
        with open(binfile, "rb") as f:
            buf = f.read()
            assert len(buf) <= ALLOC_SIZE
            self.u.iface.writemem(base, buf)
            self.u.proxy.dc_cvau(base, len(buf))
            self.u.proxy.ic_ivau(base, len(buf))

    def clear_objs(self):
        for name in self._attrs_to_clear:
            delattr(self, name)
        self._attrs_to_clear = []

        for base in self._alloced_bases:
            self.u.free(base)
        self._alloced_bases = []

        self.symbols = [(a, b, objname) for (a, b, objname) \
                        in self.symbols if objname == self.base_object]

    @contextmanager
    def _copy_args_to_target(self, args):
        heap = self.u.heap
        with ExitStack() as stack:
            args_copied = []
            for arg in args:
                if type(arg) is str:
                    arg = arg.encode("ascii")
                    # fallthrough
                if type(arg) is bytes:
                    p = stack.enter_context(heap.guarded_malloc(len(arg) + 1))
                    self.u.iface.writemem(p, arg + b"\0")
                    args_copied.append(p)
                elif type(arg) is int:
                    args_copied.append(arg)
                else:
                    raise NotImplementedError(type(arg))
            yield args_copied

    def _wrap_call_to(self, addr):
        def call_symbol(*args, call=self.u.proxy.call):
            with self._copy_args_to_target(args) as args_copied:
                return call(addr, *args_copied)
        return call_symbol

    def lookup(self, addr):
        idx = bisect.bisect_left(self.symbols, (addr + 1, "", "")) - 1
        if idx < 0 or idx >= len(self.symbols):
            return None, None
        return self.symbols[idx]

    def load_inline_c(self, source):
        tmp = tempfile.mkdtemp()
        cfile = tmp + ".c"
        objfile = tmp + ".o"
        with open(cfile, "w") as f:
            f.write(source)
        run_tool("make", "-C", self.SOURCE_ROOT, "invoke_cc",
                 f"OBJFILE={objfile}", f"CFILE={cfile}", silent=True)
        self.load_obj(objfile)


if __name__ == "__main__":
    from m1n1.setup import *
    lp = LinkedProgram(u)
    lp.debug_printf("hello from the other side! (%d)\n", 42)
    lp.load_inline_c('''
        #include "utils.h"
        int add(int a, int b) {
            debug_printf("adding %d and %d\\n", a, b);
            return a + b;
        }
    ''')
    print(f"1 + 2 = {lp.add(1, 2)}")

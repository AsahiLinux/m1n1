# SPDX-License-Identifier: MIT
"""m1n1 tests common fixtures"""

import pytest

from proxyclient.m1n1.asm import ARMAsm
from proxyclient.m1n1.toolchain import Toolchain

CODE_LOCATION = 0x1238

INPUT_CODE = """
    ldr x0, =0xDEADBEEF
    b test
    mrs x0, spsel
    svc 1
test:
    b test
    ret
"""

OBJDUMP_OUTPUT_CLANG = """
/tmp/b.elf:\tfile format elf64-littleaarch64

Disassembly of section .text:

0000000000001238 <_start>:
    1238: 580000c0     \tldr\tx0, 0x1250 <test+0x8>
    123c: 14000003     \tb\t0x1248 <test>
    1240: d5384200     \tmrs\tx0, SPSel
    1244: d4000021     \tsvc\t#0x1

0000000000001248 <test>:
    1248: 14000000     \tb\t0x1248 <test>
    124c: d65f03c0     \tret
    1250: ef be ad de  \t.word\t0xdeadbeef
    1254: 00 00 00 00  \t.word\t0x00000000
"""

NM_OUTPUT_CLANG = "0000000000001238 T _start\n"

NM_ERROR_CLANG = " error: a.out: No such file or directory\n"

OBJDUMP_OUTPUT_GCC = """
/tmp/b.elf:     file format elf64-littleaarch64


Disassembly of section .text:

0000000000001238 <_start>:
    1238:\t580000c0 \tldr\tx0, 1250 <test+0x8>
    123c:\t14000003 \tb\t1248 <test>
    1240:\td5384200 \tmrs\tx0, spsel
    1244:\td4000021 \tsvc\t#0x1

0000000000001248 <test>:
    1248:\t14000000 \tb\t1248 <test>
    124c:\td65f03c0 \tret
    1250:\tdeadbeef \t.word\t0xdeadbeef
    1254:\t00000000 \t.word\t0x00000000
"""

NM_OUTPUT_GCC = """0000000000011258 T __bss_end__
0000000000011258 T __bss_start
0000000000011258 T __bss_start__
0000000000011258 T __end__
0000000000011258 T _bss_end__
0000000000011258 T _edata
0000000000011258 T _end
0000000000001238 T _start
"""

NM_ERROR_GCC = " 'a.out': No such file\n"

@pytest.fixture
def fx_asm_object_start():
    """Return start location address"""
    return CODE_LOCATION


@pytest.fixture
def fx_asm_object():
    """Return ARMAsm object instance"""
    return ARMAsm(INPUT_CODE, CODE_LOCATION)


@pytest.fixture
def fx_asm_object_disasm():
    """Return disassembly of object"""
    return {
        "clang": OBJDUMP_OUTPUT_CLANG,
        "gcc": OBJDUMP_OUTPUT_GCC,
    }


@pytest.fixture
def fx_loadobjs_nm_output():
    """Return expected NM output"""
    return {
        "clang": NM_OUTPUT_CLANG,
        "gcc": NM_OUTPUT_GCC,
    }


@pytest.fixture
def fx_loadobjs_nm_error():
    """Return expected NM error message"""
    return {
        "clang": NM_ERROR_CLANG,
        "gcc": NM_ERROR_GCC,
    }

@pytest.fixture
def fx_toolchain():
    """Return toolchain"""
    return Toolchain()

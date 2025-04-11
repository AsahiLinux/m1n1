""" "m1n1 tests common fixtures"""

import importlib

import pytest

from proxyclient.m1n1.asm import ARMAsm

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

OBJDUMP_OUTPUT = """
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
    return OBJDUMP_OUTPUT


@pytest.fixture
def fx_toolchain():
    """Return toolchain"""
    return importlib.import_module("proxyclient.m1n1.asm")

# SPDX-License-Identifier: MIT
"""Tests for proxyclient/m1n1/asm.py"""

import re

class TestArmAsm:
    """proxyclient.m1n1.ARMAsm tests"""

    def test_compile(self, fx_asm_object, fx_asm_object_start):
        """Test basic compilation"""
        assert fx_asm_object.start == fx_asm_object_start

    def test_objdump(self, capfd, fx_asm_object,fx_asm_object_disasm):
        """Test object dump"""
        fx_asm_object.objdump()
        out, _ = capfd.readouterr()
        out = re.sub(r"/.*/b.elf:", "/tmp/b.elf:", out, count=1)
        assert out == fx_asm_object_disasm

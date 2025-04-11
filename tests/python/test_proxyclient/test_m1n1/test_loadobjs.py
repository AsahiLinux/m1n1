# SPDX-License-Identifier: MIT
"""Tests for proxyclient/m1n1/loadobjs.py"""

import pytest

from proxyclient.m1n1.loadobjs import run_tool
from proxyclient.m1n1.loadobjs import tool_output_lines


# pylint: disable=redefined-outer-name
def test_tool_output_lines(fx_toolchain, fx_asm_object):
    """ "Test nm tool"""
    lines = list(
        line for line in tool_output_lines(fx_toolchain.NM, "-g", fx_asm_object.elffile)
    )
    assert lines == ["0000000000001238 T _start\n"]


def test_tool_output_lines_exception(capfd: pytest.CaptureFixture[str], fx_toolchain):
    """ "Test nm tool"""
    with pytest.raises(Exception, match=r".*nm \(args: \(\)\) exited with status 1$"):
        list(line for line in tool_output_lines(fx_toolchain.NM))
    _, err = capfd.readouterr()
    error_message = err.split(":", 1)[1]
    assert error_message == " error: a.out: No such file or directory\n"


def test_run_tool(capfd: pytest.CaptureFixture[str], fx_toolchain, fx_asm_object):
    """ "Test nm tool"""
    run_tool(fx_toolchain.NM, "-g", fx_asm_object.elffile)
    out, _ = capfd.readouterr()
    assert out == "0000000000001238 T _start\n"


def test_run_tool_silent(
    capfd: pytest.CaptureFixture[str], fx_toolchain, fx_asm_object
):
    """ "Test nm tool"""
    run_tool(fx_toolchain.NM, "-g", fx_asm_object.elffile, silent=True)
    out, _ = capfd.readouterr()
    assert out == ""

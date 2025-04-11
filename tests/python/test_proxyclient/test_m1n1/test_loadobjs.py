# SPDX-License-Identifier: MIT
"""Tests for proxyclient/m1n1/loadobjs.py"""

import pytest

from proxyclient.m1n1.loadobjs import run_tool
from proxyclient.m1n1.loadobjs import tool_output_lines


# pylint: disable=redefined-outer-name
def test_tool_output_lines(fx_toolchain, fx_asm_object, fx_loadobjs_nm_output):
    """Test nm tool"""
    output = "".join(
        tool_output_lines(fx_toolchain.NM, "-g", fx_asm_object.elffile)
    )
    if fx_toolchain.use_clang:
        assert output == fx_loadobjs_nm_output["clang"]
    else:
        assert output == fx_loadobjs_nm_output["gcc"]


def test_tool_output_lines_exception(capfd: pytest.CaptureFixture[str], fx_toolchain, fx_loadobjs_nm_error):
    """Test nm tool"""
    with pytest.raises(Exception, match=r".*nm \(args: \(\)\) exited with status 1$"):
        list(line for line in tool_output_lines(fx_toolchain.NM))
    _, err = capfd.readouterr()
    error_message = err.split(":", 1)[1]
    if fx_toolchain.use_clang:
        assert error_message == fx_loadobjs_nm_error["clang"]
    else:
        assert error_message == fx_loadobjs_nm_error["gcc"]


def test_run_tool(capfd: pytest.CaptureFixture[str], fx_toolchain, fx_asm_object, fx_loadobjs_nm_output):
    """Test nm tool"""
    run_tool(fx_toolchain.NM, "-g", fx_asm_object.elffile)
    output, _ = capfd.readouterr()
    if fx_toolchain.use_clang:
        assert output == fx_loadobjs_nm_output["clang"]
    else:
        assert output == fx_loadobjs_nm_output["gcc"]

def test_run_tool_silent(
    capfd: pytest.CaptureFixture[str], fx_toolchain, fx_asm_object
):
    """Test nm tool"""
    run_tool(fx_toolchain.NM, "-g", fx_asm_object.elffile, silent=True)
    output, _ = capfd.readouterr()
    assert output == ""

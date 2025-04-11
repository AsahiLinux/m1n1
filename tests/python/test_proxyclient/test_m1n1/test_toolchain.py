# SPDX-License-Identifier: MIT
"""Tests for proxyclient/m1n1/toolchain.py"""

import os
import shutil

from posix import uname_result

import pytest

from proxyclient.m1n1.toolchain import LLVMResolver
from proxyclient.m1n1.toolchain import BrewLLVMResolver
from proxyclient.m1n1.toolchain import Toolchain


class TestLLVMResolver:
    """proxyclient.m1n1.LLVMResolver tests"""

    # pylint: disable=too-few-public-methods

    def test_get_paths(self):
        """Check path after default constructor"""
        r = LLVMResolver()
        assert r.get_paths() == (None, None)


class TestBrewLLVMResolver:
    """proxyclient.m1n1.BrewLLVMResolver tests"""

    # pylint: disable=too-few-public-methods

    def test_constructor(self):
        """Check default constructor"""

        if shutil.which("brew") is None:
            pytest.skip("This system does not have `brew` installed")

        r = BrewLLVMResolver()
        assert r


class TestToolchain:
    """proxyclient.m1n1.Toolchain class tests"""

    # pylint: disable=too-few-public-methods

    @pytest.mark.parametrize(
        # pylint: disable=line-too-long
        "sysname,machine,expected",
        [
            (
                "Darwin",
                "arm64",
                {
                    "use_clang": True,
                    "has_brew": True,
                    "CC": "/opt/homebrew/opt/llvm/bin/clang --target=aarch64-linux-gnu- -pipe -Wall -march=armv8.4-a",
                    "LD": "/opt/homebrew/opt/lld/bin/ld.lld -maarch64elf",
                    "OBJCOPY": "/opt/homebrew/opt/llvm/bin/llvm-objcopy",
                    "OBJDUMP": "/opt/homebrew/opt/llvm/bin/llvm-objdump",
                    "NM": "/opt/homebrew/opt/llvm/bin/llvm-nm",
                    "CFLAGS": "-pipe -Wall -march=armv8.4-a",
                    "ARCH": "aarch64-linux-gnu-",
                },
            ),
            (
                "Linux",
                "x86_64",
                {
                    "use_clang": False,
                    "has_brew": False,
                    "CC": "aarch64-linux-gnu-gcc -pipe -Wall -march=armv8.4-a",
                    "LD": "aarch64-linux-gnu-ld -maarch64linux",
                    "OBJCOPY": "aarch64-linux-gnu-objcopy",
                    "OBJDUMP": "aarch64-linux-gnu-objdump",
                    "NM": "aarch64-linux-gnu-nm",
                    "CFLAGS": "-pipe -Wall -march=armv8.4-a",
                    "ARCH": "aarch64-linux-gnu-",
                },
            ),
            (
                "Linux",
                "aarch64",
                {
                    "use_clang": False,
                    "has_brew": False,
                    "CC": "gcc -pipe -Wall -march=armv8.4-a",
                    "LD": "ld -maarch64linux",
                    "OBJCOPY": "objcopy",
                    "OBJDUMP": "objdump",
                    "NM": "nm",
                    "CFLAGS": "-pipe -Wall -march=armv8.4-a",
                    "ARCH": "",
                },
            ),
            (
                "Darwin",
                "x86_64",
                {
                    "use_clang": True,
                    "has_brew": True,
                    "CC": "/usr/local/opt/llvm/bin/clang --target=aarch64-linux-gnu- -pipe -Wall -march=armv8.4-a",
                    "LD": "/usr/local/opt/lld/bin/ld.lld -maarch64elf",
                    "OBJCOPY": "/usr/local/opt/llvm/bin/llvm-objcopy",
                    "OBJDUMP": "/usr/local/opt/llvm/bin/llvm-objdump",
                    "NM": "/usr/local/opt/llvm/bin/llvm-nm",
                    "CFLAGS": "-pipe -Wall -march=armv8.4-a",
                    "ARCH": "aarch64-linux-gnu-",
                },
            ),
            (
                "OpenBSD",
                "arm64",
                {
                    "use_clang": True,
                    "has_brew": False,
                    "CC": "/usr/local/bin/clang --target=aarch64-none-elf- -pipe -Wall -march=armv8.4-a",
                    "LD": "/usr/local/bin/ld.lld -maarch64elf",
                    "OBJCOPY": "/usr/local/bin/llvm-objcopy",
                    "OBJDUMP": "/usr/local/bin/llvm-objdump",
                    "NM": "/usr/local/bin/llvm-nm",
                    "CFLAGS": "-pipe -Wall -march=armv8.4-a",
                    "ARCH": "aarch64-none-elf-",
                },
            ),
            (
                "OpenBSD",
                "amd64",
                {
                    "use_clang": True,
                    "has_brew": False,
                    "CC": "/usr/local/bin/clang --target=aarch64-none-elf- -pipe -Wall -march=armv8.4-a",
                    "LD": "/usr/local/bin/ld.lld -maarch64elf",
                    "OBJCOPY": "/usr/local/bin/llvm-objcopy",
                    "OBJDUMP": "/usr/local/bin/llvm-objdump",
                    "NM": "/usr/local/bin/llvm-nm",
                    "CFLAGS": "-pipe -Wall -march=armv8.4-a",
                    "ARCH": "aarch64-none-elf-",
                },
            ),
        ],
    )
    def test_toolchain(
        self,
        sysname: str,
        machine: str,
        expected: dict,
    ):
        """Test toolchain for various combinations of uname values"""

        u = uname_result([sysname, None, None, None, machine])
        expected["uname"] = u
        host = os.uname()

        if host.sysname != u.sysname or host.machine != u.machine:
            pytest.skip(
                f"host does not match intended OS or architecture: "
                f"expected ({u.sysname}, {u.machine}) got ({host.sysname}, {host.machine})"
            )

        if os.environ.get("USE_CLANG", default="0") == "1" and expected["use_clang"] is False:
            pytest.skip("USE_CLANG is set while fixture targets LLVM")

        toolchain = Toolchain(u)
        assert vars(toolchain) == expected

# SPDX-License-Identifier: MIT
"""
m1n1: toolchain abstraction for compiling code on proxyclient host
"""

import os
import shutil
import subprocess

from dataclasses import dataclass

from posix import uname_result


__all__ = ["Toolchain"]

DEFAULT_TOOLCHAIN_PREFIX_OTHER = ""
DEFAULT_TOOLCHAIN_PREFIX_OPENBSD = "/usr/local/bin/"
DEFAULT_CFLAGS = "-pipe -Wall -march=armv8.4-a"


class LLVMResolver:
    """
    Class to resolve toolchain prefixes
    """

    # pylint: disable=too-few-public-methods

    def __init__(self):
        self.clangdir = None
        self.llddir = None

    def get_paths(self):
        """Return LLVM paths tuple"""
        _t = (self.clangdir, self.llddir)
        return _t


class BrewLLVMResolver(LLVMResolver):
    """
    Class to resolve toolchain prefixes on brewed system
    """

    # pylint: disable=too-few-public-methods

    def __init__(self):
        super().__init__()
        result = subprocess.run(
            "brew --prefix llvm".split(),
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        llvm_prefix = result.stdout.strip()
        self.clangdir = llvm_prefix + "/bin/"

        result = subprocess.run(
            "brew --prefix lld".split(),
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        lld_prefix = result.stdout.strip() if (result.returncode == 0) else None
        self.llddir = lld_prefix + "/bin/" if lld_prefix else None


_brew_path = shutil.which("brew")

_llvm_resolver = LLVMResolver()
if bool(_brew_path):
    _llvm_resolver = BrewLLVMResolver()


@dataclass
class Toolchain:
    """
    Class representing host's toolchain.
    """

    # pylint: disable=too-many-instance-attributes

    uname: uname_result
    use_clang: bool
    has_brew: bool
    # pylint: disable=invalid-name
    CC: str
    LD: str
    OBJCOPY: str
    OBJDUMP: str
    NM: str
    CFLAGS: str
    ARCH: str
    # pylint: enable=invalid-name

    def __init__(self, u: uname_result = os.uname(), r: LLVMResolver = _llvm_resolver):

        self.uname = u

        if u.sysname == "OpenBSD":
            default_arch = "aarch64-none-elf-"
        elif u.sysname in ["Darwin", "Linux"] and u.machine != "aarch64":
            default_arch = "aarch64-linux-gnu-"
        else:
            default_arch = ""

        if u.sysname in ["OpenBSD", "Darwin"]:
            default_use_clang = "1"
        else:
            default_use_clang = "0"

        # pylint: disable=invalid-name
        self.CFLAGS = DEFAULT_CFLAGS
        self.ARCH = os.path.join(os.environ.get("ARCH", default_arch))
        # pylint: enable=invalid-name
        self.use_clang = bool(
            os.environ.get("USE_CLANG", default_use_clang).strip() == "1"
        )
        self.has_brew = bool(_brew_path)

        toolchain_paths = ()

        if u.sysname == "Darwin":
            toolchain_paths = r.get_paths()
        elif u.sysname == "OpenBSD":
            toolchain_paths = (DEFAULT_TOOLCHAIN_PREFIX_OPENBSD, None)
        else:
            toolchain_paths = (DEFAULT_TOOLCHAIN_PREFIX_OTHER, None)

        if toolchain := os.environ.get("TOOLCHAIN", ""):
            toolchain_paths = (toolchain, None)

        if self.use_clang:
            if llddir := os.environ.get("LLDDIR", ""):
                toolchain_paths = (toolchain_paths[0], llddir)
            self._set_tools_clang(*toolchain_paths)
        else:
            self._set_tools(*toolchain_paths)

    def _set_tools_clang(self, clangdir: str, llddir: str = None):

        if llddir is None:
            llddir = clangdir

        # pylint: disable=invalid-name
        self.CC = clangdir + "clang --target=" + self.ARCH + " " + self.CFLAGS
        self.LD = llddir + "ld.lld -maarch64elf"
        self.OBJCOPY = clangdir + "llvm-objcopy"
        self.OBJDUMP = clangdir + "llvm-objdump"
        self.NM = clangdir + "llvm-nm"

    def _set_tools(self, toolchain: str, _):

        _exe_prefix = toolchain + self.ARCH
        self.CC = _exe_prefix + "gcc" + " " + self.CFLAGS
        self.LD = _exe_prefix + "ld -maarch64linux"
        self.OBJCOPY = _exe_prefix + "objcopy"
        self.OBJDUMP = _exe_prefix + "objdump"
        self.NM = _exe_prefix + "nm"


if __name__ == "__main__":
    from pprint import pprint

    pprint(Toolchain())

import os, shutil, subprocess

from posix import uname_result

__all__ = ["Toolchain"]

DEFAULT_TOOLCHAIN_EMPTY = ""
DEFAULT_TOOLCHAIN_OPENBSD = "/usr/local/bin/"
DEFAULT_CFLAGS = "-pipe -Wall -march=armv8.4-a"

match os.uname():
    case uname_result(sysname="OpenBSD"):
        DEFAULT_ARCH = "aarch64-none-elf-"
    case uname_result(sysname="Darwin") | uname_result(sysname="Linux") as u if u.machine != "aarch64":
        DEFAULT_ARCH = "aarch64-linux-gnu-"
    case _:
        DEFAULT_ARCH = ""

match os.uname():
    case uname_result(sysname="OpenBSD") | uname_result(sysname="Darwin"):
        DEFAULT_USE_CLANG = "1"
    case _:
        DEFAULT_USE_CLANG = "0"

class Toolchain(object):


    __repr_fields  = ["use_clang", "has_brew", "CC", "LD", "OBJCOPY", "OBJDUMP", "NM", "CFLAGS", "ARCH"]

    def __repr__(self):
         return f"{type(self).__name__}({', '.join(f'{f}={getattr(self, f)}' for f in self.__repr_fields)})"

    def __init__(self):

        self.CFLAGS = DEFAULT_CFLAGS
        self.ARCH = os.path.join(os.environ.get("ARCH", DEFAULT_ARCH))
        self.use_clang = os.environ.get("USE_CLANG", DEFAULT_USE_CLANG).strip() == "1"
        self.has_brew = shutil.which("brew")

        toolchain_paths = ()

        match os.uname():
            case uname_result(sysname="Darwin"):
                toolchain_paths = self._macos_paths()
            case uname_result(sysname="OpenBSD"):
                toolchain_paths = (DEFAULT_TOOLCHAIN_OPENBSD)
            case _:
                toolchain_paths = (DEFAULT_TOOLCHAIN_EMPTY)

        toolchain = os.environ.get("TOOLCHAIN", "")
        if toolchain:
            toolchain_paths = (toolchain)
        llddir = os.environ.get("LLDDIR", None)
        if llddir:
            toolchain_paths = (toolchain_paths[0], llddir)

        if self.use_clang:
            self._set_tools_clang(*toolchain_paths)
        else:
            self._set_tools(*toolchain_paths)

    def _set_tools_clang(self, clangdir: str, llddir: str = None):

        if llddir is None:
            llddir = clangdir

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

    def _macos_paths(self):

        if not self.has_brew:
            return ("")

        result = subprocess.run("brew --prefix llvm".split(), capture_output=True, text=True, check=True, timeout=2)
        llvm_prefix = result.stdout.strip()
        clangdir = llvm_prefix + "/bin/"
        result = subprocess.run("brew --prefix lld".split(), capture_output=True, text=True, timeout=2)
        lld_prefix = result.stdout.strip() if (result.returncode == 0) else None
        llddir = lld_prefix + "/bin/" if lld_prefix else None
        return (clangdir, llddir)

if __name__ == "__main__":
    from pprint import pprint

    toolchain = Toolchain()
    pprint(toolchain)

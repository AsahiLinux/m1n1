# SPDX-License-Identifier: MIT
from pathlib import Path
import os

class KernelRegmapAccessor:
    def __init__(self, name):
        self.path = self._find_path(name)
        self.read_ranges()
        self.read_linelen()

    @classmethod
    def _find_path(cls, name):
        basedir = Path("/sys/kernel/debug/regmap")

        if (path := Path(name)).exists():
            return path
        elif (path := basedir.joinpath(name)).exists():
            return path
        elif name in (available := cls._list_regmaps(basedir)):
            return available[name]
        else:
            raise ValueError(f"kernel regmap not found: {name}")

    @classmethod
    def _list_regmaps(cls, basedir):
        return {
            p.joinpath("name").open("rb").read().strip().decode(): p
            for p in basedir.iterdir() if p.is_dir()
        }

    def open_node(self, name, mode="rb", **kwargs):
        return self.path.joinpath(name).open(mode, **kwargs)

    def read_ranges(self):
        with self.open_node("range") as f:
            self.ranges = [
                range(int(a, 16), int(b, 16) + 1)
                for a, b in (l.strip().split(b"-") for l in f)
            ]

    def read_linelen(self):
        with self.open_node("registers", buffering=0) as f:
            l = f.read(64).split(b"\n")[0]
            valstr = l.split(b":")[1].strip()
            self.linelen = len(l) + 1
            self.working_width = len(valstr) * 4

    def _find_off(self, reg):
        off = 0
        for r in self.ranges:
            if reg >= r.stop:
                off += r.stop - r.start
            else:
                off += reg - r.start
                break
        if reg not in r:
            raise ValueError(f"register {reg:04x} out of range")
        return off * self.linelen

    def _read(self, reg, width=None):
        assert width == self.working_width
        with self.open_node("registers", buffering=0) as f:
            f.seek(self._find_off(reg))
            l = f.read(self.linelen)
            regstr, valstr = l.split(b":")
            assert int(regstr, 16) == reg
            return int(valstr, 16)

    def read(self, reg, width=None):
        assert width % self.working_width == 0
        ret = 0
        for off in range(0, width // 8, self.working_width // 8):
            ret |= self._read(reg + off, self.working_width) << (8 * off)
        return ret

    def _write(self, reg, val, width=None):
        assert width == self.working_width
        with self.open_node("registers", mode="wb") as f:
            f.write(f"{reg:x} {val:x}".encode())

    def write(self, reg, val, width=None):
        assert width % self.working_width == 0
        for off in range(0, width // 8, self.working_width // 8):
            self._write(reg + off, val >> (8 * off), self.working_width)

def require_debugfs():
    if os.path.ismount("/sys/kernel/debug"):
        return
    os.system("mount -t debugfs none /sys/kernel/debug")

if __name__ == "__main__":
    require_debugfs()
    from m1n1.hw.codecs import TAS5770Regs
    tas = TAS5770Regs(KernelRegmapAccessor("tas2770"), 0)
    import code
    code.interact(local=locals())

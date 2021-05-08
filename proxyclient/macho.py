#!/usr/bin/env python3

from tgtypes import *
from utils import *

class MachO:
    def __init__(self, data):
        self.data = data
        self.obj = MachOFile.parse(data)
        self.load_info()

    def load_info(self):
        self.vmin, self.vmax = (1 << 64), 0
        self.entry = None
        for cmd in self.obj.cmds:
            if cmd.cmd == MachOLoadCmdType.SEGMENT_64:
                self.vmin = min(self.vmin, cmd.args.vmaddr)
                self.vmax = max(self.vmax, cmd.args.vmaddr + cmd.args.vmsize)
            elif cmd.cmd == MachOLoadCmdType.UNIXTHREAD:
                self.entry = cmd.args[0].data.pc

    def prepare_image(self, load_hook=None):
        memory_size = self.vmax - self.vmin

        image = bytearray(memory_size)

        for cmdi, cmd in enumerate(self.obj.cmds):
            is_m1n1 = None
            if cmd.cmd == MachOLoadCmdType.SEGMENT_64:
                if is_m1n1 is None:
                    is_m1n1 = cmd.args.segname == "_HDR"
                dest = cmd.args.vmaddr - self.vmin
                end = min(len(self.data), cmd.args.fileoff + cmd.args.filesize)
                size = end - cmd.args.fileoff
                print(f"LOAD: {cmd.args.segname} {size} bytes from {cmd.args.fileoff:x} to {dest:x}")
                data = self.data[cmd.args.fileoff:end]
                if load_hook is not None:
                    data = load_hook(data, cmd.args.segname, size, cmd.args.fileoff, dest)
                image[dest:dest + size] = data
                if cmd.args.vmsize > size:
                    clearsize = cmd.args.vmsize - size
                    if cmd.args.segname == "PYLD":
                        print("SKIP: %d bytes from 0x%x to 0x%x" % (clearsize, dest + size, dest + size + clearsize))
                        memory_size -= clearsize - 4 # leave a payload end marker
                        image = image[:memory_size]
                    else:
                        print("ZERO: %d bytes from 0x%x to 0x%x" % (clearsize, dest + size, dest + size + clearsize))
                        image[dest + size:dest + cmd.args.vmsize] = bytes(clearsize)

        return image

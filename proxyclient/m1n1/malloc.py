# SPDX-License-Identifier: MIT
from contextlib import contextmanager

__all__ = ["Heap"]

class Heap(object):
    def __init__(self, start, end, block=64):
        if start%block:
            raise ValueError("heap start not aligned")
        if end%block:
            raise ValueError("heap end not aligned")
        self.offset = start
        self.count = (end - start) // block
        self.blocks = [(self.count,False)]
        self.block = block

    def malloc(self, size):
        size = (size + self.block - 1) // self.block
        pos = 0
        for i, (bsize, full) in enumerate(self.blocks):
            if not full and bsize >= size:
                self.blocks[i] = (size, True)
                if bsize > size:
                    self.blocks.insert(i+1, (bsize - size, False))
                return self.offset + self.block * pos
            pos += bsize
        raise Exception("Out of memory")

    def memalign(self, align, size):
        assert (align & (align - 1)) == 0
        align = max(align, self.block) // self.block
        size = (size + self.block - 1) // self.block
        pos = self.offset // self.block
        for i, (bsize, full) in enumerate(self.blocks):
            if not full:
                offset = 0
                if pos % align:
                    offset = align - (pos % align)
                if bsize >= (size + offset):
                    if offset:
                        self.blocks.insert(i, (offset, False))
                        i += 1
                    self.blocks[i] = (size, True)
                    if bsize > (size + offset):
                        self.blocks.insert(i+1, (bsize - size - offset, False))
                    return self.block * (pos + offset)
            pos += bsize
        raise Exception("Out of memory")

    def free(self, addr):
        if addr%self.block:
            raise ValueError("free address not aligned")
        if addr<self.offset:
            raise ValueError("free address before heap")
        addr -= self.offset
        addr //= self.block
        if addr>=self.count:
            raise ValueError("free address after heap")
        pos = 0
        for i, (bsize, used) in enumerate(self.blocks):
            if pos > addr:
                raise ValueError("bad free address")
            if pos == addr:
                if used == False:
                    raise ValueError("block already free")
                if i!=0 and self.blocks[i-1][1] == False:
                    bsize += self.blocks[i-1][0]
                    del self.blocks[i]
                    i -= 1
                if i!=(len(self.blocks)-1) and self.blocks[i+1][1] == False:
                    bsize += self.blocks[i+1][0]
                    del self.blocks[i]
                self.blocks[i] = (bsize, False)
                return
            pos += bsize
        raise ValueError("bad free address")

    def check(self):
        free = 0
        inuse = 0
        for i, (bsize, used) in enumerate(self.blocks):
            if used:
                inuse += bsize
            else:
                free += bsize
        if free + inuse != self.count:
            raise Exception("Total block size is inconsistent")
        print("Heap stats:")
        print(" In use: %8dkB"%(inuse * self.block // 1024))
        print(" Free:   %8dkB"%(free * self.block // 1024))

    @contextmanager
    def guarded_malloc(self, size):
        addr = self.malloc(size)
        try:
            yield addr
        finally:
            self.free(addr)

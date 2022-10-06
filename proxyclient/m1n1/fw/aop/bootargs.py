# SPDX-License-Identifier: MIT

class ASCArgumentSection:
    def __init__(self, bytes_):
        self.blob = bytearray(bytes_)
        self.index = self.build_index()

    def build_index(self):
        off = 0
        fields = []
        while off < len(self.blob):
            snip = self.blob[off:]
            key = snip[0:4]
            length = int.from_bytes(snip[4:8], byteorder='little')
            fields.append((key.decode('ascii'), (off + 8, length)))
            off += 8 + length

        if off > len(self.blob):
            raise ValueError('blob overran during parsing')

        return dict(fields)

    def items(self):
        for key, span in self.index.items():
            off, length = span
            yield key, self.blob[off:off + length]

    def __getitem__(self, key):
        off, length = self.index[key]
        return bytes(self.blob[off:off + length])

    def __setitem__(self, key, value):
        off, length = self.index[key]

        if type(value) is int:
            value = int.to_bytes(value, length, byteorder='little')
        elif type(value) is str:
            value = value.encode('ascii')

        if len(value) > length:
            raise ValueError(f'field {key:s} overflown')

        self.blob[off:off + length] = value

    def update(self, keyvals):
        for key, val in keyvals.items():
            self[key] = val

    def keys(self):
        return self.index.keys()

    def dump(self):
        for key, val in self.items():
            print(f"{key:4s} = {val}")

    def dump_diff(self, other, logger):
        assert self.index == other.index

        for key in self.keys():
            if self[key] != other[key]:
                logger(f"\t{key:4s} = {self[key]} -> {other[key]}")

    def to_bytes(self):
        return bytes(self.blob)

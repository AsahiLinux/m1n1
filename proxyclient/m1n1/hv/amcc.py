# SPDX-License-Identifier: GPL-2.0-or-later

from dataclasses import dataclass

@dataclass
class AMCCRegister:
    write_mask: int = 0
    override_mask: int = 0
    override: int = 0
    value: int = None

class VirtualAMCC:
    def __init__(self, hv, ranges):
        self.hv = hv
        self.registers = {}

        node = hv.adt["/chosen/lock-regs/amcc"]
        planes = [base + plane * node.plane_stride
                  for base in node.aperture_phys_addr
                  for plane in range(node.plane_count)]

        for bank, (lower, upper) in ranges.items():
            regnode = node[f'amcc-ctrr-{bank}']
            shift = regnode.page_size_shift
            fields = (
                # initialize with bounds SPTM expects to see
                ('lower_limit', (lower - hv.ram_base) >> shift),
                ('upper_limit', (upper - hv.ram_base) >> shift),
                # initialize with real hardware value on first read
                ('enable', None),
                ('lock', None),
                ('write_disable', None),
            )
            for field, override in fields:
                offset = getattr(regnode, f'{field}_reg_offset')
                mask = getattr(regnode, f'{field}_reg_mask')
                for base in planes:
                    reg = AMCCRegister(write_mask=mask)
                    if override is not None:
                        reg.override_mask = mask
                        reg.override = override & mask
                    self.registers[base + offset] = reg

    def read(self, addr, width=None):
        reg = self.registers[addr]
        if reg.value is None:
            reg.value = self.hv.p.read32(addr)
            reg.value &= ~reg.override_mask
            reg.value |= reg.override
        return reg.value

    def write(self, addr, data, width):
        reg = self.registers[addr]
        reg.value = self.read(addr)
        reg.value &= ~reg.write_mask
        reg.value |= data & reg.write_mask

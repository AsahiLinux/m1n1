# SPDX-License-Identifier: MIT
from ..utils import *

class R_PSTATE(Register32):
    RESET = 31
    AUTO_ENABLE = 28
    AUTO_STATE = 27, 24
    PARENT_MISSING = 11
    DEV_DISABLE = 10
    WAS_CLKGATED = 9
    WAS_PWRGATED = 8
    ACTUAL = 7, 4
    DESIRED = 3, 0

class R_PWRGATE(Register32):
    GATE = 31

class R_CLK_CFG(Register32):
    UNK31 = 31
    SRC = 30, 24
    UNK20 = 20
    UNK8 = 8
    UNK0 = 7, 0

class PMGRRegs0(RegMap):
    PS3 = irange(0x0000, 10, 8), R_PSTATE
    PS4 = irange(0x0200, 32, 8), R_PSTATE
    PS5 = irange(0x0300, 32, 8), R_PSTATE
    PS6 = irange(0x0c00, 2, 8), R_PSTATE
    PS7 = irange(0x4000, 13, 8), R_PSTATE
    PS8 = irange(0x8000, 5, 8), R_PSTATE
    PS9 = irange(0xc000, 7, 8), R_PSTATE
    PS10 = irange(0x10000, 10, 8), R_PSTATE
    PS11 = irange(0x100, 32, 8), R_PSTATE
    PS12 = irange(0x400, 15, 8), R_PSTATE

    PG1 = irange(0x1c010, 16, 8), R_PWRGATE
    PG1CFG = (irange(0x1c090, 69, 24), irange(0, 6, 4)), Register32

    CPUTVM0 = 0x48000, Register32
    CPUTVM1 = 0x48c00, Register32
    CPUTVM2 = 0x48800, Register32
    CPUTVM3 = 0x48400, Register32

class PMGRRegs1(RegMap):
    PS0 = irange(0x58, 32, 8), R_PSTATE
    PS1 = irange(0x4000, 32, 8), R_PSTATE
    PS2 = irange(0x8000, 32, 8), R_PSTATE

    PG0 = irange(0x1c010, 32, 8), R_PWRGATE

class PMGRRegs2(RegMap):
    CLK_CFG0 = irange(0x40000, 86, 4), R_CLK_CFG
    CLK_CFG1 = irange(0x40200, 8, 4), R_CLK_CFG
    CLK_CFG2 = irange(0x40280, 2, 4), R_CLK_CFG

class PMGR:
    def __init__(self, u):
        self.u = u
        self.p = u.proxy
        self.iface = u.iface
        self.node = u.adt["/arm-io/pmgr"]
        self.regs = [
            PMGRRegs0(u, self.node.get_reg(0)[0]),
            PMGRRegs1(u, self.node.get_reg(1)[0]),
            PMGRRegs2(u, self.node.get_reg(2)[0]),
        ]

    def dump_all(self):
        for i in self.regs:
            i.dump_regs()

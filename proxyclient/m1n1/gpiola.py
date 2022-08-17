# SPDX-License-Identifier: MIT
import os, sys, struct, time

from .utils import *
from . import asm
from .proxy import REGION_RX_EL1
from .sysreg import *

class GPIOLogicAnalyzer(Reloadable):
    def __init__(self, u, node=None, pins={}, regs={}, div=1, cpu=1, on_pin_change=True, on_reg_change=True):
        self.u = u
        self.p = u.proxy
        self.iface = u.iface
        self.cpu = cpu
        self.base = 0
        if node is not None:
            self.base = u.adt[node].get_reg(0)[0]
        else:
            on_pin_change=False
        self.node = node
        self.pins = pins
        self.regs = regs
        assert len(pins) <= 32
        assert div > 0
        self.div = div
        self.cbuf = self.u.malloc(0x1000)
        self.dbuf = None
        self.on_pin_change = on_pin_change
        self.on_reg_change = on_reg_change
        self.p.mmu_init_secondary(cpu)
        self.tfreq = u.mrs(CNTFRQ_EL0)

    def load_regmap(self, regmap, skip=set(), regs=set()):
        base = regmap._base
        for name, (addr, rcls) in regmap._namemap.items():
            if name not in skip and (not regs or name in regs):
                self.regs[name] = base + addr, rcls

    def start(self, ticks, bufsize=0x10000):
        self.bufsize = bufsize
        if self.dbuf:
            self.u.free(self.dbuf)
        self.dbuf = self.u.malloc(bufsize)

        text = f"""
        trace:
            mov x16, x2
            add x3, x3, x2
            add x2, x2, #4
            mov x12, #-8
            mov x10, x2
            mov x6, #-1
            mov x7, #0
            ldr x8, ={self.base}
            mrs x4, CNTPCT_EL0
            isb
        1:
            ldr w15, [x16]
            cmp w15, #1
            b.eq done
            add x4, x4, x1
        2:
            mrs x5, CNTPCT_EL0
            isb
        """
        if self.div > 1:
            text += f"""
                cmp x5, x4
                b.lo 2b
            """

        for idx, pin in enumerate(self.pins.values()):
            text += f"""
            ldr w9, [x8, #{pin * 4}]
            bfi x7, x9, #{idx}, #1
            """

        if self.on_pin_change:
            text += f"""
                cmp x7, x6
                b.eq 3f
                mov x6, x7
            """
        if self.on_reg_change:
            text += f"""
                mov x11, x2
            """

        text += f"""
            str w5, [x2], #4
            str w7, [x2], #4
        """
        if self.on_reg_change:
            text += f"""
                mov x13, #0
                add x14, x12, #8
            """

        for reg in self.regs.values():
            if isinstance(reg, tuple):
                reg = reg[0]
            text += f"""
                ldr x9, ={reg}
                ldr w9, [x9]
                str w9, [x2], #4
            """
            if self.on_reg_change:
                text += f"""
                    eor w15, w9, #1
                    cmp x14, #0
                    b.eq 4f
                    ldr w15, [x14], #4
                4:
                    eor w15, w15, w9
                    orr w13, w13, w15
                """

        if self.on_reg_change:
            text += f"""
                cmp x13, #0
                b.ne 4f
                mov x2, x11
                mov x11, x12
                b 3f
            4:
            """
        text += f"""
            mov x12, x11
            cmp x2, x3
            b.hs done
        3:
            sub x0, x0, #1
            cbnz x0, 1b
        done:
            sub x0, x2, x10
            ret
        """
        
        code = asm.ARMAsm(text, self.cbuf)
        self.iface.writemem(self.cbuf, code.data)
        self.p.dc_cvau(self.cbuf, len(code.data))
        self.p.ic_ivau(self.cbuf, len(code.data))

        self.p.write32(self.dbuf, 0)

        self.p.smp_call(self.cpu, code.trace | REGION_RX_EL1, ticks, self.div, self.dbuf, bufsize - (8 + 4 * len(self.regs)))
    
    def complete(self):
        self.p.write32(self.dbuf, 1)
        wrote = self.p.smp_wait(self.cpu)
        assert wrote <= self.bufsize
        data = self.iface.readmem(self.dbuf + 4, wrote)
        self.u.free(self.dbuf)
        self.dbuf = None
        
        stride = 2 + len(self.regs)
        
        #chexdump(data)
        
        self.data = [struct.unpack("<" + "I" * stride,
                                   data[i:i + 4 * stride])
                     for i in range(0, len(data), 4 * stride)]

    def vcd(self):
        off = self.data[0][0]
        if False: #len(self.data) > 1:
            off2 = max(0, ((self.data[1][0] - off) & 0xffffffff) - 5000)
        else:
            off2 = 0
        
        #print(off, off2)
        
        vcd = []
        vcd.append("""
$timescale 1ns $end
$scope module gpio $end
""")
        sym = 0
        keys = []
        rkeys = []
                                           
        for name in self.pins:
            keys.append(f"s{sym}")
            vcd.append(f"$var wire 1 s{sym} {name} $end\n")
            sym += 1
        for name, reg in self.regs.items():
            vcd.append(f"$var reg 32 s{sym} {name} [31:0] $end\n")
            if isinstance(reg, tuple):
                subkeys = {}
                rcls = reg[1]
                rkeys.append((f"s{sym}", rcls, subkeys))
                sym += 1
                for fname in rcls().fields.keys():
                    fdef = getattr(rcls, fname)
                    if isinstance(fdef, tuple):
                        width = fdef[0] - fdef[1] + 1
                    else:
                        width = 1
                    vcd.append(f"$var reg {width} s{sym} {name}.{fname} [{width-1}:0] $end\n")
                    subkeys[fname] = (width, f"s{sym}")
                    sym += 1
            else:
                rkeys.append((f"s{sym}", None, None))
                sym += 1
        vcd.append("""
$enddefinitions $end
$dumpvars
""")

        for v in self.data:
            ts = v[0]
            val = v[1]
            regs = v[2:]
            ts = ((ts - off) & 0xffffffff) - off2
            ns = max(0, 1000000000 * ts // self.tfreq)
            vcd.append(f"#{ns}\n")
            vcd.append("\n".join(f"{(val>>i) & 1}{k}" for i, k in enumerate(keys)) + "\n")
            for (key, rcls, subkeys), v in zip(rkeys, regs):
                vcd.append(f"b{v:032b} {key}\n")
                if rcls:
                    rval = rcls(v)
                    for field, (width, key) in subkeys.items():
                        v = getattr(rval, field)
                        vcd.append(f"b{v:0{width}b} {key}\n")
                    

        ns += ns//10
        vcd.append(f"#{ns}\n" + "\n".join(f"{(val>>i) & 1}{k}" for i, k in enumerate(keys)) + "\n")
 
        return "".join(vcd)
    
    def show(self):
        with open("/tmp/dump.vcd", "w") as fd:
            fd.write(self.vcd())
        
        gtkw = ("""
[dumpfile] "/tmp/dump.vcd"
[timestart] 0
[size] 3063 1418
[pos] -1 -1
*-17.000000 2 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1
[sst_width] 288
[signals_width] 197
[sst_expanded] 1
[sst_vpaned_height] 421
@23
""" +
        "\n".join("gpio." + k for k in self.pins) + "\n" + 
        "\n".join("gpio." + k + "[31:0]" for k in self.regs) + "\n")

        with open("/tmp/dump.gtkw", "w") as fd:
            fd.write(gtkw)

        os.system("gtkwave /tmp/dump.gtkw&")

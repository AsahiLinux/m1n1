#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1 import asm

LOOPS = 10000000
freq = u.mrs(CNTFRQ_EL0)

CREG = [
    0x210e00000,
    0x211e00000,
]

CLUSTER_PSTATE = 0x20020

# e-core pstates
#   600 972 1332 1704 2064
# p-core pstates
#   600 828 1056 1284 1500 1728 1956 2184 2388 2592 2772 2988 3096 3144 3204

code = u.malloc(0x1000)

util = asm.ARMAsm("""
bench:
    mrs x1, CNTPCT_EL0
1:
    sub x0, x0, #1
    cbnz x0, 1b

    mrs x2, CNTPCT_EL0
    sub x0, x2, x1
    ret
""", code)
iface.writemem(code, util.data)
p.dc_cvau(code, len(util.data))
p.ic_ivau(code, len(util.data))

def bench_cpu(idx):
    if idx == 0:
        elapsed = p.call(util.bench, LOOPS) / freq
    else:
        elapsed = p.smp_call_sync(idx, util.bench, LOOPS) / freq
    if elapsed == 0:
        return 0
    mhz = (LOOPS / elapsed) / 1000000
    return mhz

print()

e_pstate = p.read64(CREG[0] + CLUSTER_PSTATE)
p_pstate = p.read64(CREG[1] + CLUSTER_PSTATE)

print(f"E-Core pstate: {e_pstate:x}")
print(f"P-Core pstate: {p_pstate:x}")

#for cluster in range(2):
    #print(f"Initializing cluster {cluster} (early)")
    
    #p.write64(CREG[cluster] + 0x20660, 0x1000000015)
    #p.write64(CREG[cluster] + 0x48000, 0)
    #p.write64(CREG[cluster] + 0x48080, 0xa000000000000000)

    #p.clear64(CREG[cluster] + CLUSTER_PSTATE, 1<<22)

#p.set32(PMGR + 0x48000, 1)
#p.set32(PMGR + 0x48c00, 1)
#p.set32(PMGR + 0x48800, 1)
#p.set32(PMGR + 0x48400, 1)

CLUSTER_DVMR = 0x206b8
CLUSTER_LIMIT2 = 0x40240
CLUSTER_LIMIT3 = 0x40250
CLUSTER_LIMIT1 = 0x48400

PMGR_CPUGATING = 0x1c080
CLUSTER_CTRL = 0x440f8
CLUSTER_PSCTRL = 0x200f8

for cluster in range(2):
    print(f"Initializing cluster {cluster}")
    ena = (1<<63)
    val = p.read64(CREG[cluster] + CLUSTER_DVMR)
    if cluster == 1:
        ena |= (1<<32) | (1<<31)
    if (val & ena) != ena:
        print(f"DVMR: {val:#x} -> {val|ena:#x}")
        p.set64(CREG[cluster] + CLUSTER_DVMR, ena) # CLUSTER_DVMR
    
    #p.set64(CREG[cluster] + CLUSTER_LIMIT1, 1<<63)
    #p.clear64(CREG[cluster] + CLUSTER_LIMIT2, 1<<63)
    #p.set64(CREG[cluster] + CLUSTER_LIMIT3, 1<<63)
    
    #p.set64(CREG[cluster] + CLUSTER_PSTATE, 0)
    
    #p.set32(PMGR + PMGR_CPUGATING + 8 * cluster, 1<<31)

    #p.write64(CREG[cluster] + CLUSTER_CTRL, 1)
    
    #p.set64(CREG[cluster] + CLUSTER_PSCTRL, 1<<40)

    #pstate = p.read64(CREG[cluster] + CLUSTER_PSTATE) & 0xf

p.smp_start_secondaries()

print("== Initial CPU frequencies ==")

for cpu in range(8):
    print(f"CPU {cpu}: {bench_cpu(cpu):.2f} MHz")
    
def set_pstate(cluster, pstate):
    # This really seems to be all that's needed
    
    p.mask64(CREG[cluster] + CLUSTER_PSTATE, 0xf00f, (1<<25) | pstate | (pstate << 12))

    # Optionally, adjust MCC performance in higher p-core pstates
    if cluster == 1:
        if pstate > 8:
            p0, p1 = 0x133, 0x55555340
        else:
            p0, p1 = 0x813057f, 0x1800180

        for lane in range(8):
            p.write32(0x200200dc4 + lane * 0x40000, p0)
            p.write32(0x200200dbc + lane * 0x40000, p1)

    # This seems to be about notifying PMP
    #p.write32(0x23b738004 + cluster*4, pstate)
    #p.write32(0x23bc34000, 1 << cluster)

set_pstate(1, 15)

e_pstate = p.read64(CREG[0] + CLUSTER_PSTATE)
p_pstate = p.read64(CREG[1] + CLUSTER_PSTATE)

print(f"E-Core pstate: {e_pstate:x}")
print(f"P-Core pstate: {p_pstate:x}")

time.sleep(0.5)

print("== Final CPU frequencies ==")

#elapsed = p.smp_call(7, util.bench, 80000000)

for cpu in range(8):
    print(f"CPU {cpu}: {bench_cpu(cpu):.2f} MHz")

#elapsed = p.smp_wait(7)

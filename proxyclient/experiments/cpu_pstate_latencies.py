#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1 import asm

p.smp_start_secondaries()

tfreq = u.mrs(CNTFRQ_EL0)

TEST_CPUS = [1, 4]

CLUSTER_PSTATE = 0x20020
CLUSTER_STATUS = 0x20050

chip_id = u.adt["/chosen"].chip_id

if chip_id in (0x8103, 0x6000, 0x6001, 0x6002):
    CREG = [
        0x210e00000,
        0x211e00000,
    ]

    MAX_PSTATE = [5, 15]

elif chip_id in (0x8121, 0x6020, 0x6021, 0x6022):
    CREG = [
        0x210e00000,
        0x211e00000,
    ]

    if u.adt["/chosen"].target_type == "J416c":
        MAX_PSTATE = [7, 19]
    else:
        MAX_PSTATE = [7, 17]

code = u.malloc(0x1000)

util = asm.ARMAsm(f"""
bench:
    mrs x1, CNTPCT_EL0
1:
    sub x0, x0, #1
    cbnz x0, 1b

    mrs x2, CNTPCT_EL0
    sub x0, x2, x1
    ret

signal_and_write:
    sev
    mrs x2, CNTPCT_EL0
    add x2, x2, #0x800
1:
    mrs x3, CNTPCT_EL0
    sub x4, x3, x2
    cbnz x4, 1b
    str x1, [x0]
    mov x0, x3
    ret

timelog:
    mrs x2, s3_1_c15_c0_0 /* SYS_IMP_APL_PMCR0 */
    orr x2, x2, #1
    msr s3_1_c15_c0_0, x2
    mov x2, #0xffffffffffffffff
    msr s3_1_c15_c1_0, x2
    isb
    wfe
1:
    mrs x2, CNTPCT_EL0
    mrs x3, s3_2_c15_c0_0
    isb
    stp x2, x3, [x0], #16
    mov x4, #0x40
2:
    sub x4, x4, #1
    cbnz x4, 2b
    sub x1, x1, #1
    cbnz x1, 1b
    
    ret
""", code)
iface.writemem(code, util.data)
p.dc_cvau(code, len(util.data))
p.ic_ivau(code, len(util.data))

def bench_cpu(idx, loops=10000000):
    if u.adt["cpus"][idx].state == "running":
        elapsed = p.call(util.bench, loops) / tfreq
    else:
        elapsed = p.smp_call_sync(idx, util.bench, loops) / tfreq
    if elapsed == 0:
        return 0
    mhz = (loops / elapsed) / 1000000
    return mhz

def set_pstate(cluster, pstate):
    p.mask64(CREG[cluster] + CLUSTER_PSTATE, 0x1f01f, (1<<25) | pstate)

print()

LOG_ITERS = 10000
logbuf = u.malloc(LOG_ITERS * 16)

def bench_latency(cluster, cpu, from_pstate, to_pstate, verbose=False):
    set_pstate(cluster, from_pstate)
    bench_cpu(cpu)

    p.smp_call(cpu, util.timelog, logbuf, LOG_ITERS)
    psreg = (p.read64(CREG[cluster] + CLUSTER_PSTATE) & ~0x1f01f) | (1<<25) | to_pstate
    tval = p.call(util.signal_and_write, CREG[cluster] + CLUSTER_PSTATE, psreg)
    p.smp_wait(cpu)
    
    logdata = iface.readmem(logbuf, LOG_ITERS * 16)
    lts, lcyc = None, None
    
    log = []
    for i in range(LOG_ITERS):
        ts, cyc = struct.unpack("<QQ", logdata  [i*16:i*16+16])
        log.append((ts, cyc))

    off = 256
    
    ts_0, cyc_0 = log[off]
    ts_e, cyc_e = log[-1]
    f_init = None
    f_end = None
    lts, lcyc = ts_0, cyc_0

    inc = to_pstate > from_pstate

    blip = 0
    cnt = dts_sum = 0
    for i in range(off, len(log)):
        ts, cyc = log[i]
        dts = ts - lts
        dcyc = cyc - lcyc

        cnt += 1
        dts_sum += dts

        blip = max(blip, dts)

        if f_init is None and ts > tval:
            tidx = i
            f_init = (lcyc - cyc_0) / (lts - ts_0) * tfreq / 1000000
            dts_init = dts_sum / cnt
        if f_end is None and ts > (tval + ts_e) / 2:
            f_end = (cyc_e - cyc) / (ts_e - ts) * tfreq / 1000000
            cnt = dts_sum = 0
    
        #if lts is not None:
            #print(f"{i}: {ts}: {cyc} ({ts-lts}: {cyc-lcyc})")
        #else:
            #print(f"{i}: {ts}: {cyc}")
        lts, lcyc = ts, cyc

    dts_end = dts_sum / cnt

    window = 32

    if verbose:
        print(f"Triggered at {tval}")

    thresh = 2/ (1/f_init + 1/f_end)

    for i in range(tidx, LOG_ITERS - window - 1):
        ts0, cyc0 = log[i - window]
        ts1, cyc1 = log[i + window]
        f = (cyc1 - cyc0) / (ts1 - ts0) * tfreq / 1000000
        if inc and (f > thresh) or ((not inc) and f < thresh):
            tts = log[i][0]
            tidx = i
            if verbose:
                print(f"Frequency transition at #{i} {tts}")
            break

    if verbose:
        print(f"Initial frequency: {f_init:.2f}")
        print(f"Final frequency: {f_end:.2f}")
        print(f"Threshold: {thresh:.2f}")

        for i in range(max(window, tidx - 10 * window), tidx + 10 * window):
            ts0, cyc0 = log[i - window]
            ts1, cyc1 = log[i + window]
            lts, lcyc = log[i - 1]
            ts, cyc = log[i]
            f = (cyc1 - cyc0) / (ts1 - ts0) * tfreq / 1000000
            print(f"{i}: {ts}: {cyc} ({ts-lts}: {cyc-lcyc}): {f:.2f}")

    blip -= min(dts_init, dts_end)

    return (tts - tval) / tfreq * 1000000000, blip / tfreq * 1000000000

for cluster, creg in enumerate(CREG):
    cpu = TEST_CPUS[cluster]

    freqs = []

    print(f"#### Cluster {cluster} ####")
    print(" P-States:")
    print("  ", end="")
    for pstate in range(MAX_PSTATE[cluster] + 1):
        set_pstate(cluster, pstate)
        freq = int(round(bench_cpu(cpu)))
        freqs.append(freq)
        print(f"{pstate}:{freq}MHz", end=" ")
    print()
    print()
    
    print(" To-> |", end="")
    for to_pstate in range(1, MAX_PSTATE[cluster] + 1):
        print(f" {freqs[to_pstate]:7d} |", end="")
    print()
    print(" From |", end="")
    for to_pstate in range(1, MAX_PSTATE[cluster] + 1):
        print(f"---------+", end="")
    print()
    
    maxblip = 0
    
    for from_pstate in range(1, MAX_PSTATE[cluster] + 1):
        print(f" {freqs[from_pstate]:4d} |", end="")
        for to_pstate in range(1, MAX_PSTATE[cluster] + 1):
            if from_pstate == to_pstate:
                print(f" ******* |", end="")
                continue
            lat, blip = bench_latency(cluster, cpu, from_pstate, to_pstate)
            print(f" {lat:7.0f} |", end="")
            maxblip = max(maxblip, blip)
        print()
    
    print()
    print(f"Maximum execution latency spike: {maxblip:.0f} ns")
    print()

print()

#bench_latency(1, TEST_CPUS[1], 15, 14, True)



#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
import time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.loadobjs import *
import argparse
import numpy as np

argparser = argparse.ArgumentParser()
argparser.add_argument("-d", "--domain", type=str,
		       help='Look for MMIO range associated with a particular'
		       		' power domain')
argparser.add_argument("-p", "--print", action='store_true',
		       help='Print power domain list')
args = argparser.parse_args()

if args.print:
	for dev in u.adt["/arm-io/pmgr"].devices:
		print(dev.name)
	sys.exit(0)

granule = 0x4000

lp = LinkedProgram(u)
lp.load_inline_c(f'''
	#define GRANULE {granule}
	''' + '''
	#include "exception.h"
	#include "utils.h"
	#include "soc.h"

	bool is_t6000(void)
	{
		return chip_id == T6000;
	}

	void sweep(u64 from, u64 to, u64 target)
	{
		u32 *mask = (u32 *) target;
		exc_guard = GUARD_MARK | GUARD_SILENT;

		int bitp = 0;
		for (u64 p = from; p < to; p += GRANULE) {
			sysop("dsb sy");
			sysop("isb");
			bool hit = read32(p) != 0xabad1dea;

			if (hit)
				*mask |= (1 << bitp);
			else
				*mask &= ~(1 << bitp);

			if (++bitp >= 32) {
				bitp = 0;
				mask++;
			}
		}

		sysop("dsb sy");
		sysop("isb");
	}
	''')

def do_sweep(maskrange):
	masklen = (maskrange.stop - maskrange.start) // granule // 32 * 4 + 4
	mask_base = u.heap.malloc(masklen)
	lp.sweep(maskrange.start, maskrange.stop, mask_base)
	mask = iface.readmem(mask_base, masklen)
	u.heap.free(mask_base)
	return np.frombuffer(mask, dtype=np.uint8)

def describe_mask(mask, maskrange):
	'''
	Describe mask in terms of hot from-to ranges
	'''
	ranges = []
	prev_hit = False
	mask = np.concatenate((mask, [0]))
	for i in range(len(mask)*8):
		hit = mask[i//8] & (1<<(i%8)) != 0
		if hit and not prev_hit:
			start = maskrange.start + i*granule
		if not hit and prev_hit:
			end = maskrange.start + i*granule
			ranges.append((start, end))
		prev_hit = hit
	return ranges

if lp.is_t6000():
	maskrange = range(0x2_9000_0000, 0x4_0000_0000)
else:
	maskrange = range(0x2_2000_0000, 0x3_0000_0000)

pd_did_enable = set()
pmgr = u.adt["/arm-io/pmgr"]
ps_dev_by_id = {dev.id: dev for dev in pmgr.devices}
ps_deps = dict()
ps_addrs = dict()

for dev in pmgr.devices:
	ps = pmgr.ps_regs[dev.psreg]
	addr = pmgr.get_reg(ps.reg)[0] + ps.offset + dev.psidx * 8

	if lp.is_t6000() and dev.name.startswith("AOP_"):
		addr = 0x292284000 + (dev.id - 403) * 8		

	ps_addrs[dev.name] = addr
	ps_deps[dev.name] = [
		ps_dev_by_id[idx].name for idx
		in dev.parents if idx in ps_dev_by_id
	]

if lp.is_t6000():
	# on t6000, guess the AOP PD hierarchy (undocumented
	# in ADT) by analogy with t8103
	ps_deps["AOP_GPIO"] += ["AOP_FILTER"]
	ps_deps["AOP_BASE"] += ["AOP_FILTER"]
	ps_deps["AOP_FR"] += ["AOP_FILTER"]
	ps_deps["AOP_SPMI0"] += ["AOP_FR"]
	ps_deps["AOP_SPMI1"] += ["AOP_FR"]
	ps_deps["AOP_LEAP_CLK"] += ["AOP_FILTER"]
	ps_deps["AOP_SHIM"] += ["AOP_BASE"]
	ps_deps["AOP_UART0"] += ["AOP_SHIM"]
	ps_deps["AOP_UART1"] += ["AOP_SHIM"]
	ps_deps["AOP_UART2"] += ["AOP_SHIM"]
	ps_deps["AOP_SCM"] += ["AOP_BASE", "AOP_FR"]
	ps_deps["AOP_CPU"] += ["AOP_BASE"]
	ps_deps["AOP_I2CM0"] += ["AOP_FR"]
	ps_deps["AOP_I2CM1"] += ["AOP_FR"]
	ps_deps["AOP_MCA0"] += ["AOP_FR", "AOP_SHIM"]
	ps_deps["AOP_MCA1"] += ["AOP_FR", "AOP_SHIM"]
	ps_deps["AOP_SPI0"] += ["AOP_FR"]
	ps_deps["AOP_LEAP"] += ["AOP_LEAP_CLK"]
	ps_deps["AOP_AUDIO_SHIM"] += ["AOP_LEAP_CLK"]
	ps_deps["AOP_AUDIO_ADMA0"] += ["AOP_FR"]
	ps_deps["AOP_PDMC_LPD"] += ["AOP_SHIM"]
	ps_deps["AOP_SRAM"] += ["AOP_SCM", "AOP_CPU"]

def ps_pstate(name):
	return p.read32(ps_addrs[name]) & 0x0f

def ps_enabled(name):
	return p.read32(ps_addrs[name]) & 0x0f == 0x0f

def ps_set_pstate(name, desired):
	p.mask32(ps_addrs[name], 0xf, desired)
	time.sleep(0.001)
	actual = p.read32(ps_addrs[name])
	if actual & 0xf0 != desired << 4:
		print("WARNING: %s stuck at pstate 0x%x (desired 0x%x)" \
			% (name, actual >> 4, desired))

def ps_enable(name):
	print("Enabling %s..." % name)
	ps_set_pstate(name, 0xf)

def ps_disable(name):
	p.mask32(ps_addrs[name], 0xf, 0x0)

if args.domain:
	ps_disable(args.domain)

	to_enable = set([args.domain])
	for dev in reversed(pmgr.devices):
		if dev.name not in to_enable \
				or ps_enabled(dev.name):
			continue

		for dep in ps_deps[dev.name]:
			to_enable.add(dep)

	save = dict()
	for dev in pmgr.devices:
		if dev.name in to_enable:
			save[dev.name] = ps_pstate(dev.name)
			if dev.name != args.domain:
				ps_enable(dev.name)

	premask = do_sweep(maskrange)
	ps_enable(args.domain)
	postmask = do_sweep(maskrange)

	print("Reverting...")

	for dev in reversed(pmgr.devices):
		if dev.name in to_enable and dev.name:
			ps_set_pstate(dev.name, save[dev.name])

	hitmask = premask ^ postmask
	if np.count_nonzero(hitmask & premask):
		print("Que? Some ranges disappeared?")
else:
	# no --domain flag, do a plain sweep
	hitmask = do_sweep(maskrange)

al = u.adt.build_addr_lookup()
for start, stop in describe_mask(hitmask, maskrange):
	# bit ugly but it makes addrlookup do all the heavy lifting for us
	al.add(range(start, stop), "hit")

print("Hits:")
for zone, value in al.items():
	if ((zone.start - 1) // granule + 1) * granule >= zone.stop:
		continue
	if not any([v[0] == "hit" for v in value]):
		continue

	labels = set([v[0] for v in value if v[0] != "hit"])
	print(f"\t{zone.start:9x} - {zone.stop:9x} | {' '.join(labels)}")

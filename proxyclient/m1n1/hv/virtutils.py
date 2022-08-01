# SPDX-License-Identifier: MIT
from m1n1.utils import align_up

def collect_aic_irqs_in_use(adt):
	used = set()
	aic_phandle = getattr(adt["/arm-io/aic"], "AAPL,phandle")
	for node in adt.walk_tree():
		if not hasattr(node, "interrupt_parent") or \
				node.interrupt_parent != aic_phandle:
			continue
		for no in node.interrupts:
			used.add(no)
	return used

def usable_aic_irq_range(adt):
	# These are too optimistic but since we allocate
	# from the bottom of the range it doesn't matter much.
	return {
		"aic,1": range(0, 0x400),
		"aic,2": range(0, 0x1000),
	}.get(adt["/arm-io/aic"].compatible[0])

def alloc_aic_irq(adt):
	used = collect_aic_irqs_in_use(adt)
	for no in usable_aic_irq_range(adt):
		if no not in used:
			return no
	return None

def usable_mmio_range(adt):
	arm_io_range = adt["arm-io"].ranges[0]
	return range(arm_io_range.parent_addr, arm_io_range.parent_addr + arm_io_range.size)

def alloc_mmio_base(adt, size, alignment=0x4000):
	span = usable_mmio_range(adt)
	la = adt.build_addr_lookup()
	for zone, devs in la.populate(span):
		if len(devs) != 0:
			continue
		base = align_up(zone.start, alignment)
		if zone.stop > base + size:
			return base
	return None

# SPDX-License-Identifier: MIT

__all__ = ["NCO"]

def galois_lfsr(init, poly):
	state = init
	for i in range((1 << poly.bit_length() - 1) - 1):
		if state & 1:
			state = (state >> 1) ^ (poly >> 1)
		else:
			state = (state >> 1)
		yield state

def gen_lookup_tables():
	fwd, inv = dict(), dict()
	lfsr_states = [0] + list(reversed(list(galois_lfsr(0x7ff, 0xa01))))
	for cycle, sr_state in enumerate(lfsr_states):
		fwd[cycle + 2] = sr_state
		inv[sr_state] = cycle + 2
	return fwd, inv


class NCOChannel:
	def __init__(self, parent, base):
		self.parent = parent
		self.base = base
		self.p = parent.u.proxy

	def enabled(self):
		return bool(self.p.read32(self.base) & (1<<31))

	def enable(self):
		self.p.set32(self.base, 1<<31)

	def disable(self):
		self.p.clear32(self.base, 1<<31)

	def set_rate(self, target):
		was_enabled = self.enabled()
		for off, val in enumerate(NCO.calc_regvals(self.parent.fin, target)):
			self.p.write32(self.base + off*4, val)
		if was_enabled:
			self.enable()

	def get_rate(self):
		return NCO.calc_rate(self.parent.fin,
			[self.p.read32(self.base + off*4) for off in range(4)]
		)

	def __repr__(self):
		return f"<NCO channel @ 0x{self.base:x}>"


class NCO:
	TBL, TBL_INV = gen_lookup_tables()

	@classmethod
	def calc_rate(self, fin, regvals):
		try:
			div = self.TBL_INV[regvals[1] >> 2] << 2 | regvals[1] & 3
		except KeyError:
			raise ValueError("bad configuration")
		inc1 = regvals[2]
		inc2 = regvals[3] - 0x1_0000_0000
		return 2 * fin * (inc1 - inc2) // (div * (inc1 - inc2) + inc1)

	@classmethod
	def calc_regvals(self, fin, fout):
		div = 2 * fin // fout
		inc1 = (2 * fin - div * fout)
		inc2 = inc1 - fout
		try:
			return [0, self.TBL[div >> 2] << 2 | div & 3, inc1, inc2 + 0x1_0000_0000]
		except KeyError:
			raise ValueError("target rate out of range")

	def __init__(self, u, devpath, stride=0x4000):
		self.u = u
		node = u.adt[devpath]
		self.fin = u.adt["/arm-io"].clock_frequencies[node.clock_ids[0] - 256]

		reg = node.get_reg(0)
		self.chans = [
			NCOChannel(self, base)
			for base in range(reg[0], reg[0] + reg[1], stride)
		]

	def __getitem__(self, idx):
		return self.chans[idx]

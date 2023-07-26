# SPDX-License-Identifier: MIT

import struct


class ISPChannelMessage:
	def __init__(self, arg0=0x0, arg1=0x0, arg2=0x0, arg3=0x0, arg4=0x0, arg5=0x0, arg6=0x0, arg7=0x0):
		self.count = 8
		self.arg0 = arg0; self.arg1 = arg1; self.arg2 = arg2; self.arg3 = arg3; self.arg4 = arg4; self.arg5 = arg5; self.arg6 = arg6; self.arg7 = arg7
		self.args = [self.arg0, self.arg1, self.arg2, self.arg3, self.arg4, self.arg5, self.arg6, self.arg7]

	@classmethod
	def build(cls, arg0=0x0, arg1=0x0, arg2=0x0, arg3=0x0, arg4=0x0, arg5=0x0, arg6=0x0, arg7=0x0):
	        return cls(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7)

	@classmethod
	def new(cls): return cls.build()

	@classmethod
	def parse(cls, buf):
	        arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7 = struct.unpack("<8q", buf)
	        return cls(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7)

	def encode(self):
	        return struct.pack("<8q", *(self.arg0, self.arg1, self.arg2, self.arg3, self.arg4, self.arg5, self.arg6, self.arg7))

	def __str__(self, max_count=3):
		s = "["
		for n in range(max_count):
			s += "0x%x" % (getattr(self, f"arg{n}"))
			if (n < max_count-1):
		                s += ", "
		s += "]"
		return s

	def valid(self):  # rough check used for dumps
		return (self.arg0 != 0x1) and (self.arg0 != 0x3) and (not (all(arg == 0x0 for arg in self.args)))

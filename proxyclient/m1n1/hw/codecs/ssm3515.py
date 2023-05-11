from m1n1.utils import Register8, RegMap
from enum import IntEnum

class R_PWR(Register8):
	APWDN_EN  = 7
	BSNS_PWDN = 6
	S_RST     = 1
	SPWDN     = 0

class R_GEC(Register8):
	EDGE     = 4
	ANA_GAIN = 1, 0

class E_FS(IntEnum):
	FS_8_12    = 0b000
	FS_16_24   = 0b001
	FS_32_48   = 0b010
	FS_64_96   = 0b011
	FS_128_192 = 0b100
	FS_48_72   = 0b101

class R_DAC(Register8):
	HV   = 7
	MUTE = 6
	HPF  = 5
	LPM  = 4
	FS   = 1, 0, E_FS

class R_SAI1(Register8):
	DAC_POL    = 7
	BCLK_POL   = 6
	TDM_BCLKS  = 5, 3
	FSYNC_MODE = 2
	SDATA_FMT  = 1
	SAI_MODE   = 0

class R_SAI2(Register8):
	DATA_WIDTH = 7
	AUTO_SLOT  = 4
	TDM_SLOT   = 3, 0

class R_STATUS(Register8):
	UVLO_VREG = 6
	LIM_EG    = 5
	CLIP      = 4
	AMP_OC    = 3
	OTF       = 2
	OTW       = 1
	BAT_WARN  = 0

class SSM3515Regs(RegMap):
	PWR      = 0x00, R_PWR
	GEC      = 0x01, R_GEC
	DAC      = 0x02, R_DAC
	DAC_VOL  = 0x03, Register8
	SAI1     = 0x04, R_SAI1
	SAI2     = 0x05, R_SAI2
	VBAT_OUT = 0x06, Register8
	LIM1     = 0x07, Register8
	LIM2     = 0x08, Register8
	LIM3     = 0x09, Register8
	STATUS   = 0x0a, Register8
	FAULT    = 0x0b, Register8

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
import time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

# audio_capture.py -- capture audio on jack microphone input (on M1 macs with cs42l83)
#
# sample usage with sox: (recoding can be loud!)
#
#  ./audio_capture.py | sox -t raw -r 48000 -c 1 -e signed-int -b 32 -L - OUTPUT_FILE

from m1n1.setup import *
from m1n1.hw.dart import DART, DARTRegs
from m1n1.hw.i2c import I2C
from m1n1.hw.pmgr import PMGR
from m1n1.hw.nco import NCO
from m1n1.hw.admac import *
from m1n1.hw.mca import *

p.pmgr_adt_clocks_enable("/arm-io/i2c2")
p.pmgr_adt_clocks_enable("/arm-io/admac-sio")
p.pmgr_adt_clocks_enable("/arm-io/dart-sio")
p.pmgr_adt_clocks_enable("/arm-io/mca-switch")
p.pmgr_adt_clocks_enable("/arm-io/mca3")

# reset AUDIO_P
PS_AUDIO_P = PMGR(u).regs[0].PS4[10]
PS_AUDIO_P.set(DEV_DISABLE=1)
PS_AUDIO_P.set(RESET=1)
PS_AUDIO_P.set(RESET=0)
PS_AUDIO_P.set(DEV_DISABLE=0)

dart_base, _ = u.adt["/arm-io/dart-sio"].get_reg(0)
dart = DART(iface, DARTRegs(u, dart_base), util=u)
dart.initialize()

cl_no = 2

admac = ADMAC(u, "/arm-io/admac-sio", dart, debug=True)
dmachan = admac.chans[4*cl_no+1]
dmachan.buswidth = E_BUSWIDTH.W_32BIT
dmachan.framesize = E_FRAME.F_1_WORD

nco = NCO(u, "/arm-io/nco")
nco[cl_no].set_rate(6000000)
nco[cl_no].enable()

mca_switch1_base = u.adt["/arm-io/mca-switch"].get_reg(1)[0]
mca_cl_base = u.adt["/arm-io/mca-switch"].get_reg(0)[0] + 0x4000*cl_no
cl = MCACluster(u, mca_cl_base)

regs, serdes = cl.regs, cl.rxa

regs.SYNCGEN_STATUS.set(EN=0)
regs.SYNCGEN_MCLK_SEL.val =(1 + cl_no)
regs.SYNCGEN_HI_PERIOD.val = 0    # period minus one
regs.SYNCGEN_LO_PERIOD.val = 0x7b # period minus one

serdes.STATUS.set(EN=0)
serdes.CONF.set(
	NSLOTS=0,
	SLOT_WIDTH=E_SLOT_WIDTH.W_32BIT,
	BCLK_POL=1,
	UNK1=1, UNK2=1,
	SYNC_SEL=(1 + cl_no)
)
serdes.UNK1.val = 0x4

serdes.BITDELAY.val = 1

serdes.CHANMASK[0].val = 0xffff_ffff
serdes.CHANMASK[1].val = 0xffff_fffe

regs.PORT_ENABLES.set(CLOCK1=1, CLOCK2=1, DATA=0)
regs.PORT_CLK_SEL.set(SEL=(cl_no + 1))
regs.MCLK_STATUS.set(EN=1)
regs.SYNCGEN_STATUS.set(EN=1)

cs42l_addr = 0x48
i2c2 = I2C(u, "/arm-io/i2c2")
def cs42l_write(regaddr, val):
	i2c2.write_reg(cs42l_addr, 0x0, [regaddr >> 8])
	i2c2.write_reg(cs42l_addr, regaddr & 0xff, [val])

p.write32(0x23d1f002c, 0x76a02)
p.write32(0x23d1f002c, 0x76a03) # take jack codec out of reset

cs42l_write(0x1009, 0x0)  # FS_int = MCLK/250
cs42l_write(0x1101, 0x7a) # power on
cs42l_write(0x1103, 0x22) # power on ring sense
cs42l_write(0x1107, 0x1)  # SCLK present
cs42l_write(0x1121, 0xa6) # Headset Switch Control
cs42l_write(0x1129, 0x1)  # Headset Clamp Disable
cs42l_write(0x1205, 0x7c) # FSYNC period
cs42l_write(0x1207, 0x20) # ASP Clock Configuration
cs42l_write(0x1208, 0x12) # BITDELAY = 1
cs42l_write(0x120c, 0x1)  # SCLK_PREDIV = div-by-2
cs42l_write(0x150a, 0x55) # PLL
cs42l_write(0x151b, 0x1)  # PLL
cs42l_write(0x1501, 0x1)  # power on PLL
cs42l_write(0x1b70, 0xc3) # HSBIAS sense
cs42l_write(0x1b71, 0xe0) # v-- headset 
cs42l_write(0x1b73, 0xc0)
cs42l_write(0x1b74, 0x1f)
cs42l_write(0x1b75, 0xb6)
cs42l_write(0x1b76, 0x8f)
cs42l_write(0x1b79, 0x0)
cs42l_write(0x1b7a, 0xfc)
cs42l_write(0x1c03, 0xc0) # HSBIAS
cs42l_write(0x2506, 0xc)  # ASP TX samp. rate
cs42l_write(0x2609, 0x4c) # SRC output samp. rate
cs42l_write(0x2901, 0x1)  # ASP TX enable & size
cs42l_write(0x2902, 0x1)  # ASP TX channel enable

time.sleep(0.01)

cs42l_write(0x1201, 0x1) # transition to PLL clock

# drain garbled samples (why are they garbled? i am not sure)
time.sleep(0.5)

dmachan.submit(buflen=0x4000)
dmachan.enable()

p.write32(mca_switch1_base + 0x8000*cl_no, 0x24800)
serdes.STATUS.set(EN=1)

while True:
	while dmachan.can_submit():
		dmachan.submit(buflen=0x4000)
	sys.stdout.buffer.write(dmachan.poll())

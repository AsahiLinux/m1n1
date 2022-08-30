#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
import time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

# speaker_amp.py -- play audio through the embedded speaker on Mac mini
#
# sample usage with sox:
#
#   sox INPUT_FILE -t raw -r 48000 -c 1 -e signed-int -b 32 -L - gain -63 | python3 ./speaker_amp.py
#
# (expects mono, 24-bit signed samples padded to 32 bits on the msb side)

import argparse
from m1n1.setup import *
from m1n1.hw.dart import DART, DARTRegs
from m1n1.hw.i2c import I2C
from m1n1.hw.pmgr import PMGR
from m1n1.hw.nco import NCO
from m1n1.hw.admac import *
from m1n1.hw.mca import *

argparser = argparse.ArgumentParser()
argparser.add_argument("-f", "--file", "--input", "--samples",
                       type=str, default=None,
                       help='input filename to take samples from ' \
                            '(default: standard input)')
argparser.add_argument("-b", "--bufsize", type=int, default=1024*32,
                       help='size of buffers to keep submitting to DMA')
args = argparser.parse_args()

inputf = open(args.file, "rb") if args.file is not None \
            else sys.stdin.buffer 

p.pmgr_adt_clocks_enable("/arm-io/i2c1")
p.pmgr_adt_clocks_enable("/arm-io/admac-sio")
p.pmgr_adt_clocks_enable("/arm-io/dart-sio")
p.pmgr_adt_clocks_enable("/arm-io/mca-switch")

# reset AUDIO_P
PS_AUDIO_P = PMGR(u).regs[0].PS4[5]
PS_AUDIO_P.set(DEV_DISABLE=1)
PS_AUDIO_P.set(RESET=1)
PS_AUDIO_P.set(RESET=0)
PS_AUDIO_P.set(DEV_DISABLE=0)

i2c1 = I2C(u, "/arm-io/i2c1")

dart_base, _ = u.adt["/arm-io/dart-sio"].get_reg(0) # stream index 2
dart = DART(iface, DARTRegs(u, dart_base), util=u)
dart.initialize()

cl_no = 0

admac = ADMAC(u, "/arm-io/admac-sio", dart, debug=True)
tx_chan = admac.chans[4*cl_no]

tx_chan.disable()
tx_chan.reset()
tx_chan.read_reports() # read stale reports
tx_chan.buswidth = E_BUSWIDTH.W_32BIT
tx_chan.framesize = E_FRAME.F_1_WORD

nco = NCO(u, "/arm-io/nco")
nco[cl_no].set_rate(48000 * 256)
nco[cl_no].enable()

mca_switch1_base = u.adt["/arm-io/mca-switch"].get_reg(1)[0]
mca_cl_base = u.adt["/arm-io/mca-switch"].get_reg(0)[0] + 0x4000*cl_no
cl = MCACluster(u, mca_cl_base)

regs, serdes = cl.regs, cl.txa

regs.SYNCGEN_STATUS.set(RST=1, EN=0)
regs.SYNCGEN_STATUS.set(RST=0)
regs.SYNCGEN_MCLK_SEL.val =(1 + cl_no)
regs.SYNCGEN_HI_PERIOD.val = 0
regs.SYNCGEN_LO_PERIOD.val = 0xfe  # full period minus two

serdes.STATUS.set(EN=0)
serdes.CONF.set(
    NSLOTS=0,
    SLOT_WIDTH=E_SLOT_WIDTH.W_32BIT,
    BCLK_POL=1,
    UNK1=1, UNK2=1,
    IDLE_UNDRIVEN=1,
    SYNC_SEL=(1 + cl_no)
)
serdes.BITDELAY.val = 0

serdes.CHANMASK[0].val = 0xffff_fffe
serdes.CHANMASK[1].val = 0xffff_fffe

regs.PORT_ENABLES.set(CLOCK1=1, CLOCK2=1, DATA=1)
regs.PORT_CLK_SEL.set(SEL=(cl_no + 1))
regs.PORT_DATA_SEL.val = cl_no + 1
regs.MCLK_STATUS.set(EN=1)
regs.SYNCGEN_STATUS.set(EN=1)

p.write32(mca_switch1_base + 0x8000*cl_no, 0x102048)

# toggle the GPIO line driving the speaker-amp IC reset
p.write32(0x23c1002d4, 0x76a02) # invoke reset
p.write32(0x23c1002d4, 0x76a03) # take out of reset

tx_chan.submit(inputf.read(args.bufsize))
tx_chan.enable()
while tx_chan.can_submit():
    tx_chan.submit(inputf.read(args.bufsize))

serdes.STATUS.set(EN=1)

# by ADT and leaked schematic, i2c1 contains TAS5770L,
# which is not a public part. but there's e.g. TAS2770
# with similar registers
#
# https://www.ti.com/product/TAS2770
#
# if the speaker-amp IC loses clock on the serial sample input,
# it automatically switches to software shutdown.
#

i2c1.write_reg(0x31, 0x08, [0x40])
i2c1.write_reg(0x31, 0x0a, [0x06, 0x00, 0x1a])
i2c1.write_reg(0x31, 0x1b, [0x01, 0x82, 0x06])
i2c1.write_reg(0x31, 0x16, [0x50, 0x04])
i2c1.write_reg(0x31, 0x0d, [0x00])
#i2c1.write_reg(0x31, 0x03, [0x14])

# amplifier gain, presumably this is the lowest setting
i2c1.write_reg(0x31, 0x03, [0x0])

# take the IC out of software shutdown
i2c1.write_reg(0x31, 0x02, [0x0c])

while (buf := inputf.read(args.bufsize)):
    while not tx_chan.can_submit():
        tx_chan.poll()
    tx_chan.submit(buf)

# mute
i2c1.write_reg(0x31, 0x02, [0x0d])

# software shutdown
i2c1.write_reg(0x31, 0x02, [0x0e])

tx_chan.disable()

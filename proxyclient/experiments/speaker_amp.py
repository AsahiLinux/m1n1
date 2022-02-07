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
from m1n1.hw.admac import *
from m1n1.hw.i2c import I2C


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


i2c1 = I2C(u, "/arm-io/i2c1")

dart_base, _ = u.adt["/arm-io/dart-sio"].get_reg(0) # stream index 2
dart = DART(iface, DARTRegs(u, dart_base), util=u)
dart.initialize()

admac = ADMAC(u, "/arm-io/admac-sio", dart, debug=True)
tx_chan = admac.chans[4]

tx_chan.disable()
tx_chan.reset()
tx_chan.read_reports() # read stale reports
tx_chan.buswidth = E_BUSWIDTH.W_32BIT
tx_chan.framesize = E_FRAME.F_1_WORD

mca_switch0_base = 0x2_3840_0000 # size: 0x1_8000
mca_switch1_base = 0x2_3830_0000 # size: 0x3_0000

for off in [0x0, 0x100, 0x4000, 0x4100]:
    p.write32(mca_switch0_base + off, 0x0)
    p.write32(mca_switch0_base + off, 0x2)


p.write32(mca_switch0_base + 0x4104, 0x0)
p.write32(mca_switch0_base + 0x4108, 0x0)
p.write32(mca_switch0_base + 0x410c, 0xfe)

p.write32(mca_switch1_base + 0x8000, 0x102048)
# bits 0x0000e0 influence clock
#      0x00000f influence sample serialization

# clock
p.write32(0x23b0400d8, 0x06000000) # 48 ksps, zero out for ~96 ksps

p.write32(mca_switch0_base + 0x0600, 0xe) # 0x8 or have zeroed samples, 0x6 or have no clock
p.write32(mca_switch0_base + 0x0604, 0x200) # sensitive in mask 0xf00, any other value disables clock
p.write32(mca_switch0_base + 0x0608, 0x4) # 0x4 or zeroed samples

# toggle the GPIO line driving the speaker-amp IC reset
p.write32(0x23c1002d4, 0x76a02) # invoke reset
p.write32(0x23c1002d4, 0x76a03) # take out of reset


tx_chan.submit(inputf.read(args.bufsize))
tx_chan.enable()
while tx_chan.can_submit():
    tx_chan.submit(inputf.read(args.bufsize))

# accesses to 0x100-sized blocks in the +0x4000 region require 
# the associated enable bit cleared, or they cause SErrors
def mca_switch_unk_disable():
    for off in [0x4000, 0x4100, 0x4300]:
        p.write32(mca_switch0_base + off, 0x0)

def mca_switch_unk_enable():
    for off in [0x4000, 0x4100, 0x4300]:
        p.write32(mca_switch0_base + off, 0x1)

p.write32(mca_switch0_base + 0x4104, 0x2)
mca_switch_unk_enable()


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

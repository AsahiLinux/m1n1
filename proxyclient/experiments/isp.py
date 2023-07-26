#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *

from m1n1.fw.isp_base import ISP
from m1n1.fw.isp.isp_vid import ISPFrameReceiver


isp = ISP(u)
isp.boot()

rcver = ISPFrameReceiver(isp)
rcver.stream()  # Press 'Enter' to exit stream

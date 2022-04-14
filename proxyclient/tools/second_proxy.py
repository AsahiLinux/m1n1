#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
import time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *

p.usb_iodev_vuart_setup(p.iodev_whoami())
p.iodev_set_usage(IODEV.USB_VUART, USAGE.UARTPROXY)

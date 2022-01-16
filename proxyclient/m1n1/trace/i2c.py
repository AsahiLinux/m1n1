# SPDX-License-Identifier: MIT

from ..hv import TraceMode
from ..utils import *
from ..hw import i2c
from . import ADTDevTracer

class I2CTracer(ADTDevTracer):
    REGMAPS = [i2c.I2CRegs]
    NAMES = ["i2c"]

    def __init__(self, hv, devpath, verbose=False):
        super().__init__(hv, devpath, verbose=verbose)
        self.default_dev = I2CDevTracer()
        self.default_dev.i2c_tracer = self

    def init_state(self):
        self.state.txn = []
        self.state.devices = {}

    def w_MTXFIFO(self, mtxfifo):
        if self.state.txn is None:
            self.state.txn = []

        d = mtxfifo.DATA
        if mtxfifo.START:
            self.state.txn += ["S"]
        if mtxfifo.READ:
            self.state.txn += [None] * d
        else:
            self.state.txn.append(d)
        
        if mtxfifo.STOP:
            self.state.txn.append("P")
            self.flush_txn()

    def r_MRXFIFO(self, mrxfifo):
        if mrxfifo.EMPTY:
            self.log(f"Read while FIFO empty")
            return

        if not self.state.txn:
            self.log(f"Stray read: {mrxfifo}")
            return

        try:
            pos = self.state.txn.index(None)
            self.state.txn[pos] = mrxfifo.DATA
        except ValueError:
            self.log(f"Stray read: {mrxfifo}")

        self.flush_txn()

    def flush_txn(self):
        if not self.state.txn:
            return

        if self.state.txn[-1] != "P":
            return

        if not any(i is None for i in self.state.txn):
            self.handle_txn(self.state.txn)
            self.state.txn = None

    def handle_txn(self, txn):
        st = False
        dev = self.default_dev
        read = False
        for i in txn:
            if i == "S":
                st = True
                continue
            if st:
                addr = i >> 1
                dev = self.state.devices.get(addr, self.default_dev)
                read = bool(i & 1)
                dev.start(addr, read=read)
            elif i == "P":
                dev.stop()
            elif read:
                dev.read(i)
            else:
                dev.write(i)
            st = False

    def add_device(self, addr, device):
        device.hv = self.hv
        device.i2c_tracer = self
        self.state.devices[addr] = device

class I2CDevTracer(Reloadable):
    def __init__(self, addr=None):
        self.addr = addr
        self.txn = []

    def log(self, *args, **kwargs):
        self.i2c_tracer.log(*args, **kwargs)

    def start(self, addr, read):
        self.txn.append("S")
        if read:
            self.txn.append(f"{addr:02x}.r")
        else:
            self.txn.append(f"{addr:02x}.w")

    def stop(self):
        self.txn.append("P")
        self.log(f"Txn: {' '.join(self.txn)}")
        self.txn = []

    def read(self, data):
        self.txn.append(f"{data:02x}")

    def write(self, data):
        self.txn.append(f"{data:02x}")

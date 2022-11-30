# SPDX-License-Identifier: MIT

from enum import Enum

from m1n1.trace.i2c import I2CTracer, I2CDevTracer

class HpmTracer(I2CDevTracer):
    class State(Enum):
        UNKNOWN = 0
        REQUEST = 1
        WRITE = 2
        READ = 3

    def __init__(self, addr=128, name=None, verbose=True):
        print(f"CD3217Tracer.__init__(addr={addr}, name={name}, verbose={verbose})")
        super().__init__(addr, name, verbose)
        self.reset()

    def reset(self):
        self.reg = None
        self.state = CD3217Tracer.State.UNKNOWN
        self.length = None
        self.data = []

    def start(self, addr, read):
        if addr != self.addr:
            return

        if self.state == CD3217Tracer.State.UNKNOWN:
            if read:
                self.state = CD3217Tracer.State.READ
            else:
                self.state = CD3217Tracer.State.REQUEST
        elif self.state == CD3217Tracer.State.REQUEST and read:
            pass
        else:
            self.log(f"unexpected state in start(read={read}): state:{self.state} reg:{self.reg} data:{self.data}")

    def stop(self):
        if self.state == CD3217Tracer.State.REQUEST and len(self.data) == 0:
            return

        msg = f"Txn: {self.addr:02x}."
        if self.state == CD3217Tracer.State.REQUEST:
            msg += f"r [{self.reg:02x}]"
        elif self.state == CD3217Tracer.State.WRITE:
            msg += f"w [{self.reg:02x}]"
        elif self.state == CD3217Tracer.State.READ:
            msg += f"r [xx]"
        else:
            self.log(f"unexpected state in stop(): state:{self.state} reg:{self.reg} data:{self.data}")
            self.reset()
            return

        # only for debugging as some mismatches are expected as
        # cd3217 seems to report the register size and not the number
        # of requested bytes (or I2CDevTracer truncates reads).
        #if self.length is not None and self.length > len(self.data):
        #    self.log(f"length {self.length:02x} mismatch received data: {len(self.data):02x}")

        for data in self.data:
            msg += f" {data:02x}"

        self.log(msg)
        self.reset()

    def read(self, data):
        self.data.append(data)

    def write(self, data):
        if self.reg is None:
            self.reg = data
        elif self.length is None:
            self.length = data
            self.state = CD3217Tracer.State.WRITE
        else:
            self.data.append(data)

class CD3217Tracer(HpmTracer):
    def read(self, data):
        if self.length is None:
            self.length = data - 1
        else:
            self.data.append(data)


i2c_tracers = {}

for node in hv.adt["/arm-io"]:
    if not node.name.startswith("i2c"):
        continue

    n = int(node.name[3:])
    bus = I2CTracer(hv, f"/arm-io/{node.name}")

    for mngr_node in node:
        if "compatible" not in mngr_node._properties: # thanks Apple
            continue

        if mngr_node.compatible[0] != "usbc,manager":
            continue

        addr = mngr_node.reg[0] & 0xff
        bus.add_device(addr, HpmTracer(addr=addr, name=mngr_node.name))

        for devnode in mngr_node:

            dcls = {
                "usbc,cd3217": CD3217Tracer,
            }.get(devnode.compatible[0], None)
            if dcls:
                addr = devnode.hpm_iic_addr & 0xff
                bus.add_device(addr, dcls(addr=addr, name=devnode.name))

    if len(bus.state.devices) > 1:
        i2c_tracers[n] = bus

for bus in i2c_tracers.values():
    bus.start()

# SPDX-License-Identifier: MIT
import struct, functools
from dataclasses import dataclass
from enum import IntEnum

from construct.lib import hexundump

from ..asc.base import *
from ...utils import *

from . import ipc
from .dcpep import CallContext

## DCP API manager

class DCPBaseManager:
    def __init__(self, dcpep):
        self.dcpep = dcpep
        self.dcp = dcpep.asc
        dcpep.mgr = self

        self.name_map = {}
        self.tag_map = {}

        self.in_callback = 0

        for k, (cls, v) in ipc.ALL_METHODS.items():
            self.name_map[v.name] = k, v
            self.tag_map[k] = v

    def handle_cb(self, state):
        method = self.tag_map.get(state.tag, None)
        if method is None:
            raise Exception(f"Unknown callback {state.tag}")

        func = getattr(self, method.name, None)

        if func is None:
            raise Exception(f"Unimplemented callback {method!s} [{state.tag}]")

        self.in_callback += 1
        try:
            retval = method.callback(func, state.in_data)
        except Exception as e:
            print(f"Exception in callback {method.name}")
            raise
        self.in_callback -= 1
        return retval

    def __getattr__(self, attr):
        tag, method = self.name_map.get(attr, (None, None))
        if method is None or tag.startswith("D"):
            raise AttributeError(f"Unknown method {attr}")

        out_len = method.out_struct.sizeof()
        if self.in_callback:
            ctx = CallContext.CB
        else:
            ctx = CallContext.CMD
        rpc = functools.partial(self.dcpep.ch_cmd.call, ctx, tag, out_len=out_len)
        return functools.partial(method.call, rpc)

class DCPManager(DCPBaseManager):
    def __init__(self, dcpep):
        super().__init__(dcpep)

        self.iomfb_prop = {}
        self.dcpav_prop = {}
        self.service_prop = {}
        self.pr_prop = {}

        self.swaps = 0
        self.frame = 0

        self.mapid = 0

    ## IOMobileFramebufferAP methods

    def find_swap_function_gated(self):
        pass

    def create_provider_service(self):
        return True

    def create_product_service(self):
        return True

    def create_PMU_service(self):
        return True

    def create_iomfb_service(self):
        return True

    def create_backlight_service(self):
        return False

    def setProperty(self, key, value):
        self.iomfb_prop[key] = value
        print(f"setProperty({key} = {value!r})")
        return True

    setProperty_dict = setProperty_int = setProperty_bool = setProperty_str = setProperty

    def swap_complete_ap_gated(self, arg0, arg1, arg2, arg3, arg4):
        print(f"swap_complete_ap_gated({arg0}, {arg1}, ..., ..., {arg4}")
        chexdump(arg2)
        chexdump(arg3)
        self.swaps += 1
        self.frame = arg0

    def swap_complete_intent_gated(self, frame, arg1, arg2, width, height):
        print(f"swap_complete_intent_gated({frame}, {arg1}, {arg2}, {width}, {height}")
        self.swaps += 1
        self.frame = frame

    ## UPPipeAP_H13P methods

    def did_boot_signal(self):
        return True

    def did_power_on_signal(self):
        return True

    def will_power_off_signal(self):
        return

    def rt_bandwidth_setup_ap(self, config):
        print("rt_bandwidth_setup_ap(...)")
        config.val = {"data":unhex("""
          6C 43 6C 6F 63 6B 00 44 14 80 73 3B 02 00 00 00
          00 C0 C3 3B 02 00 00 00 00 00 00 00 02 00 00 00
          00 00 00 00 90 26 FB 43 FF FF FF FF 04 00 00 00
          00 00 00 00 65 04 00 00 00 00 00 00
          """)}
    ## UnifiedPipeline2 methods

    def match_pmu_service(self):
        pass

    def create_provider_service(self):
        return True

    def read_edt_data(self, key, count, value):
        return False

    def UNK_get_some_field(self):
        return 0

    def start_hardware_boot(self):
        self.set_create_DFB()
        self.do_create_default_frame_buffer()
        self.setup_video_limits()
        self.flush_supportsPower(True)
        self.late_init_signal()
        self.setDisplayRefreshProperties()
        return True

    def setDCPAVPropStart(self, length):
        print(f"setDCPAVPropStart({length:#x})")
        return True

    def setDCPAVPropChunk(self, data, offset, length):
        print(f"setDCPAVPropChunk(..., {offset:#x}, {length:#x})")
        return True

    def setDCPAVPropEnd(self, key):
        print(f"setDCPAVPropEnd({key!r})")
        return True

    def set_boolean_property(self, key, value):
        print(f"set {key!r} = {value}")

    def removeProperty(self, key):
        print(f"removeProperty({key!r})")

    def powerstate_notify(self, unk1, unk2):
        print(f"powerstate_notify({unk1}, {unk2})")

    def powerUpDART(self, unk):
        print(f"powerUpDART({unk})")
        return 0

    def is_waking_from_hibernate(self):
        return False

    ## UPPipe2 methods

    def match_pmu_service_2(self):
        return True

    def match_backlight_service(self):
        return True

    def map_buf(self, buf, out1, out2, unkBool):
        print(f"map buf {buf}, {unkBool}")
        out1.val = 0xfffffe1667b9d0e0
        out2.val = 0
        return 0

    ## ServiceRelay methods

    def sr_setProperty(self, obj, key, value):
        self.service_prop.setdefault(obj, {})[key] = value
        print(f"sr_setProperty({obj}/{key} = {value!r})")
        return True

    def sr_getClockFrequency(self, obj, arg):
        print(f"sr_getClockFrequency({obj}, {arg})")
        return 533333328

    sr_setProperty_dict = sr_setProperty_int = sr_setProperty_bool = sr_setProperty_str = sr_setProperty

    def sr_get_uint_prop(self, obj, key, value):
        value.val = 0
        return False

    def sr_mapDeviceMemoryWithIndex(self, obj, index, flags, addr, length):
        assert obj == "PROV"
        addr.val, length.val = self.dcp.u.adt["/arm-io/disp0"].get_reg(index)
        print(f"sr_mapDeviceMemoryWithIndex({obj}, {index}, {flags}, {addr.val:#x}, {length.val:#x})")
        return 0

    ## PropRelay methods

    def pr_publish(self, prop_id, value):
        self.pr_prop[prop_id] = value
        print(f"pr_publish({prop_id}, {value!r})")

    ## MemDescRelay methods:

    def allocate_buffer(self, unk0, size, unk1, paddr, dva, dvasize):
        print(f"allocate_buffer({unk0}, {size}, {unk1})")

        dvasize.val = align_up(size, 4096)
        paddr.val = self.dcp.u.memalign(0x4000, size)
        dva.val = self.dcp.dart.iomap(0, paddr.val, size)

        self.mapid += 1
        print(f"Allocating {self.mapid} as {hex(paddr.val)} / {hex(dva.val)}")
        return self.mapid

    def map_physical(self, paddr, size, flags, dva, dvasize):
        dvasize.val = align_up(size, 4096)
        dva.val = self.dcp.dart.iomap(0, paddr, size)
        print(f"map_physical({paddr:#x}, {size:#x}, {flags}, {dva.val:#x}, {dvasize.val:#x})")

        self.mapid += 1
        return self.mapid


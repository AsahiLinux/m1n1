# SPDX-License-Identifier: MIT
from ...utils import *

from ..asc import StandardASC
from .aopep import *
from .base import AOPBase

class AOPClient(StandardASC, AOPBase):
    ENDPOINTS = {
        0x20: AOPSPUAppEndpoint,
        0x21: AOPAccelEndpoint,
        0x22: AOPGyroEndpoint,
        0x24: AOPALSEndpoint,
        0x25: AOPWakehintEndpoint,
        0x26: AOPUNK26Endpoint,
        0x27: AOPAudioEndpoint,
        0x28: AOPVoiceTriggerEndpoint,
    }
    def __init__(self, u, dev_path, dart=None):
        node = u.adt[dev_path]
        asc_base = node.get_reg(0)[0]
        AOPBase.__init__(self, u)
        super().__init__(u, asc_base, dart)
        self.dart = dart

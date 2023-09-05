# SPDX-License-Identifier: MIT
from ...utils import *

from ..asc import StandardASC
from .dcpep import DCPEndpoint
from ..afk.epic import *

class DCPClient(StandardASC):
    ENDPOINTS = {
        0x20: AFKSystemEndpoint,
        0x37: DCPEndpoint,
    }

    def __init__(self, u, asc_base, dart=None, disp_dart=None):
        super().__init__(u, asc_base, dart)
        self.disp_dart = disp_dart

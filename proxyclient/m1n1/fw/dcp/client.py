# SPDX-License-Identifier: MIT
from ...utils import *

from ..asc import StandardASC
from .dcpep import DCPEndpoint

class DCPClient(StandardASC):
    ENDPOINTS = {
        0x37: DCPEndpoint,
    }

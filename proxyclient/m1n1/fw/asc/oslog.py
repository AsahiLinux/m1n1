# SPDX-License-Identifier: MIT
from .base import *
from ...utils import *

## OSLog endpoint

class OSLogMessage(Register64):
    TYPE        = 63, 56

class OSLog_Init(OSLogMessage):
    TYPE        = 63, 56, Constant(1)
    UNK         = 51, 0

class OSLog_Ack(OSLogMessage):
    TYPE        = 63, 56, Constant(3)

class ASCOSLogEndpoint(ASCBaseEndpoint):
    BASE_MESSAGE = OSLogMessage
    SHORT = "oslog"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started = False

    @msg_handler(1, OSLog_Init)
    def Init(self, msg):
        self.log(f"oslog init: {msg.UNK:#x}")
        self.send(OSLog_Ack())
        self.started = True
        return True

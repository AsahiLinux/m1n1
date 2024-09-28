# SPDX-License-Identifier: MIT
import time
from construct import *
from ..afk.epic import *
from .ipc import *

# spuapp
class AOPSPUAppService(EPICService):
    NAME = "SPUApp"
    SHORT = "spuapp"

class AOPSPUAppI2CService(EPICService):
    NAME = "i2c"
    SHORT = "i2c"

class AOPSPUAppEndpoint(EPICEndpoint):
    SHORT = "spuapp"
    SERVICES = [
        AOPSPUAppService,
        AOPSPUAppI2CService,
    ]

# accel
class AOPAccelService(EPICService):
    NAME = "accel"
    SHORT = "accel"

class AOPAccelEndpoint(EPICEndpoint):
    SHORT = "accel"
    SERVICES = [
        AOPAccelService,
    ]

# gyro
class AOPGyroService(EPICService):
    NAME = "gyro"
    SHORT = "gyro"

class AOPGyroEndpoint(EPICEndpoint):
    SHORT = "gyro"
    SERVICES = [
        AOPGyroService,
    ]

    def start_queues(self):
        pass  # don't init gyro ep (we don't have one)

# als
class AOPALSService(EPICService):
    NAME = "als"
    SHORT = "als"

    @report_handler(0xc4, ALSLuxReport)
    def handle_lux(self, seq, fd, rep):
        self.log(rep)
        return True

class AOPALSEndpoint(EPICEndpoint):
    SHORT = "als"
    SERVICES = [
        AOPALSService,
    ]

    def send_notify(self, call, chan="als"):
        return super(AOPALSEndpoint, self).send_notify(chan, call)

    def send_roundtrip(self, call, chan="als"):
        return super(AOPALSEndpoint, self).send_roundtrip(chan, call)

    def send_cmd(self, call, chan="als"):
        return super(AOPALSEndpoint, self).send_cmd(chan, call)

# wakehint
class AOPWakehintService(EPICService):
    NAME = "wakehint"
    SHORT = "wakehint"

class AOPWakehintEndpoint(EPICEndpoint):
    SHORT = "wakehint"
    SERVICES = [
        AOPWakehintService,
    ]

# unk26
class AOPUNK26Service(EPICService):
    NAME = "unk26"
    SHORT = "unk26"

class AOPUNK26Endpoint(EPICEndpoint):
    SHORT = "unk26"
    SERVICES = [
        AOPUNK26Service,
    ]

# audio
class AOPAudioService(EPICService):
    NAME = "aop-audio"
    SHORT = "audio"

class AOPAudioEndpoint(EPICEndpoint):
    SHORT = "audio"
    SERVICES = [
        AOPAudioService,
    ]

    def send_ipc(self, data, chan="aop-audio", **kwargs):
        return super(AOPAudioEndpoint, self).send_ipc(data, **kwargs)

    def send_notify(self, call, chan="aop-audio", **kwargs):
        return super(AOPAudioEndpoint, self).send_notify(chan, call, **kwargs)

    def send_roundtrip(self, call, chan="aop-audio", **kwargs):
        return super(AOPAudioEndpoint, self).send_roundtrip(chan, call, **kwargs)

    def send_cmd(self, call, chan="aop-audio", **kwargs):
        return super(AOPAudioEndpoint, self).send_cmd(chan, call, **kwargs)

    def send_notifycmd(self, type, data, chan="aop-audio", **kwargs):
        return super(AOPAudioEndpoint, self).send_notifycmd(chan, type, data, **kwargs)

class AOPVoiceTriggerService(EPICService):
    NAME = "aop-voicetrigger"
    SHORT = "voicetrigger"

class AOPVoiceTriggerEndpoint(EPICEndpoint):
    SHORT = "voicetrigger"
    SERVICES = [
        AOPVoiceTriggerService,
    ]

    def send_notify(self, call, chan="aop-voicetrigger", **kwargs):
        return super(AOPVoiceTriggerEndpoint, self).send_notify(chan, call, **kwargs)

    def send_roundtrip(self, call, chan="aop-voicetrigger", **kwargs):
        return super(AOPVoiceTriggerEndpoint, self).send_roundtrip(chan, call, **kwargs)

    def send_cmd(self, type, data, chan="aop-voicetrigger", **kwargs):
        return super(AOPVoiceTriggerEndpoint, self).send_cmd(chan, type, data, **kwargs)

    def send_notifycmd(self, type, data, chan="aop-voicetrigger", **kwargs):
        return super(AOPVoiceTriggerEndpoint, self).send_notifycmd(chan, type, data, **kwargs)

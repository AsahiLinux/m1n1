# SPDX-License-Identifier: MIT
import datetime

from m1n1.constructutils import show_struct_trace, Ver
from m1n1.utils import *

Ver.set_version(hv.u)

from m1n1.trace.agx import AGXTracer
AGXTracer = AGXTracer._reloadcls(True)

agx_tracer = AGXTracer(hv, "/arm-io/gfx-asc", verbose=1)

agx_tracer.pause_after_init = True
agx_tracer.trace_usermap = False
agx_tracer.trace_kernmap = False
agx_tracer.redump = True

agx_tracer.start()

def resume_tracing(ctx):
    fname = f"{datetime.datetime.now().isoformat()}.log"
    hv.set_logfile(open(f"gfxlogs/{fname}", "a"))
    agx_tracer.start()
    agx_tracer.resume()
    return True

def pause_tracing(ctx):
    agx_tracer.pause()
    agx_tracer.stop()
    hv.set_logfile(None)
    return True

hv.add_hvcall(100, resume_tracing)
hv.add_hvcall(101, pause_tracing)

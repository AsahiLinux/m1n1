from m1n1.trace.isp import ISPTracer

hv.log('ISP: Registering ISP ASC tracer...')
isp_asc_tracer = ISPTracer(hv, "/arm-io/isp", "/arm-io/dart-isp", verbose=4)
isp_asc_tracer.start()
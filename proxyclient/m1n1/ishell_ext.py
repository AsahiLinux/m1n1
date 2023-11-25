# SPDX-License-Identifier: MIT
# Extension for ipython to handle monitor polling
# and simd context after each executed line


class PostExecuteWatcher(object):
    def __init__(self, ip):
        self.shell = ip

    def post_execute(self):
        mon = self.shell.user_ns.get("mon", None)
        if mon != None:
            try:
                mon.poll()
            except Exception as e:
                print(f"mon.poll() failed: {e!r}")
        u = self.shell.user_ns.get("u", None)
        if u != None:
            u.push_simd()


def load_ipython_extension(ip):
    pew = PostExecuteWatcher(ip)
    ip.events.register("post_execute", pew.post_execute)

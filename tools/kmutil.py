#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

from base64 import b64encode
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCRIPT_HEADER = b'''#!/bin/sh
#######################################################################
# kmutil configure-boot script with embedded m1n1.bin for easy setup
#
# Preparations on the host:
#     make
#     ./tools/kmutil.py
#
# Usage on the target:
#     sh <(curl HOST:8000)
#
# This script can not be piped into the shell since it uses stdin.
#
#######################################################################

set -e

boot_disk=$(bless --getboot)
system_dir=$(diskutil info -plist ${boot_disk} | plutil -extract MountPoint raw -)

"${system_dir}"/usr/bin/uudecode <<EOF_M1N1
begin-base64 644 m1n1.bin
'''

SCRIPT_TRAILER = b'''====
EOF_M1N1

# TODO: ensure this is booted into 1TR and check boot policy, see step2.sh from asahi-installer

echo
echo "Set m1n1.bin as custom boot object for \"${system_dir}\"?"
echo "Use control-c to cancel."
echo
read

while ! kmutil configure-boot -c m1n1.bin --raw --entry-point 2048 --lowest-virtual-address 0 -v "${system_dir}"; do
    echo
    echo "kmutil failed. Did you mistype your password?"
    echo "Press enter to try again."
    read
done

echo
echo "Installation complete! Press enter to reboot."
read

reboot
'''


class KmutilHTTPRequestHandler(BaseHTTPRequestHandler):

    def __init__(self, *args, payload, **kwargs):
        self.payload = payload
        super().__init__(*args, **kwargs)

    def do_GET(self):
        try:
            with self.payload.open("rb") as f:
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(SCRIPT_HEADER)
                while True:
                    payload = f.read(45)
                    if not payload:
                        break
                    self.wfile.write(b64encode(payload) + b'\n')
                self.wfile.write(SCRIPT_TRAILER)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()


if __name__ == '__main__':
    import argparse, contextlib, pathlib, socket

    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bind', default='::', metavar='ADDRESS',
                        help='bind to this address '
                             '(default: all interfaces)')
    parser.add_argument('-p', '--port', default=8000, type=int,
                        help='bind to this port '
                             '(default: %(default)s)')
    parser.add_argument('payload', default='build/m1n1.bin', type=pathlib.Path, nargs='?',
                        help='Serve payload as bputil self-install script '
                             '(default: %(default)s)')
    args = parser.parse_args()


    # ensure dual-stack is not disabled; ref #38907
    class DualStackServerMixin:
        address_family = socket.AF_INET6

        def server_bind(self):
            # suppress exception when protocol is IPv4
            with contextlib.suppress(Exception):
                self.socket.setsockopt(
                    socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            return super().server_bind()

        def finish_request(self, request, client_address):
            self.RequestHandlerClass(request, client_address, self,
                                     payload=args.payload)

    class HTTPDualStackServer(DualStackServerMixin, ThreadingHTTPServer):
        pass

    server = HTTPDualStackServer((args.bind, args.port), KmutilHTTPRequestHandler)
    server.serve_forever()

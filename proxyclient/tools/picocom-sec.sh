#!/bin/sh
#
# Secondary UART device name exposed when m1n1 boots is /dev/m1n1-sec on
# Linux host and /dev/cu.usbmodemP_03 on macOS host
#
DEFAULT_SECDEV=/dev/m1n1-sec
PLATFORM_NAME=$(uname)

case "${PLATFORM_NAME}" in
Darwin)
    SECDEV=/dev/cu.usbmodemP_03 ;;
*)
    SECDEV="$DEFAULT_SECDEV" ;;
esac

# The secondary UART device shows up when m1n1 boots on the tethered machine
echo "Waiting for UART device file '$SECDEV' to appear (Ctrl+C to abort)..."

while true; do
    while [ ! -e $SECDEV ] ; do sleep 1 ; done
    picocom --omap crlf --imap lfcrlf -b 500000 $SECDEV
    sleep 1
done

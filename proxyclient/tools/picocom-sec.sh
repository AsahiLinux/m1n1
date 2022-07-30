#!/bin/sh

while true; do
    while [ ! -e /dev/m1n1-sec ]; do sleep 1; done
    picocom --omap crlf --imap lfcrlf -b 500000 /dev/m1n1-sec
    sleep 1
done

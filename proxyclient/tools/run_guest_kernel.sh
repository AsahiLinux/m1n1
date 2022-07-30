#!/bin/sh
set -e

if [ ! -d "$1" ]; then
    echo "Usage:"
    echo "  $0 <kernel build root> [kernel commandline] [initramfs]"
    exit 1
fi

kernel_base="$(realpath "$1")"
args="$2"
initramfs=""
if [ ! -z "$3" ]; then
    initramfs="$(realpath "$3")"
fi

cd "$(dirname "$0")"

echo "Creating m1n1+kernel image"
cp ../../build/m1n1.bin /tmp/m1n1-linux.bin
if [ ! -z "$args" ]; then
    echo "chosen.bootargs=$args" >>/tmp/m1n1-linux.bin
fi

cat "$kernel_base"/arch/arm64/boot/dts/apple/*.dtb "$kernel_base"/arch/arm64/boot/Image.gz >>/tmp/m1n1-linux.bin
if [ ! -z "$initramfs" ]; then
    cat "$initramfs" >>/tmp/m1n1-linux.bin
fi
echo "Chainloading to updated m1n1..."
python chainload.py -r ../../build/m1n1.bin
echo "Starting guest..."
exec python run_guest.py -c "load_system_map('$kernel_base/System.map')" -r /tmp/m1n1-linux.bin

#!/bin/sh
set -e

: ${TMPDIR:=$XDG_RUNTIME_DIR}
: ${TMPDIR:=/tmp}

if [ "$1" == "-k" ]; then
    kernel="$(realpath "$2")"
    shift 2
fi

if [ ! -d "$1" ]; then
    echo "Usage:"
    echo "  $0 <kernel build root> [kernel commandline] [initramfs]"
    exit 1
fi

kernel_base="$(realpath "$1")"
args="$2"
initramfs=""
shift 2

if [ "$1" == "--" ]; then
	shift
elif [ -n "$1" ]; then
    initramfs="$(realpath "$1")"
    shift
fi

if [ -z "$kernel" ]; then
    kernel="$kernel_base"/arch/arm64/boot/Image.gz
fi

base="$(dirname "$0")"

echo "Creating m1n1+kernel image"
cp "$base"/../../build/m1n1.bin "$TMPDIR/m1n1-linux.bin"
if [ -n "$args" ]; then
    echo "chosen.bootargs=$args" >>"$TMPDIR/m1n1-linux.bin"
fi

cat "$kernel_base"/arch/arm64/boot/dts/apple/*.dtb >>"$TMPDIR/m1n1-linux.bin"
if [[ "$kernel" == *.gz ]]; then
    cat "$kernel" >>"$TMPDIR/m1n1-linux.bin"
else
    gzip -c <"$kernel" >>"$TMPDIR/m1n1-linux.bin"
fi

if [ -n "$initramfs" ]; then
    cat "$initramfs" >>"$TMPDIR/m1n1-linux.bin"
fi

echo "Chainloading to updated m1n1..."
python "$base"/chainload.py -r "$base"/../../build/m1n1.bin
echo "Starting guest..."
exec python "$base"/run_guest.py \
    -c "load_system_map('$kernel_base/System.map')" "$@" \
    -r "$TMPDIR/m1n1-linux.bin"

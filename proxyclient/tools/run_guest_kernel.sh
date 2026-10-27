#!/bin/sh
set -e

: ${TMPDIR:=$XDG_RUNTIME_DIR}
: ${TMPDIR:=/tmp}

show_usage() {
    echo "Usage:"
    echo "  $0 OPTIONS <kernel build root> [kernel commandline] [initramfs]"
    echo
    echo "    -k IMAGE             Use $IMAGE as kernel image name (full path)"
    echo "    -m                   Append Linux' modules-cpio-pkg to the initramfs"
    echo "    -e ESP_PART_UUID     Use $ESP_PART_UUID as EFI system partition for fw loading"
    echo "    -h                   Print this usage information"
}

while [[ -n "${1}" ]]; do
    case "${1}" in
    -k|--kernel)
        kernel="$(realpath "${2}")"
        shift 2
        ;;
    -m|--modules-cpio-pkg)
        modules_initramfs=1
        shift 1
        ;;
    -e|--efi)
        esp="${2}"
        shift 2
        ;;
    -h|--help)
        show_usage
        exit 1
        ;;
    *)
        break
        ;;
    esac
done

if [ ! -d "$1" ]; then
    show_usage
    exit 1
fi

kernel_base="$(realpath "$1")"
args="$2"
initramfs=""
shift 2

if [ "$1" == "--" ]; then
    if [ -n $modules_initramfs ]; then
        echo "-m/--modules-cpio-pkg requires a base initramfs"
        exit 1
    fi
    shift
elif [ -n "$1" ]; then
    initramfs="$(realpath "$1")"
    shift
fi

if [ -z "$kernel" ]; then
    kernel="$kernel_base"/arch/arm64/boot/Image.gz
fi

if [ -n "${modules_initramfs}" ]; then
    kernel_release=$(make -s -C "${kernel_base}" kernelrelease)
    modules_initramfs="$(realpath "${kernel_base}"/modules-${kernel_release}-arm64.cpio)"
    if [ -f "${modules_initramfs}.gz" -a "${modules_initramfs}.gz" -nt "${modules_initramfs}" ]; then
        modules_initramfs="${modules_initramfs}.gz"
    fi
    if [ "${modules_initramfs}" -ot "${kernel}" ]; then
        echo "WARN: ${modules_initramfs} is older than ${kernel}"
    fi
fi

base="$(dirname "$0")"

echo "Creating m1n1+kernel image"
cp "$base"/../../build/m1n1.bin "$TMPDIR/m1n1-linux.bin"
if [ -n "$args" ]; then
    echo "chosen.bootargs=$args" >>"$TMPDIR/m1n1-linux.bin"
fi
if [ -n "${esp}" ]; then
    echo "chosen.asahi,efi-system-partition=${esp}" >>"$TMPDIR/m1n1-linux.bin"
fi

cat "$kernel_base"/arch/arm64/boot/dts/apple/*.dtb >>"$TMPDIR/m1n1-linux.bin"
if [[ "$kernel" == *.gz ]]; then
    cat "$kernel" >>"$TMPDIR/m1n1-linux.bin"
else
    gzip -c <"$kernel" >>"$TMPDIR/m1n1-linux.bin"
fi

if [ -n "$initramfs" ]; then
    initramfs_size=$(stat --printf='%s' "$initramfs")
    if [ -n "${modules_initramfs}" ]; then
        initramfs_size="${initramfs_size} + $(stat --printf='%s' "${modules_initramfs}")"
    fi

    python3 - << EOF >>"$TMPDIR/m1n1-linux.bin"
import os, sys

magic = b'm1n1_initramfs'
size = int(${initramfs_size}).to_bytes(4, byteorder='little')
os.write(sys.stdout.fileno(), magic + size)
EOF

    cat "$initramfs" >>"$TMPDIR/m1n1-linux.bin"
    if [ -n "${modules_initramfs}" ]; then
        echo "Appending modules-cpio-pkg ${modules_initramfs}"
        cat "${modules_initramfs}" >>"$TMPDIR/m1n1-linux.bin"
    fi
fi

echo "Chainloading to updated m1n1..."
python3 "$base"/chainload.py -r "$base"/../../build/m1n1.bin
echo "Starting guest..."
exec python3 "$base"/run_guest.py \
    -c "load_system_map('$kernel_base/System.map')" "$@" \
    -r "$TMPDIR/m1n1-linux.bin"

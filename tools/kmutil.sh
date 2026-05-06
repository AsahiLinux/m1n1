#!/bin/sh
#######################################################################
# kmutil configure-boot script with embedded m1n1.bin for easy setup
#
# host dependencies: uuencode (sharutils)
#
# Preparations on the host:
#     make build/kmutil && python3 -m http.server --directory build
#
# Usage on the target:
#     sh <(curl HOST:8000/kmutil)
#
# This script can not be piped into the shell since it uses stdin.
#
#######################################################################

set -e

uudecode <<EOF_M1N1
UUENCODED_DATA # replaced with uuencoded m1n1.bin by make build/kmutil
EOF_M1N1

boot_disk=$(bless --getboot)
system_dir=$(diskutil info -plist ${boot_disk} | plutil -extract MountPoint raw -)

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

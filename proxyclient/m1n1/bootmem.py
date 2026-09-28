# SPDX-License-Identifier: MIT
import struct
from m1n1.utils import align

BOOT_BLOBS = (
    "SEPFW", "SEPPatches", "uStuff", "preoslog", "RTBuddySeg", "RAMDisk",
    "SPTMDebug", "ExclaveOSIntegrityCatalog", "ExclaveOSTrustCache", "TrustCache",
)

def find_boot_blobs(properties, names, base):
    blobs = []
    end = align(base)
    for name in names:
        value = properties.get(name)
        if value is None:
            continue
        src, size = value
        if (src, size) == (0xffffffffffffffff, 0xffffffffffffffff):
            continue
        if size == 0:
            continue
        blobs.append((name, src, size, end))
        end += size
        end = align(end)
    return blobs, end

def copy_boot_blobs(p, blobs):
    for name, src, size, dst in blobs:
        print(f"Copying {name:30}: 0x{src:x}..0x{src + size:x} -> 0x{dst:x} (0x{size:x} bytes)")
        p.memcpy8(dst, src, size)

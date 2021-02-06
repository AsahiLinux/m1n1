/* SPDX-License-Identifier: MIT */

#include <assert.h>

#include "payload.h"
#include "heapblock.h"
#include "kboot.h"
#include "smp.h"
#include "utils.h"

#include "libfdt/libfdt.h"
#include "minilzlib/minlzma.h"
#include "tinf/tinf.h"

// Kernels must be 2MB aligned
#define KERNEL_ALIGN (2 << 20)

const u8 gz_magic[] = {0x1f, 0x8b};
const u8 xz_magic[] = {0xfd, '7', 'z', 'X', 'Z', 0x00};
const u8 fdt_magic[] = {0xd0, 0x0d, 0xfe, 0xed};
const u8 kernel_magic[] = {'A', 'R', 'M', 0x64};   // at 0x38
const u8 cpio_magic[] = {'0', '7', '0', '7', '0'}; // '1' or '2' next
const u8 empty[] = {0, 0, 0, 0};

struct kernel_header *kernel = NULL;
void *fdt = NULL;

static void *load_one_payload(void *start, size_t size);

static void finalize_uncompression(void *dest, size_t dest_len)
{
    // Actually reserve the space. malloc is safe after this, but...
    assert(dest == heapblock_alloc_aligned(dest_len, KERNEL_ALIGN));

    void *end = ((u8 *)dest) + dest_len;
    void *next = load_one_payload(dest, dest_len);
    assert(!next || next >= dest);

    // If the payload needs padding, we need to reserve more, so it better have not used
    // malloc either.
    if (next > end) {
        // Explicitly *un*aligned or it'll fail this assert, since 64b alignment is the default
        assert(end == heapblock_alloc_aligned((u8 *)next - (u8 *)end, 1));
    }
}

static void *decompress_gz(void *p, size_t size)
{
    unsigned int source_len = size, dest_len = 1 << 30; // 1 GiB should be enough hopefully

    // Start at the end of the heap area, no allocation yet. The following code must not use
    // malloc or heapblock, until finalize_uncompression is called.
    void *dest = heapblock_alloc_aligned(0, KERNEL_ALIGN);

    printf("Uncompressing... ");
    int ret = tinf_gzip_uncompress(dest, &dest_len, p, &source_len);

    if (ret != TINF_OK) {
        printf("Error %d\n", ret);
        return NULL;
    }

    printf("%d bytes uncompressed to %d bytes\n", source_len, dest_len);

    finalize_uncompression(dest, dest_len);

    return ((u8 *)p) + source_len;
}

static void *decompress_xz(void *p, size_t size)
{
    uint32_t source_len = size, dest_len = 1 << 30; // 1 GiB should be enough hopefully

    // Start at the end of the heap area, no allocation yet. The following code must not use
    // malloc or heapblock, until finalize_uncompression is called.
    void *dest = heapblock_alloc_aligned(0, KERNEL_ALIGN);

    printf("Uncompressing... ");
    int ret = XzDecode(p, &source_len, dest, &dest_len);

    if (!ret) {
        printf("XZ decode failed\n");
        return NULL;
    }

    printf("%d bytes uncompressed to %d bytes\n", source_len, dest_len);

    finalize_uncompression(dest, dest_len);

    return ((u8 *)p) + source_len;
}

static void *load_fdt(void *p, size_t size)
{
    fdt = p;
    assert(!size || size == fdt_totalsize(fdt));
    return ((u8 *)p) + fdt_totalsize(fdt);
}

static void *load_cpio(void *p, size_t size)
{
    if (!size) {
        // We could handle this, but who uses uncompressed initramfs?
        printf("Uncompressed cpio archives not supported\n");
        return NULL;
    }

    kboot_set_initrd(p, size);
    return ((u8 *)p) + size;
}

static void *load_kernel(void *p, size_t size)
{
    kernel = p;

    assert(size <= kernel->image_size);

    // If this is an in-line kernel, it's probably not aligned, so we need to make a copy
    if (((u64)kernel) & (KERNEL_ALIGN - 1)) {
        void *new_addr = heapblock_alloc_aligned(kernel->image_size, KERNEL_ALIGN);
        memcpy(new_addr, kernel, size ? size : kernel->image_size);
        kernel = new_addr;
    }

    /*
     * Kernel blobs unfortunately do not have an accurate file size header, so
     * this will fail for in-line payloads. However, conversely, this is required for
     * compressed payloads, in order to allocate padding that the kernel needs, which will be
     * beyond the end of the compressed data. So if we know the input size, tell the caller
     * about the true image size; otherwise don't.
     */
    if (size) {
        return ((u8 *)p) + kernel->image_size;
    } else {
        return NULL;
    }
}

static void *load_one_payload(void *start, size_t size)
{
    u8 *p = start;

    if (!start)
        return NULL;

    if (!memcmp(p, gz_magic, sizeof gz_magic)) {
        printf("Found a gzip compressed payload at %p\n", p);
        return decompress_gz(p, size);
    } else if (!memcmp(p, xz_magic, sizeof xz_magic)) {
        printf("Found an XZ compressed payload at %p\n", p);
        return decompress_xz(p, size);
    } else if (!memcmp(p, fdt_magic, sizeof fdt_magic)) {
        printf("Found a devicetree at %p\n", p);
        return load_fdt(p, size);
    } else if (!memcmp(p, cpio_magic, sizeof cpio_magic)) {
        printf("Found a cpio initramfs at %p\n", p);
        return load_cpio(p, size);
    } else if (!memcmp(p + 0x38, kernel_magic, sizeof kernel_magic)) {
        printf("Found a kernel at %p\n", p);
        return load_kernel(p, size);
    } else if (!memcmp(p, empty, sizeof empty)) {
        printf("No more payloads at %p\n", p);
        return NULL;
    } else {
        printf("Unknown payload at %p (magic: %02x%02x%02x%02x)\n", p, p[0], p[1], p[2], p[3]);
        return NULL;
    }
}

void payload_run(void)
{
    void *p = _payload_start;

    while (p)
        p = load_one_payload(p, 0);

    if (kernel && fdt) {
        smp_start_secondaries();

        if (kboot_prepare_dt(fdt)) {
            printf("Failed to prepare FDT!");
            return;
        }

        kboot_boot(kernel);
        printf("Failed to boot kernel!");
    }
}

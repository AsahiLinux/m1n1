/* SPDX-License-Identifier: MIT */

#include "assert.h"
#include "heapblock.h"
#include "types.h"
#include "utils.h"
#include "xnuboot.h"

/*
 * This is a non-freeing allocator, used as a backend for malloc and for uncompressing data.
 *
 * Allocating 0 bytes is allowed, and guarantees "infinite" (until the end of RAM) space is
 * available at the returned pointer as long as no other malloc/heapblock calls occur, which is
 * useful as a buffer for unknown-length uncompressed data. A subsequent call with a size will then
 * actually reserve the block.
 */

static void *heap_base;

void heapblock_init(void)
{
    void *top_of_kernel_data = (void *)cur_boot_args.top_of_kernel_data;
    void *payload_end = _payload_end;

    if (payload_end > top_of_kernel_data)
        heap_base = payload_end; // Chainloaded, we are last in RAM
    else
        heap_base = top_of_kernel_data; // Loaded by iBoot, there is data after us in RAM

    heapblock_alloc(0); // align base

    printf("Heap base: %p\n", heap_base);
}

void *heapblock_alloc(size_t size)
{
    return heapblock_alloc_aligned(size, 64);
}

void *heapblock_alloc_aligned(size_t size, size_t align)
{
    assert((align & (align - 1)) == 0);

    uintptr_t block = (((uintptr_t)heap_base) + align - 1) & ~(align - 1);
    heap_base = (void *)(block + size);

    return (void *)block;
}

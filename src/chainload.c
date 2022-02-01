/* SPDX-License-Identifier: MIT */

#include "chainload.h"
#include "heapblock.h"
#include "payload.h"
#include "utils.h"

int do_chainload(void) {
    size_t buf_size = prepare_chainload();
    if (buf_size == 0) {
	return 1;
    }
    void *buf = heapblock_alloc(0);
    if (chainload_get_bytes(buf, buf_size)) {
	heapblock_alloc(buf_size);
	printf(buf);
	return 0;
    } else {
	printf("Failed to load m1n1 upgrade from ssd.");
	return 1;
    }
}

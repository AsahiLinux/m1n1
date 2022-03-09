/* SPDX-License-Identifier: MIT */

#ifndef KBOOT_H
#define KBOOT_H

#include "types.h"

struct kernel_header {
    u32 code[2];     /* Executable code */
    u64 text_offset; /* Image load offset, little endian */
    u64 image_size;  /* Effective Image size, little endian */
    u64 flags;       /* kernel flags, little endian */
    u64 res2;        /* reserved */
    u64 res3;        /* reserved */
    u64 res4;        /* reserved */
    u32 magic;       /* Magic number, little endian, "ARM\x64" */
    u32 res5;        /* reserved (used for PE COFF offset) */
};

void kboot_set_initrd(void *start, size_t size);
int kboot_set_chosen(const char *name, const char *value);
int kboot_prepare_dt(void *fdt);
int kboot_boot(void *kernel);

#endif

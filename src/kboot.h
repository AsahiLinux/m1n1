/* SPDX-License-Identifier: MIT */

#ifndef KBOOT_H
#define KBOOT_H

void kboot_set_initrd(void *start, size_t size);
void kboot_set_bootargs(const char *ba);
int kboot_prepare_dt(void *fdt);
int kboot_boot(void *kernel);

#endif

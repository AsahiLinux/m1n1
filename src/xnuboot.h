/* SPDX-License-Identifier: MIT */

#ifndef XNUBOOT_H
#define XNUBOOT_H

#define CMDLINE_LENGTH 608

struct boot_video {
    u64 base;
    u64 display;
    u64 stride;
    u64 width;
    u64 height;
    u64 depth;
};

struct boot_args {
    u16 revision;
    u16 version;
    u64 virt_base;
    u64 phys_base;
    u64 mem_size;
    u64 top_of_kernel_data;
    struct boot_video video;
    u32 machine_type;
    void *devtree;
    u32 devtree_size;
    char cmdline[CMDLINE_LENGTH];
    u64 boot_flags;
    u64 mem_size_actual;
};

extern u64 boot_args_addr;
extern struct boot_args cur_boot_args;

#endif

/* SPDX-License-Identifier: MIT */

#ifndef MACHO_H
#define MACHO_H

#include "types.h"

#define MACHO_COMMAND_UNIX_THREAD 0x05
#define MACHO_COMMAND_SEGMENT_64  0x19

struct macho_header {
    u32 irrelevant[5];
    u32 cmdsize;
    u32 irrelevant2[2];
};

struct macho_command {
    u32 type;
    u32 size;
    union {
        struct {
            u32 thread_type;
            u32 length;
            u64 regs[32];
            u64 pc;
            u64 regs2[1];
        } unix_thread;
        struct {
            char segname[16];
            u64 vmaddr;
            u64 vmsize;
            u64 fileoff;
            u64 filesize;
            u64 unused2[2];
        } segment_64;
    } u;
};

void *macho_load(void *start, size_t size);
extern int (*macho_boot)(void);

#endif

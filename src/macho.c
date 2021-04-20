/* SPDX-License-Identifier: MIT */

#include "macho.h"
#include "malloc.h"
#include "memory.h"
#include "utils.h"
#include "xnuboot.h"

#include "libfdt/libfdt.h"

extern u64 boot_args_addr;
extern void mmu_shutdown(void);

static void (*macho_start_pc)(u64) = NULL;
int (*macho_boot)(void);

int macho_boot_impl(void)
{
    mmu_shutdown();

    macho_start_pc(boot_args_addr);

    panic("macho call returned\n");
}

void *macho_load(void *start, size_t size)
{
    UNUSED(size);
    struct macho_header *header = start;
    struct macho_command *command = (void *)(header + 1);
    struct macho_command *last_command = (void *)command + header->cmdsize;
    u64 pc = 0;
    u64 vmbase = 0;
    u64 vmtotalsize = 0;
    while (command < last_command) {
        switch (command->type) {
            case MACHO_COMMAND_UNIX_THREAD:
                pc = command->u.unix_thread.pc;
                break;
            case MACHO_COMMAND_SEGMENT_64: {
                u64 vmaddr = command->u.segment_64.vmaddr;
                u64 vmsize = command->u.segment_64.vmsize;

                if (vmbase == 0)
                    vmbase = vmaddr;
                if (vmsize + vmbase - vmaddr > vmtotalsize)
                    vmtotalsize = vmsize + vmaddr - vmbase;
                break;
            }
        }
        command = (void *)command + command->size;
    }
    void *dest = memalign(0x10000, vmtotalsize);
    memset(dest, 0, vmtotalsize);
    command = (void *)(header + 1);
    void *virtpc = NULL;
    while (command < last_command) {
        switch (command->type) {
            case MACHO_COMMAND_SEGMENT_64: {
                if (vmbase == 0)
                    vmbase = command->u.segment_64.vmaddr;
                u64 vmaddr = command->u.segment_64.vmaddr;
                u64 vmsize = command->u.segment_64.vmsize;
                u64 fileoff = command->u.segment_64.fileoff;
                u64 filesize = command->u.segment_64.filesize;
                u64 pcoff = pc - vmaddr;

                memcpy(dest + vmaddr - vmbase, start + fileoff, filesize);
                if (pcoff < vmsize) {

                    if (pcoff < filesize) {
                        virtpc = dest + vmaddr - vmbase + pcoff;
                    }
                }
            }
        }
        command = (void *)command + command->size;
    }

    macho_start_pc = virtpc;
    macho_boot = macho_boot_impl;

    return NULL;
}

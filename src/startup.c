/* SPDX-License-Identifier: MIT */

#include "chickens.h"
#include "exception.h"
#include "smp.h"
#include "string.h"
#include "types.h"
#include "uart.h"
#include "utils.h"
#include "xnuboot.h"

u64 boot_args_addr;
struct boot_args cur_boot_args;
void *adt;

struct rela_entry {
    uint64_t off, type, addend;
};

void debug_putc(char c);
void m1n1_main(void);

extern char _bss_start[0];
extern char _bss_end[0];

#define R_AARCH64_RELATIVE 1027

void apply_rela(uint64_t base, struct rela_entry *rela_start, struct rela_entry *rela_end)
{
    struct rela_entry *e = rela_start;

    while (e < rela_end) {
        switch (e->type) {
            case R_AARCH64_RELATIVE:
                *(u64 *)(base + e->off) = base + e->addend;
                break;
            default:
                debug_putc('R');
                debug_putc('!');
                while (1)
                    ;
        }
        e++;
    }
}

void dump_boot_args(struct boot_args *ba)
{
    printf("  revision:     %d\n", ba->revision);
    printf("  version:      %d\n", ba->version);
    printf("  virt_base:    0x%lx\n", ba->virt_base);
    printf("  phys_base:    0x%lx\n", ba->phys_base);
    printf("  mem_size:     0x%lx\n", ba->mem_size);
    printf("  top_of_kdata: 0x%lx\n", ba->top_of_kernel_data);
    printf("  video:\n");
    printf("    base:       0x%lx\n", ba->video.base);
    printf("    display:    0x%lx\n", ba->video.display);
    printf("    stride:     0x%lx\n", ba->video.stride);
    printf("    width:      %lu\n", ba->video.width);
    printf("    height:     %lu\n", ba->video.height);
    printf("    depth:      %lubpp\n", ba->video.depth & 0xff);
    printf("    density:    %lu\n", ba->video.depth >> 16);
    printf("  machine_type: %d\n", ba->machine_type);
    printf("  devtree:      %p\n", ba->devtree);
    printf("  devtree_size: 0x%x\n", ba->devtree_size);
    printf("  cmdline:      %s\n", ba->cmdline);
    printf("  boot_flags:   0x%lx\n", ba->boot_flags);
    printf("  mem_size_act: 0x%lx\n", ba->mem_size_actual);
}

void _start_c(void *boot_args, void *base)
{
    UNUSED(base);

    if (in_el2())
        msr(TPIDR_EL2, 0);
    else
        msr(TPIDR_EL1, 0);

    memset64(_bss_start, 0, _bss_end - _bss_start);
    boot_args_addr = (u64)boot_args;
    memcpy(&cur_boot_args, boot_args, sizeof(cur_boot_args));

    adt =
        (void *)(((u64)cur_boot_args.devtree) - cur_boot_args.virt_base + cur_boot_args.phys_base);

    int ret = uart_init();
    if (ret < 0) {
        debug_putc('!');
    }

    uart_puts("Initializing");
    printf("CPU init (MIDR: 0x%lx)...\n", mrs(MIDR_EL1));
    const char *type = init_cpu();
    printf("  CPU: %s\n\n", type);

    printf("boot_args at %p\n", boot_args);

    dump_boot_args(&cur_boot_args);
    printf("\n");

    exception_initialize();
    m1n1_main();
}

/* Secondary SMP core boot */
void _cpu_reset_c(void *stack)
{
    if (mrs(MPIDR_EL1) & 0xffffff)
        uart_puts("RVBAR entry on secondary CPU");
    else
        uart_puts("RVBAR entry on primary CPU");

    printf("\n  Stack base: %p\n", stack);
    printf("  MPIDR: 0x%lx\n", mrs(MPIDR_EL1));
    const char *type = init_cpu();
    printf("  CPU: %s\n", type);

    exception_initialize();
    smp_secondary_entry();
}

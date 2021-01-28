/* SPDX-License-Identifier: MIT */

#include "smp.h"
#include "types.h"
#include "utils.h"

#define CPU_START_BASE 0x23b754000L
#define RVBAR_BASE     0x210050000L

struct spin_table {
    u64 flag;
    u64 target;
};

void *_reset_stack;

u8 secondary_stacks[MAX_CPUS][0x8000] ALIGNED(64);

int target_cpu;
struct spin_table spin_table[MAX_CPUS];

extern u8 _vectors_start[0];

void smp_secondary_entry(void)
{
    spin_table[target_cpu].flag = 1;
    sysop("dmb sy");
    u64 target;
    while (1) {
        while (!(target = spin_table[target_cpu].target)) {
            sysop("wfe");
        }
        sysop("dmb sy");
        spin_table[target_cpu].target = 0;
        spin_table[target_cpu].flag++;
        sysop("dmb sy");
        ((void (*)(void))target)();
    }
}

static void smp_start_cpu(int index, int cluster, int core)
{
    int i;
    int cpu_id = (cluster << 4) | core;

    printf("Starting CPU %d (%d:%d)... ", index, cluster, core);

    spin_table[index].flag = 0;

    target_cpu = index;
    _reset_stack = secondary_stacks[index];

    sysop("dmb sy");

    write64(RVBAR_BASE + (cpu_id << 20), (u64)_vectors_start);

    if (cluster == 0) {
        write32(CPU_START_BASE + 0x8, 1 << core);
    } else {
        write32(CPU_START_BASE + 0xc, 1 << core);
    }

    for (i = 0; i < 500; i++) {
        sysop("dmb ld");
        if (spin_table[index].flag)
            break;
        udelay(1000);
    }

    if (i >= 500)
        printf("Failed!\n");
}

void smp_start_secondaries(void)
{
    printf("Starting secondary CPUs...\n");

    smp_start_cpu(1, 0, 1);
    smp_start_cpu(2, 0, 2);
    smp_start_cpu(3, 0, 3);
    smp_start_cpu(4, 1, 0);
    smp_start_cpu(5, 1, 1);
    smp_start_cpu(6, 1, 2);
    smp_start_cpu(7, 1, 3);
}

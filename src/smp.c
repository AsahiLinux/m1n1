/* SPDX-License-Identifier: MIT */

#include "smp.h"
#include "adt.h"
#include "string.h"
#include "types.h"
#include "utils.h"

#define CPU_START_OFF 0x54000

#define SECONDARY_STACK_SIZE 0x4000

struct spin_table {
    u64 flag;
    u64 target;
};

void *_reset_stack;

u8 secondary_stacks[MAX_CPUS][SECONDARY_STACK_SIZE] ALIGNED(64);

int target_cpu;
struct spin_table spin_table[MAX_CPUS];

extern u8 _vectors_start[0];

void smp_secondary_entry(void)
{
    struct spin_table *me = &spin_table[target_cpu];
    printf("  Index: %d (table: %p)\n\n", target_cpu, me);

    sysop("dmb sy");
    me->flag = 1;
    sysop("dmb sy");
    u64 target;
    while (1) {
        while (!(target = me->target)) {
            sysop("wfe");
        }
        sysop("dmb sy");
        me->target = 0;
        me->flag++;
        sysop("dmb sy");
        ((void (*)(void))target)();
    }
}

static void smp_start_cpu(int index, int cluster, int core, u64 rvbar, u64 cpu_start_base)
{
    int i;

    printf("Starting CPU %d (%d:%d)... ", index, cluster, core);

    spin_table[index].flag = 0;

    target_cpu = index;
    _reset_stack = secondary_stacks[index] + SECONDARY_STACK_SIZE;

    sysop("dmb sy");

    write64(rvbar, (u64)_vectors_start);

    if (cluster == 0) {
        write32(cpu_start_base + 0x8, 1 << core);
    } else {
        write32(cpu_start_base + 0xc, 1 << core);
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

    int pmgr_path[8];
    u64 pmgr_reg;

    if (adt_path_offset_trace(adt, "/arm-io/pmgr", pmgr_path) < 0) {
        printf("Error getting /arm-io/pmgr node\n");
        return;
    }
    if (adt_get_reg(adt, pmgr_path, "reg", 0, &pmgr_reg, NULL) < 0) {
        printf("Error getting /arm-io/pmgr regs\n");
        return;
    }

    int node = adt_path_offset(adt, "/cpus");
    if (node < 0) {
        printf("Error getting /cpus node\n");
        return;
    }

    int cpu_nodes[MAX_CPUS];

    memset(cpu_nodes, 0, sizeof(cpu_nodes));

    ADT_FOREACH_CHILD(adt, node)
    {
        u32 cpu_id;

        if (ADT_GETPROP(adt, node, "cpu-id", &cpu_id) < 0)
            continue;
        if (cpu_id >= MAX_CPUS) {
            printf("cpu-id %d exceeds max CPU count %d: increase MAX_CPUS\n", cpu_id, MAX_CPUS);
            continue;
        }

        cpu_nodes[cpu_id] = node;
    }

    for (int i = 1; i < MAX_CPUS; i++) {
        int node = cpu_nodes[i];

        if (!node)
            break;

        u32 reg;
        u64 cpu_impl_reg[2];
        if (ADT_GETPROP(adt, node, "reg", &reg) < 0)
            continue;
        if (ADT_GETPROP_ARRAY(adt, node, "cpu-impl-reg", cpu_impl_reg) < 0)
            continue;

        smp_start_cpu(i, reg >> 8, reg & 0xff, cpu_impl_reg[0], pmgr_reg + CPU_START_OFF);
    }
}

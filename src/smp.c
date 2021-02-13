/* SPDX-License-Identifier: MIT */

#include "smp.h"
#include "adt.h"
#include "string.h"
#include "types.h"
#include "utils.h"

#define CPU_START_OFF 0x54000

#define SECONDARY_STACK_SIZE 0x4000

struct spin_table {
    u64 mpidr;
    u64 flag;
    u64 target;
    u64 args[4];
    u64 retval;
};

void *_reset_stack;

static u8 secondary_stacks[MAX_CPUS][SECONDARY_STACK_SIZE] ALIGNED(64);

static int target_cpu;
static struct spin_table spin_table[MAX_CPUS];

extern u8 _vectors_start[0];

void smp_secondary_entry(void)
{
    struct spin_table *me = &spin_table[target_cpu];
    printf("  Index: %d (table: %p)\n\n", target_cpu, me);

    me->mpidr = mrs(MPIDR_EL1) & 0xFFFFFF;

    sysop("dmb sy");
    me->flag = 1;
    sysop("dmb sy");
    u64 target;
    while (1) {
        while (!(target = me->target)) {
            sysop("wfe");
        }
        sysop("dmb sy");
        me->flag++;
        sysop("dmb sy");
        me->retval = ((u64(*)(u64 a, u64 b, u64 c, u64 d))target)(me->args[0], me->args[1],
                                                                  me->args[2], me->args[3]);
        sysop("dmb sy");
        me->target = 0;
        sysop("dmb sy");
    }
}

static void smp_start_cpu(int index, int cluster, int core, u64 rvbar, u64 cpu_start_base)
{
    int i;

    if (spin_table[index].flag)
        return;

    printf("Starting CPU %d (%d:%d)... ", index, cluster, core);

    memset(&spin_table[index], 0, sizeof(struct spin_table));

    target_cpu = index;
    _reset_stack = secondary_stacks[index] + SECONDARY_STACK_SIZE;

    sysop("dmb sy");

    write64(rvbar, (u64)_vectors_start);

    // Some kind of system level startup/status bit
    // Without this, IRQs don't work
    write32(cpu_start_base + 0x4, 1 << index);

    // Actually start the core
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

    spin_table[0].mpidr = mrs(MPIDR_EL1) & 0xFFFFFF;
}

void smp_call4(int cpu, void *func, u64 arg0, u64 arg1, u64 arg2, u64 arg3)
{
    struct spin_table *target = &spin_table[cpu];

    if (cpu == 0)
        return;

    u64 flag = target->flag;
    target->args[0] = arg0;
    target->args[1] = arg1;
    target->args[2] = arg2;
    target->args[3] = arg3;
    sysop("dmb sy");
    target->target = (u64)func;
    sysop("dmb sy");
    sysop("sev");
    while (target->flag == flag)
        sysop("dmb sy");
}

u64 smp_wait(int cpu)
{
    struct spin_table *target = &spin_table[cpu];

    while (target->target)
        sysop("dmb sy");

    return target->retval;
}

int smp_get_mpidr(int cpu)
{
    return spin_table[cpu].mpidr;
}

u64 smp_get_release_addr(int cpu)
{
    struct spin_table *target = &spin_table[cpu];

    target->args[0] = 0;
    target->args[1] = 0;
    target->args[2] = 0;
    target->args[3] = 0;
    return (u64)&target->target;
}

int smp_is_primary(void)
{
    return mrs(MPIDR_EL1) == 0x80000000;
}

/* SPDX-License-Identifier: MIT */

#include "smp.h"
#include "adt.h"
#include "cpu_regs.h"
#include "malloc.h"
#include "pmgr.h"
#include "soc.h"
#include "string.h"
#include "types.h"
#include "utils.h"

#define CPU_START_OFF_T8103 0x54000
#define CPU_START_OFF_T8112 0x34000
#define CPU_START_OFF_T6020 0x28000
#define CPU_START_OFF_T6031 0x88000

#define CPU_REG_CORE    GENMASK(7, 0)
#define CPU_REG_CLUSTER GENMASK(10, 8)
#define CPU_REG_DIE     GENMASK(14, 11)

struct spin_table {
    u64 mpidr;
    u64 flag;
    u64 target;
    u64 args[4];
    u64 retval;
};

void *_reset_stack;

#define DUMMY_STACK_SIZE 0x1000
u8 dummy_stack[DUMMY_STACK_SIZE];

u8 *secondary_stacks[MAX_CPUS] = {dummy_stack};

static bool wfe_mode = false;

static int target_cpu;
static int cpu_nodes[MAX_CPUS];
static struct spin_table spin_table[MAX_CPUS];
static u64 pmgr_reg;
static u64 cpu_start_off;

extern u8 _vectors_start[0];
int boot_cpu_idx = -1;
u64 boot_cpu_mpidr = 0;

void smp_secondary_entry(void)
{
    struct spin_table *me = &spin_table[target_cpu];

    if (in_el2())
        msr(TPIDR_EL2, target_cpu);
    else
        msr(TPIDR_EL1, target_cpu);

    printf("  Index: %d (table: %p)\n\n", target_cpu, me);

    me->mpidr = mrs(MPIDR_EL1) & 0xFFFFFF;

    sysop("dmb sy");
    me->flag = 1;
    sysop("dmb sy");
    u64 target;

    while (1) {
        while (!(target = me->target)) {
            if (wfe_mode) {
                sysop("wfe");
            } else {
                deep_wfi();
                msr(SYS_IMP_APL_IPI_SR_EL1, 1);
            }
            sysop("isb");
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

static void smp_start_cpu(int index, int die, int cluster, int core, u64 impl, u64 cpu_start_base)
{
    int i;

    if (index >= MAX_CPUS)
        return;

    if (spin_table[index].flag)
        return;

    printf("Starting CPU %d (%d:%d:%d)... ", index, die, cluster, core);

    memset(&spin_table[index], 0, sizeof(struct spin_table));

    target_cpu = index;
    secondary_stacks[index] = memalign(0x4000, SECONDARY_STACK_SIZE);
    _reset_stack = secondary_stacks[index] + SECONDARY_STACK_SIZE;

    sysop("dmb sy");

    write64(impl, (u64)_vectors_start);

    cpu_start_base += die * PMGR_DIE_OFFSET;

    // Some kind of system level startup/status bit
    // Without this, IRQs don't work
    write32(cpu_start_base + 0x4, 1 << (4 * cluster + core));

    // Actually start the core
    write32(cpu_start_base + 0x8 + 4 * cluster, 1 << core);

    for (i = 0; i < 100; i++) {
        sysop("dmb ld");
        if (spin_table[index].flag)
            break;
        udelay(1000);
    }

    if (i >= 100)
        printf("Failed!\n");
    else
        printf("  Started.\n");

    _reset_stack = dummy_stack + DUMMY_STACK_SIZE;
}

static void smp_stop_cpu(int index, int die, int cluster, int core, u64 impl, u64 cpu_start_base,
                         bool deep_sleep)
{
    int i;

    if (index >= MAX_CPUS)
        return;

    if (!spin_table[index].flag)
        return;

    printf("Stopping CPU %d (%d:%d:%d)... ", index, die, cluster, core);

    cpu_start_base += die * PMGR_DIE_OFFSET;

    // Request CPU stop
    write32(cpu_start_base + 0x0, 1 << (4 * cluster + core));

    // Put the CPU to sleep
    smp_call1(index, cpu_sleep, deep_sleep);

    // If going into deep sleep, powering off the last core in a cluster kills our register
    // access, so just wait a bit.
    if (deep_sleep) {
        udelay(10000);
        printf("  Presumed stopped.\n");
        memset(&spin_table[index], 0, sizeof(struct spin_table));
        return;
    }

    // Check that it actually shut down
    for (i = 0; i < 50; i++) {
        sysop("dmb ld");
        if (!(read64(impl + 0x100) & 0xff))
            break;
        udelay(1000);
    }

    if (i >= 50) {
        printf("Failed!\n");
    } else {
        printf("  Stopped.\n");

        memset(&spin_table[index], 0, sizeof(struct spin_table));
    }
}

void smp_start_secondaries(void)
{
    printf("Starting secondary CPUs...\n");

    int pmgr_path[8];

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

    memset(cpu_nodes, 0, sizeof(cpu_nodes));

    switch (chip_id) {
        case T8103:
        case T6000:
        case T6001:
        case T6002:
            cpu_start_off = CPU_START_OFF_T8103;
            break;
        case T8112:
        case T8122:
        case T6030:
            cpu_start_off = CPU_START_OFF_T8112;
            break;
        case T6020:
        case T6021:
        case T6022:
            cpu_start_off = CPU_START_OFF_T6020;
            break;
        case T6031:
        case T6034:
            cpu_start_off = CPU_START_OFF_T6031;
            break;
        default:
            printf("CPU start offset is unknown for this SoC!\n");
            return;
    }

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

    /* The boot cpu id never changes once set */
    if (boot_cpu_idx == -1) {
        /* Figure out which CPU we are on by seeing which CPU is running */

        /* This seems silly but it's what XNU does */
        for (int i = 0; i < MAX_CPUS; i++) {
            int cpu_node = cpu_nodes[i];
            if (!cpu_node)
                continue;
            const char *state = adt_getprop(adt, cpu_node, "state", NULL);
            if (!state)
                continue;
            if (strcmp(state, "running") == 0) {
                boot_cpu_idx = i;
                boot_cpu_mpidr = mrs(MPIDR_EL1);
                break;
            }
        }
    }

    if (boot_cpu_idx == -1) {
        printf(
            "Could not find currently running CPU in cpu table, can't start other processors!\n");
        return;
    }

    if (in_el2())
        msr(TPIDR_EL2, boot_cpu_idx);
    else
        msr(TPIDR_EL1, boot_cpu_idx);


    for (int i = 0; i < MAX_CPUS; i++) {

        if (i == boot_cpu_idx)
            continue;
        int cpu_node = cpu_nodes[i];

        if (!cpu_node)
            continue;

        u32 reg;
        u64 cpu_impl_reg[2];
        if (ADT_GETPROP(adt, cpu_node, "reg", &reg) < 0)
            continue;
        if (ADT_GETPROP_ARRAY(adt, cpu_node, "cpu-impl-reg", cpu_impl_reg) < 0)
            continue;

        u8 core = FIELD_GET(CPU_REG_CORE, reg);
        u8 cluster = FIELD_GET(CPU_REG_CLUSTER, reg);
        u8 die = FIELD_GET(CPU_REG_DIE, reg);

        smp_start_cpu(i, die, cluster, core, cpu_impl_reg[0], pmgr_reg + cpu_start_off);
    }

    spin_table[boot_cpu_idx].mpidr = mrs(MPIDR_EL1) & 0xFFFFFF;
}

void smp_stop_secondaries(bool deep_sleep)
{
    printf("Stopping secondary CPUs...\n");
    smp_set_wfe_mode(true);

    for (int i = 0; i < MAX_CPUS; i++) {
        int node = cpu_nodes[i];

        if (!node)
            continue;

        u32 reg;
        u64 cpu_impl_reg[2];
        if (ADT_GETPROP(adt, node, "reg", &reg) < 0)
            continue;
        if (ADT_GETPROP_ARRAY(adt, node, "cpu-impl-reg", cpu_impl_reg) < 0)
            continue;

        u8 core = FIELD_GET(CPU_REG_CORE, reg);
        u8 cluster = FIELD_GET(CPU_REG_CLUSTER, reg);
        u8 die = FIELD_GET(CPU_REG_DIE, reg);

        smp_stop_cpu(i, die, cluster, core, cpu_impl_reg[0], pmgr_reg + cpu_start_off, deep_sleep);
    }
}

void smp_send_ipi(int cpu)
{
    if (cpu >= MAX_CPUS)
        return;

    u64 mpidr = spin_table[cpu].mpidr;
    msr(SYS_IMP_APL_IPI_RR_GLOBAL_EL1, (mpidr & 0xff) | ((mpidr & 0xff00) << 8));
}

void smp_call4(int cpu, void *func, u64 arg0, u64 arg1, u64 arg2, u64 arg3)
{
    if (cpu >= MAX_CPUS)
        return;

    struct spin_table *target = &spin_table[cpu];

    if (cpu == boot_cpu_idx)
        return;

    u64 flag = target->flag;
    target->args[0] = arg0;
    target->args[1] = arg1;
    target->args[2] = arg2;
    target->args[3] = arg3;
    sysop("dmb sy");
    target->target = (u64)func;
    sysop("dsb sy");

    if (wfe_mode)
        sysop("sev");
    else
        smp_send_ipi(cpu);

    while (target->flag == flag)
        sysop("dmb sy");
}

u64 smp_wait(int cpu)
{
    if (cpu >= MAX_CPUS)
        return 0;

    struct spin_table *target = &spin_table[cpu];

    while (target->target)
        sysop("dmb sy");

    return target->retval;
}

void smp_set_wfe_mode(bool new_mode)
{
    wfe_mode = new_mode;
    sysop("dsb sy");

    for (int cpu = 0; cpu < MAX_CPUS; cpu++)
        if (cpu != boot_cpu_idx && smp_is_alive(cpu))
            smp_send_ipi(cpu);

    sysop("sev");
}

bool smp_is_alive(int cpu)
{
    if (cpu >= MAX_CPUS)
        return false;

    return spin_table[cpu].flag;
}

uint64_t smp_get_mpidr(int cpu)
{
    if (cpu >= MAX_CPUS)
        return 0;

    return spin_table[cpu].mpidr;
}

u64 smp_get_release_addr(int cpu)
{
    struct spin_table *target = &spin_table[cpu];

    if (cpu >= MAX_CPUS)
        return 0;

    target->args[0] = 0;
    target->args[1] = 0;
    target->args[2] = 0;
    target->args[3] = 0;
    return (u64)&target->target;
}

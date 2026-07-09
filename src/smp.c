/* SPDX-License-Identifier: MIT */

#include "smp.h"
#include "adt.h"
#include "aic.h"
#include "aic_regs.h"
#include "cpu_regs.h"
#include "memory.h"
#include "pmgr.h"
#include "soc.h"
#include "string.h"
#include "types.h"
#include "utils.h"

#define CPU_START_OFF_S5L8960X 0x30000
#define CPU_START_OFF_S8000    0xd4000
#define CPU_START_OFF_T8103    0x54000
#define CPU_START_OFF_T8112    0x34000
#define CPU_START_OFF_T6020    0x28000
#define CPU_START_OFF_T6031    0x88000

#define CPU_REG_CORE    GENMASK(7, 0)
#define CPU_REG_CLUSTER GENMASK(10, 8)
#define CPU_REG_DIE     GENMASK(14, 11)

#define RVBAR_LOCK BIT(0)
#define RVBAR_ADDR GENMASK(47, 12)

struct spin_table {
    u64 mpidr;
    u64 flag;
    u64 target;
    u64 args[4];
    u64 retval;
};

void *_reset_stack;
void *_reset_stack_el1;

#define DUMMY_STACK_SIZE 0x1000
u8 dummy_stack[DUMMY_STACK_SIZE];     // Highest EL
u8 dummy_stack_el1[DUMMY_STACK_SIZE]; // EL1 stack if EL3 exists

u8 secondary_stacks[MAX_CPUS][SECONDARY_STACK_SIZE] ALIGNED(0x4000);
u8 secondary_stacks_el3[MAX_EL3_CPUS][SECONDARY_STACK_SIZE] ALIGNED(0x4000);

static bool wfe_mode = false;

static int target_cpu;
static int cpu_nodes[MAX_CPUS];
static struct spin_table spin_table[MAX_CPUS];

struct cpu_info {
    bool valid;
    u8 die;
    u8 cluster;
    u8 core;
    u64 impl_reg;
};

static bool smp_initialized = false;
static u64 cpu_start_base;
static struct cpu_info cpu_info[MAX_CPUS];

// Used from start.S to find the correct stack after the first entry
struct smp_reset_stack {
    u64 mpidr;
    u64 stack;
};

struct smp_reset_stack smp_reset_stacks[MAX_CPUS] = {
    [0 ... MAX_CPUS - 1] = {.mpidr = ~0ULL, .stack = 0},
};

extern u8 _vectors_start[0];
int boot_cpu_idx = -1;
u64 boot_cpu_mpidr = 0;

void smp_secondary_entry(void)
{
    u64 mpidr = mrs(MPIDR_EL1) & 0xFFFFFF;
    int index = target_cpu;

    // target_cpu identifies us during the initial start handshake, but may
    // be stale on an RVBAR re-entry after deep wfi
    for (int i = 0; i < MAX_CPUS; i++) {
        if (smp_reset_stacks[i].mpidr == mpidr) {
            index = i;
            break;
        }
    }

    smp_reset_stacks[index].stack = (u64)secondary_stacks[index] + SECONDARY_STACK_SIZE;
    smp_reset_stacks[index].mpidr = mpidr;
    dc_civac_range(&smp_reset_stacks[index], sizeof(smp_reset_stacks[index]));
    sysop("dsb sy");

    struct spin_table *me = &spin_table[index];

    if (in_el2())
        msr(TPIDR_EL2, index);
    else
        msr(TPIDR_EL1, index);

    printf("  Index: %d (table: %p)\n\n", index, me);

    me->mpidr = mpidr;

    sysop("dmb sy");
    me->flag++;
    sysop("dmb sy");
    u64 target;
    if (!cpu_features->fast_ipi)
        aic_write(AIC_IPI_MASK_SET, AIC_IPI_SELF); // we only use the "other" IPI

    while (1) {
        while (!(target = me->target)) {
            if (wfe_mode) {
                sysop("wfe");
            } else {
                deep_wfi();

                if (cpu_features->fast_ipi) {
                    msr(SYS_IMP_APL_IPI_SR_EL1, 1);
                } else {
                    aic_ack(); // Actually read IPI reason
                    aic_write(AIC_IPI_ACK, AIC_IPI_OTHER);
                    aic_write(AIC_IPI_MASK_CLR, AIC_IPI_OTHER);
                }
            }
            sysop("isb");
        }
        sysop("dmb sy");
        me->flag++;
        sysop("dmb sy");
        me->retval = ((u64 (*)(u64 a, u64 b, u64 c, u64 d))target)(me->args[0], me->args[1],
                                                                   me->args[2], me->args[3]);
        sysop("dmb sy");
        me->target = 0;
        sysop("dmb sy");
    }
}

void smp_secondary_prep_el3(void)
{
    msr(TPIDR_EL3, target_cpu);
    return;
}

static void smp_start_cpu(int index, int die, int cluster, int core, u64 impl, u64 cpu_start_base)
{
    int i;

    if (index >= MAX_CPUS)
        return;

    if (has_el3() && index >= MAX_EL3_CPUS)
        return;

    if (spin_table[index].flag)
        return;

    if (!cpu_features->apple_sysregs_unlocked &&
        (read64(impl) & RVBAR_ADDR) != (u64)_vectors_start) {
        printf("Failed! \n    RVBAR (=0x%lx) is locked and differs from entry point (=0x%lx)\n",
               read64(impl) & RVBAR_ADDR, (u64)_vectors_start);
    }

    printf("Starting CPU %d (%d:%d:%d)... ", index, die, cluster, core);

    memset(&spin_table[index], 0, sizeof(struct spin_table));

    target_cpu = index;
    if (has_el3()) {
        _reset_stack = secondary_stacks_el3[index] + SECONDARY_STACK_SIZE; // EL3
        _reset_stack_el1 = secondary_stacks[index] + SECONDARY_STACK_SIZE; // EL1

        dc_civac_range(&_reset_stack_el1, sizeof(void *));
    } else
        _reset_stack = secondary_stacks[index] + SECONDARY_STACK_SIZE;

    dc_civac_range(&_reset_stack, sizeof(void *));

    sysop("dsb sy");

    if (cpu_features->apple_sysregs_unlocked) {
        // This also clears RVBAR_LOCK, so that HV can set RVBAR later when the core is running
        write64(impl, (u64)_vectors_start);
    }

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
    _reset_stack_el1 = dummy_stack_el1 + DUMMY_STACK_SIZE;
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

    u64 dsleep = deep_sleep;
    // Put the CPU to sleep
    smp_call1(index, cpu_sleep, dsleep);

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

int smp_init(void)
{
    if (smp_initialized)
        return 0;

    int pmgr_path[8];
    u64 pmgr_reg;
    u64 cpu_start_off;

    if (adt_path_offset_trace(adt, "/arm-io/pmgr", pmgr_path) < 0) {
        printf("Error getting /arm-io/pmgr node\n");
        return -1;
    }
    if (adt_get_reg(adt, pmgr_path, "reg", 0, &pmgr_reg, NULL) < 0) {
        printf("Error getting /arm-io/pmgr regs\n");
        return -1;
    }

    int arm_io_node;
    if ((arm_io_node = adt_path_offset(adt, "/arm-io")) < 0) {
        printf("Error getting /arm-io node\n");
        return -1;
    }

    int node = adt_path_offset(adt, "/cpus");
    if (node < 0) {
        printf("Error getting /cpus node\n");
        return -1;
    }

    memset(cpu_nodes, 0, sizeof(cpu_nodes));
    memset(cpu_info, 0, sizeof(cpu_info));

    switch (chip_id) {
        case S5L8960X:
        case T7000:
        case T7001:
            cpu_start_off = CPU_START_OFF_S5L8960X;
            break;
        case S8000:
        case S8001:
        case S8003:
        case T8010:
        case T8011:
        case T8012:
        case T8015:
            cpu_start_off = CPU_START_OFF_S8000;
            break;
        case T8103:
        case T6000:
        case T6001:
        case T6002:
            cpu_start_off = CPU_START_OFF_T8103;
            break;
        case T8112:
        case T8122:
        case T8132:
        case T8140:
            cpu_start_off = CPU_START_OFF_T8112;
            break;
        case T6020:
        case T6021:
        case T6022:
            cpu_start_off = CPU_START_OFF_T6020;
            break;
        case T6030:
            cpu_start_off = CPU_START_OFF_T8112;
            break;
        case T6031:
        case T6034:
        case T6040:
        case T6050:
        case T6051:
            cpu_start_off = CPU_START_OFF_T6031;
            break;
        default:
            printf("CPU start offset is unknown for this SoC!\n");
            return -1;
    }

    ADT_FOREACH_CHILD(adt, node)
    {
        u32 cpu_id;

        if (ADT_GETPROP(adt, node, "cpu-id", &cpu_id) < 0)
            if (ADT_GETPROP(adt, node, "reg", &cpu_id) < 0)
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
                if (in_el2())
                    msr(TPIDR_EL2, boot_cpu_idx);
                else
                    msr(TPIDR_EL1, boot_cpu_idx);
                break;
            }
        }
    }

    if (boot_cpu_idx == -1) {
        printf(
            "Could not find currently running CPU in cpu table, can't start other processors!\n");
        return -1;
    }

    spin_table[boot_cpu_idx].mpidr = mrs(MPIDR_EL1) & 0xFFFFFF;

    for (int i = 0; i < MAX_CPUS; i++) {
        int cpu_node = cpu_nodes[i];

        if (!cpu_node)
            continue;

        u32 reg;
        u64 cpu_impl_reg[2];
        if (ADT_GETPROP(adt, cpu_node, "reg", &reg) < 0)
            continue;
        if (ADT_GETPROP_ARRAY(adt, cpu_node, "cpu-impl-reg", cpu_impl_reg) < 0) {
            u32 reg_len;
            const u64 *regs = adt_getprop(adt, arm_io_node, "reg", &reg_len);
            if (!regs)
                continue;
            u32 index = 2 * i + 2;
            if (reg_len < index)
                continue;
            memcpy(cpu_impl_reg, &regs[index], 16);
        }

        cpu_info[i].valid = true;
        cpu_info[i].core = FIELD_GET(CPU_REG_CORE, reg);
        cpu_info[i].cluster = FIELD_GET(CPU_REG_CLUSTER, reg);
        cpu_info[i].die = FIELD_GET(CPU_REG_DIE, reg);
        cpu_info[i].impl_reg = cpu_impl_reg[0];
    }

    cpu_start_base = pmgr_reg + cpu_start_off;
    smp_initialized = true;

    return 0;
}

void smp_start_secondaries(void)
{
    printf("Starting secondary CPUs...\n");

    if (!smp_initialized)
        return;

    for (int i = 0; i < MAX_CPUS; i++) {
        struct cpu_info *cpu = &cpu_info[i];

        if (!cpu->valid)
            continue;

        if (i == boot_cpu_idx) {
            // Check if already locked
            if (FIELD_GET(RVBAR_LOCK, read64(cpu->impl_reg)))
                continue;

            // Unlocked, write _vectors_start into boot CPU's rvbar
            write64(cpu->impl_reg, (u64)_vectors_start);
            sysop("dmb sy");

            continue;
        }

        smp_start_cpu(i, cpu->die, cpu->cluster, cpu->core, cpu->impl_reg, cpu_start_base);
    }
}

void smp_stop_secondaries(bool deep_sleep)
{
    printf("Stopping secondary CPUs...\n");

    if (!smp_initialized)
        return;

    smp_set_wfe_mode(true);

    for (int i = 0; i < MAX_CPUS; i++) {
        struct cpu_info *cpu = &cpu_info[i];

        if (!cpu->valid || i == boot_cpu_idx)
            continue;

        smp_stop_cpu(i, cpu->die, cpu->cluster, cpu->core, cpu->impl_reg, cpu_start_base,
                     deep_sleep);
    }
}

void smp_send_ipi(int cpu)
{
    if (cpu >= MAX_CPUS)
        return;

    u64 mpidr = spin_table[cpu].mpidr;
    if (cpu_features->fast_ipi) {
        msr(SYS_IMP_APL_IPI_RR_GLOBAL_EL1, (mpidr & 0xff) | ((mpidr & 0xff00) << 8));
    } else {
        aic_write(AIC_IPI_SEND, AIC_IPI_SEND_CPU(cpu));
    }
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

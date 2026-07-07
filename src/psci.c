/* SPDX-License-Identifier: MIT */

#include "psci.h"
#include "smp.h"
#include "types.h"
#include "utils.h"

#ifdef PSCI_DEBUG
#define psci_printf(fmt, ...) printf("PSCI: " fmt, ##__VA_ARGS__)
#else
#define psci_printf(...)                                                                           \
    do {                                                                                           \
    } while (0)
#endif

enum psci_affinity_info_t {
    PSCI_AFFINITY_INFO_ON = 0,
    PSCI_AFFINITY_INFO_OFF = 1,
    PSCI_AFFINITY_INFO_ON_PENDING = 2,
};

static unsigned long psci_cpu_suspend(unsigned long power_state, unsigned long entry_point,
                                      unsigned long context_id)
{
    switch (power_state) {
        case 0:
            if (!cpu_features->apple_sysregs_unlocked)
                return PSCI_RET_NOT_SUPPORTED;
            sysop("dsb sy");
            sysop("wfi");
            return PSCI_RET_SUCCESS;
            break;
        case 1:
            deep_wfi();
            return PSCI_RET_SUCCESS;
            break;
        default:
            psci_printf("CPU_SUSPEND(power_state=0x%lx, entry_point=0x%lx, context_id=0x%lx)\n",
                        power_state, entry_point, context_id);
            return PSCI_RET_NOT_SUPPORTED;
    }
}

static unsigned long psci_cpu_off(void)
{
    psci_printf("CPU_OFF()\n");
    return PSCI_RET_NOT_SUPPORTED;
}

static unsigned long psci_cpu_on(unsigned long target_cpu, unsigned long entry_point,
                                 unsigned long context_id)
{
    int cpu = -1;

    if (!entry_point)
        return PSCI_RET_INVALID_ADDRESS;

    for (int i = 0; i < MAX_CPUS; i++) {
        if (!smp_is_alive(i))
            continue;
        if (smp_get_mpidr(i) == (target_cpu & 0xFFFFFF)) {
            cpu = i;
            break;
        }
    }

    if (cpu == -1)
        return PSCI_RET_INVALID_PARAMS;

    if (read64(smp_get_release_addr(cpu)))
        return PSCI_RET_ALREADY_ON;

    psci_printf("CPU_ON: releasing CPU %d (mpidr=0x%lx) to 0x%lx\n", cpu, target_cpu, entry_point);

    smp_call1(cpu, (void *)entry_point, context_id);

    return PSCI_RET_SUCCESS;
}

static unsigned long psci_affinity_info(unsigned long target_affinity,
                                        unsigned long lowest_affinity_level)
{
    psci_printf("AFFINITY_INFO(target_affinity=0x%lx, lowest_affinity_level=0x%lx)\n",
                target_affinity, lowest_affinity_level);
    return PSCI_AFFINITY_INFO_OFF;
}

unsigned long efi_psci_handler(unsigned long fid, unsigned long arg0, unsigned long arg1,
                               unsigned long arg2)
{
    switch (fid) {
        case PSCI_0_2_FN64_CPU_SUSPEND:
            return psci_cpu_suspend(arg0, arg1, arg2);
        case PSCI_0_2_FN_CPU_OFF:
            return psci_cpu_off();
        case PSCI_0_2_FN64_CPU_ON:
            return psci_cpu_on(arg0, arg1, arg2);
        case PSCI_0_2_FN64_AFFINITY_INFO:
            return psci_affinity_info(arg0, arg1);
        default:
            psci_printf("unsupported fid 0x%lx (arg0=0x%lx, arg1=0x%lx, arg2=0x%lx)\n", fid, arg0,
                        arg1, arg2);
            return PSCI_RET_NOT_SUPPORTED;
    }
}

const struct psci_efi_table psci_efi_table = {
    .version = PSCI_VERSION_1_0,
    .handler = efi_psci_handler,
    .features =
        {
            [0 ... PSCI_MAX_FN - 1] = PSCI_RET_NOT_SUPPORTED,
            [PSCI_FN(PSCI_0_2_FN_PSCI_VERSION)] = PSCI_RET_SUCCESS,
            [PSCI_FN(PSCI_1_0_FN_PSCI_FEATURES)] = PSCI_RET_SUCCESS,
            [PSCI_FN(PSCI_0_2_FN64_CPU_SUSPEND)] = PSCI_RET_SUCCESS,
            [PSCI_FN(PSCI_0_2_FN_CPU_OFF)] = PSCI_RET_SUCCESS,
            [PSCI_FN(PSCI_0_2_FN64_CPU_ON)] = PSCI_RET_SUCCESS,
            [PSCI_FN(PSCI_0_2_FN64_AFFINITY_INFO)] = PSCI_RET_SUCCESS,
        },
};

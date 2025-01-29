/* SPDX-License-Identifier: MIT */

#include "mitigations.h"
#include "cpu_regs.h"
#include "midr.h"
#include "smp.h"
#include "string.h"
#include "types.h"
#include "utils.h"

bool patch_gofetch(void)
{
    reg_set(SYS_IMP_APL_HID11, HID11_DISABLE_DMP);
    return true;
}

// M3 and later CPUs implement DIT to disable the DMP, so these CPUs behave as architecturally
// intended. We do not consider M3 and later to be vulnerable to GoFetch. The correct mitigation
// on those CPUs is for software to enable the DIT feature around crypto code. Not doing so is a
// software bug.
static u32 cpus_gofetch[] = {
    MIDR_PART_T8101_FIRESTORM,
    MIDR_PART_T8103_FIRESTORM,
    MIDR_PART_T6000_FIRESTORM,
    MIDR_PART_T6001_FIRESTORM,
    MIDR_PART_T8110_AVALANCHE,
    MIDR_PART_T8112_AVALANCHE,
    MIDR_PART_T6020_AVALANCHE,
    MIDR_PART_T6021_AVALANCHE,
    /* This table is complete, do not add newer CPUs */
    -1,
};

struct mitigation {
    const char *name;
    u32 *cpus;
    bool (*apply_patch)(void);
    bool vulnerable;
    bool mitigate;
    bool mitigated;
};

static struct mitigation mitigations[] = {
    {"gofetch", cpus_gofetch, patch_gofetch},
};

void mitigations_configure(const char *config)
{
    const char *end;
    size_t len;
    do {
        end = strchr(config, ',');
        if (end)
            len = end - config;
        else
            len = strlen(config);

        for (unsigned i = 0; i < ARRAY_SIZE(mitigations); i++) {
            struct mitigation *p = &mitigations[i];
            if (strlen(p->name) == len && !memcmp(p->name, config, len))
                p->mitigate = true;
        }
        if (end)
            config = end + 1;
    } while (end != NULL);
}

static void apply_mitigations(void)
{
    uint64_t midr = mrs(MIDR_EL1);
    u32 part = FIELD_GET(MIDR_PART, midr);

    for (unsigned i = 0; i < ARRAY_SIZE(mitigations); i++) {
        struct mitigation *p = &mitigations[i];
        u32 *ppart = p->cpus;
        while (*ppart != (u32)-1) {
            if (*ppart++ == part) {
                if (p->mitigate) {
                    if (!p->vulnerable) {
                        p->mitigated = true;
                    }
                    p->mitigated = p->mitigated && p->apply_patch();
                }
                p->vulnerable = true;
            }
        }
    }
}

void mitigations_perform(void)
{
    apply_mitigations();
    for (int i = 0; i < MAX_CPUS; i++) {
        if (i == boot_cpu_idx)
            continue;
        if (smp_is_alive(i)) {
            smp_call0(i, apply_mitigations);
            smp_wait(i);
        }
    }

    printf("\nCPU vulnerability status:\n");
    for (unsigned i = 0; i < ARRAY_SIZE(mitigations); i++) {
        const struct mitigation *p = &mitigations[i];
        printf("  %4s: %s\n", p->name,
               p->vulnerable ? (p->mitigated ? "Mitigated" : "Vulnerable") : "Not vulnerable");
    }
    printf("\n");
}

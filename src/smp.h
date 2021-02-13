/* SPDX-License-Identifier: MIT */

#ifndef __SMP_H__
#define __SMP_H__

#include "types.h"

#define MAX_CPUS 8

void smp_secondary_entry(void);

void smp_start_secondaries(void);

#define smp_call0(i, f)          smp_call(i, f, 0, 0, 0, 0)
#define smp_call1(i, f, a)       smp_call(i, f, a, 0, 0, 0)
#define smp_call2(i, f, a, b)    smp_call(i, f, a, b, 0, 0)
#define smp_call3(i, f, a, b, c) smp_call(i, f, a, b, c, 0)

void smp_call4(int cpu, void *func, u64 arg0, u64 arg1, u64 arg2, u64 arg3);

u64 smp_wait(int cpu);

int smp_get_mpidr(int cpu);
u64 smp_get_release_addr(int cpu);

int smp_is_primary(void);

#endif

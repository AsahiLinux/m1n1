/* SPDX-License-Identifier: MIT */

#ifndef __SMP_H__
#define __SMP_H__

#define MAX_CPUS 8

void smp_secondary_entry(void);

void smp_start_secondaries(void);

#endif

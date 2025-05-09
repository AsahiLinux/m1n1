/* SPDX-License-Identifier: MIT */

#ifndef CPUFREQ_H
#define CPUFREQ_H

int cpufreq_init(void);
void cpufreq_fixup(void);
void cpufreq_prepare_1500000_baud(void);

#endif

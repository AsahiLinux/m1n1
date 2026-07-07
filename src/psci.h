/* SPDX-License-Identifier: MIT */

#ifndef PSCI_H
#define PSCI_H

#include "types.h"

#define PSCI_VERSION_1_0 0x00010000

/*
 * PSCI function numbers are the low byte of a function ID and are identical for
 * the SMC32 and SMC64 variants. All PSCI 1.x functions stay below this, so the
 * feature table is indexed by function number rather than by full fid.
 */
#define PSCI_MAX_FN 0x20

#define PSCI_FN(fid) ((fid) & 0xff)

enum psci_fn_id_t {
    PSCI_0_2_FN_PSCI_VERSION = 0x84000000,
    PSCI_0_2_FN64_CPU_SUSPEND = 0xc4000001,
    PSCI_0_2_FN_CPU_OFF = 0x84000002,
    PSCI_0_2_FN64_CPU_ON = 0xc4000003,
    PSCI_0_2_FN64_AFFINITY_INFO = 0xc4000004,
    PSCI_1_0_FN_PSCI_FEATURES = 0x8400000a,
};

enum psci_ret_t {
    PSCI_RET_SUCCESS = 0,
    PSCI_RET_NOT_SUPPORTED = -1,
    PSCI_RET_INVALID_PARAMS = -2,
    PSCI_RET_DENIED = -3,
    PSCI_RET_ALREADY_ON = -4,
    PSCI_RET_ON_PENDING = -5,
    PSCI_RET_INTERNAL_FAILURE = -6,
    PSCI_RET_NOT_PRESENT = -7,
    PSCI_RET_DISABLED = -8,
    PSCI_RET_INVALID_ADDRESS = -9,
};

unsigned long efi_psci_handler(unsigned long fid, unsigned long arg0, unsigned long arg1,
                               unsigned long arg2);

/*
 * Payload of the LINUX_EFI_ARM_PSCI_HANDLER_TABLE EFI config table, which lets
 * the kernel call into the resident PSCI implementation via a plain function
 * pointer instead of SMC/HVC. Layout must match the kernel's
 * struct efi_arm_psci_handler_table.
 */
struct psci_efi_table {
    u32 version;
    unsigned long (*handler)(unsigned long fid, unsigned long arg0, unsigned long arg1,
                             unsigned long arg2);
    s32 features[PSCI_MAX_FN];
};

extern const struct psci_efi_table psci_efi_table;

#endif

/* SPDX-License-Identifier: MIT */

#ifndef __PROXY_H__
#define __PROXY_H__

#include "types.h"

typedef enum {
    P_NOP = 0x000, // System functions
    P_EXIT,
    P_CALL,
    P_GET_BOOTARGS,
    P_GET_BASE,
    P_SET_BAUD,
    P_UDELAY,
    P_SET_EXC_GUARD,
    P_GET_EXC_COUNT,

    P_WRITE64 = 0x100, // Generic register functions
    P_WRITE32,
    P_WRITE16,
    P_WRITE8,
    P_READ64,
    P_READ32,
    P_READ16,
    P_READ8,
    P_SET64,
    P_SET32,
    P_SET16,
    P_SET8,
    P_CLEAR64,
    P_CLEAR32,
    P_CLEAR16,
    P_CLEAR8,
    P_MASK64,
    P_MASK32,
    P_MASK16,
    P_MASK8,

    P_MEMCPY64 = 0x200, // Memory block transfer functions
    P_MEMCPY32,
    P_MEMCPY16,
    P_MEMCPY8,
    P_MEMSET64,
    P_MEMSET32,
    P_MEMSET16,
    P_MEMSET8,

    P_IC_IALLUIS = 0x300, // Cache and memory ops
    P_IC_IALLU,
    P_IC_IVAU,
    P_DC_IVAC,
    P_DC_ISW,
    P_DC_CSW,
    P_DC_CISW,
    P_DC_ZVA,
    P_DC_CVAC,
    P_DC_CVAU,
    P_DC_CIVAC,
    P_MMU_SHUTDOWN,

    P_XZDEC = 0x400, // Decompression and data processing ops
    P_GZDEC,

    P_SMP_START_SECONDARIES = 0x500, // SMP and system management ops
    P_SMP_CALL,
    P_SMP_CALL_SYNC,

    P_HEAPBLOCK_ALLOC = 0x600, // Heap and memory management ops
    P_MALLOC,
    P_MEMALIGN,
    P_FREE,

    P_KBOOT_BOOT = 0x700, // Kernel boot ops
    P_KBOOT_SET_BOOTARGS,
    P_KBOOT_SET_INITRD,
    P_KBOOT_PREPARE_DT,

} ProxyOp;

#define S_OK     0
#define S_BADCMD -1

typedef u64(callfunc)(u64, u64, u64, u64);

typedef struct {
    u64 opcode;
    u64 args[6];
} ProxyRequest;

typedef struct {
    u64 opcode;
    s64 status;
    u64 retval;
} ProxyReply;

int proxy_process(ProxyRequest *request, ProxyReply *reply);

#endif

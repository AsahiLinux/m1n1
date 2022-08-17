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
    P_EL0_CALL,
    P_EL1_CALL,
    P_VECTOR,
    P_GL1_CALL,
    P_GL2_CALL,
    P_GET_SIMD_STATE,
    P_PUT_SIMD_STATE,
    P_REBOOT,

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
    P_WRITEREAD64,
    P_WRITEREAD32,
    P_WRITEREAD16,
    P_WRITEREAD8,

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
    P_MMU_INIT,
    P_MMU_DISABLE,
    P_MMU_RESTORE,
    P_MMU_INIT_SECONDARY,

    P_XZDEC = 0x400, // Decompression and data processing ops
    P_GZDEC,

    P_SMP_START_SECONDARIES = 0x500, // SMP and system management ops
    P_SMP_CALL,
    P_SMP_CALL_SYNC,
    P_SMP_WAIT,
    P_SMP_SET_WFE_MODE,

    P_HEAPBLOCK_ALLOC = 0x600, // Heap and memory management ops
    P_MALLOC,
    P_MEMALIGN,
    P_FREE,

    P_KBOOT_BOOT = 0x700, // Kernel boot ops
    P_KBOOT_SET_CHOSEN,
    P_KBOOT_SET_INITRD,
    P_KBOOT_PREPARE_DT,

    P_PMGR_POWER_ENABLE = 0x800, // power/clock management ops
    P_PMGR_POWER_DISABLE,
    P_PMGR_ADT_POWER_ENABLE,
    P_PMGR_ADT_POWER_DISABLE,
    P_PMGR_RESET,

    P_IODEV_SET_USAGE = 0x900,
    P_IODEV_CAN_READ,
    P_IODEV_CAN_WRITE,
    P_IODEV_READ,
    P_IODEV_WRITE,
    P_IODEV_WHOAMI,
    P_USB_IODEV_VUART_SETUP,

    P_TUNABLES_APPLY_GLOBAL = 0xa00,
    P_TUNABLES_APPLY_LOCAL,
    P_TUNABLES_APPLY_LOCAL_ADDR,

    P_DART_INIT = 0xb00,
    P_DART_SHUTDOWN,
    P_DART_MAP,
    P_DART_UNMAP,

    P_HV_INIT = 0xc00,
    P_HV_MAP,
    P_HV_START,
    P_HV_TRANSLATE,
    P_HV_PT_WALK,
    P_HV_MAP_VUART,
    P_HV_TRACE_IRQ,
    P_HV_WDT_START,
    P_HV_START_SECONDARY,
    P_HV_SWITCH_CPU,
    P_HV_SET_TIME_STEALING,
    P_HV_PIN_CPU,
    P_HV_WRITE_HCR,

    P_FB_INIT = 0xd00,
    P_FB_SHUTDOWN,
    P_FB_BLIT,
    P_FB_UNBLIT,
    P_FB_FILL,
    P_FB_CLEAR,
    P_FB_DISPLAY_LOGO,
    P_FB_RESTORE_LOGO,
    P_FB_IMPROVE_LOGO,

    P_PCIE_INIT = 0xe00,
    P_PCIE_SHUTDOWN,

    P_NVME_INIT = 0xf00,
    P_NVME_SHUTDOWN,
    P_NVME_READ,
    P_NVME_FLUSH,

    P_MCC_GET_CARVEOUTS = 0x1000,

    P_DISPLAY_INIT = 0x1100,
    P_DISPLAY_CONFIGURE,
    P_DISPLAY_SHUTDOWN,

    P_DAPF_INIT_ALL = 0x1200,
    P_DAPF_INIT,

} ProxyOp;

#define S_OK     0
#define S_BADCMD -1

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

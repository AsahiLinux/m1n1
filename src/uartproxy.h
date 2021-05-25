/* SPDX-License-Identifier: MIT */

#ifndef __UARTPROXY_H__
#define __UARTPROXY_H__

#include "iodev.h"

extern iodev_id_t uartproxy_iodev;

typedef enum _uartproxy_start_reason_t {
    START_BOOT,
    START_EXCEPTION,
    START_EXCEPTION_LOWER,
    START_HV,
} uartproxy_boot_reason_t;

typedef enum _uartproxy_exc_code_t {
    EXC_SYNC,
    EXC_IRQ,
    EXC_FIQ,
    EXC_SERROR,
} uartproxy_exc_code_t;

typedef enum _uartproxy_exc_ret_t {
    EXC_RET_UNHANDLED = 1,
    EXC_RET_HANDLED = 2,
    EXC_EXIT_GUEST = 3,
    EXC_RET_STEP = 4,
} uartproxy_exc_ret_t;

typedef enum _uartproxy_event_type_t {
    EVT_MMIOTRACE = 1,
} uartproxy_event_type_t;

struct uartproxy_exc_info {
    u64 spsr;
    u64 elr;
    u64 esr;
    u64 far;
    u64 regs[31];
    u64 sp[3];
    u64 mpidr;
    u64 elr_phys;
    u64 far_phys;
    u64 sp_phys;
    void *extra;
};

struct uartproxy_msg_start {
    u32 reason;
    u32 code;
    void *info;
    void *reserved;
};

int uartproxy_run(struct uartproxy_msg_start *start);
void uartproxy_send_event(u16 event_type, void *data, u16 length);

#endif

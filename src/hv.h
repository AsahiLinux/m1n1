/* SPDX-License-Identifier: MIT */

#ifndef HV_H
#define HV_H

#include "iodev.h"
#include "types.h"
#include "uartproxy.h"

typedef bool(hv_hook_t)(u64 addr, u64 *val, bool write, int width);

#define MMIO_EVT_WIDTH GENMASK(2, 0)
#define MMIO_EVT_WRITE BIT(3)

struct hv_evt_mmiotrace {
    u32 flags;
    u32 reserved;
    u64 pc;
    u64 addr;
    u64 data;
};

struct hv_vm_proxy_hook_data {
    u32 flags;
    u32 id;
    u64 addr;
    u64 data;
};

typedef enum _hv_entry_type {
    HV_HOOK_VM = 1,
} hv_entry_type;

/* VM */
void hv_pt_init(void);
int hv_map(u64 from, u64 to, u64 size, u64 incr);
int hv_unmap(u64 from, u64 size);
int hv_map_hw(u64 from, u64 to, u64 size);
int hv_map_sw(u64 from, u64 to, u64 size);
int hv_map_hook(u64 from, hv_hook_t *hook, u64 size);
int hv_map_proxy_hook(u64 from, u64 id, u64 size);
u64 hv_translate(u64 addr, bool s1only, bool w);
u64 hv_pt_walk(u64 addr);
bool hv_handle_dabort(u64 *regs);

/* Virtual peripherals */
void hv_map_vuart(u64 base, iodev_id_t iodev);

/* Exceptions */
void hv_exc_proxy(u64 *regs, uartproxy_boot_reason_t reason, uartproxy_exc_code_t type,
                  void *extra);

/* HV main */
void hv_init(void);
void hv_start(void *entry, u64 regs[4]);

#endif

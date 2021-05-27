/* SPDX-License-Identifier: MIT */

#ifndef HV_H
#define HV_H

#include "iodev.h"
#include "types.h"
#include "uartproxy.h"

typedef bool(hv_hook_t)(u64 addr, u64 *val, bool write, int width);

#define MMIO_EVT_WIDTH GENMASK(4, 0)
#define MMIO_EVT_WRITE BIT(5)
#define MMIO_EVT_MULTI BIT(6)

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
    u64 data[2];
};

typedef enum _hv_entry_type {
    HV_HOOK_VM = 1,
    HV_VTIMER,
    HV_USER_INTERRUPT,
    HV_WDT_BARK,
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

/* WDT */
void hv_wdt_pet(void);
void hv_wdt_suspend(void);
void hv_wdt_resume(void);
void hv_wdt_init(void);
void hv_wdt_start(void);
void hv_wdt_stop(void);
void hv_wdt_breadcrumb(char c);

/* Utilities */
void hv_write_hcr(u64 val);
u64 hv_get_spsr(void);
void hv_set_spsr(u64 val);
u64 hv_get_esr(void);
u64 hv_get_far(void);
u64 hv_get_elr(void);
void hv_set_elr(u64 val);

/* HV main */
void hv_init(void);
void hv_start(void *entry, u64 regs[4]);
void hv_arm_tick(void);
void hv_tick(u64 *regs);

#endif

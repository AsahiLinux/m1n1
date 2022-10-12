/* SPDX-License-Identifier: MIT */

#ifndef HV_H
#define HV_H

#include "exception.h"
#include "iodev.h"
#include "types.h"
#include "uartproxy.h"

typedef bool(hv_hook_t)(struct exc_info *ctx, u64 addr, u64 *val, bool write, int width);

#define MMIO_EVT_ATTR  GENMASK(31, 24)
#define MMIO_EVT_CPU   GENMASK(23, 16)
#define MMIO_EVT_SH    GENMASK(15, 14)
#define MMIO_EVT_MULTI BIT(6)
#define MMIO_EVT_WRITE BIT(5)
#define MMIO_EVT_WIDTH GENMASK(4, 0)

struct hv_evt_mmiotrace {
    u32 flags;
    u32 reserved;
    u64 pc;
    u64 addr;
    u64 data;
};

struct hv_evt_irqtrace {
    u32 flags;
    u16 type;
    u16 num;
};

#define HV_MAX_RW_SIZE  64
#define HV_MAX_RW_WORDS (HV_MAX_RW_SIZE >> 3)

struct hv_vm_proxy_hook_data {
    u32 flags;
    u32 id;
    u64 addr;
    u64 data[HV_MAX_RW_WORDS];
};

typedef enum _hv_entry_type {
    HV_HOOK_VM = 1,
    HV_VTIMER,
    HV_USER_INTERRUPT,
    HV_WDT_BARK,
    HV_CPU_SWITCH,
} hv_entry_type;

/* VM */
void hv_pt_init(void);
int hv_map(u64 from, u64 to, u64 size, u64 incr);
int hv_unmap(u64 from, u64 size);
int hv_map_hw(u64 from, u64 to, u64 size);
int hv_map_sw(u64 from, u64 to, u64 size);
int hv_map_hook(u64 from, hv_hook_t *hook, u64 size);
u64 hv_translate(u64 addr, bool s1only, bool w, u64 *par_out);
u64 hv_pt_walk(u64 addr);
bool hv_handle_dabort(struct exc_info *ctx);
bool hv_pa_write(struct exc_info *ctx, u64 addr, u64 *val, int width);
bool hv_pa_read(struct exc_info *ctx, u64 addr, u64 *val, int width);
bool hv_pa_rw(struct exc_info *ctx, u64 addr, u64 *val, bool write, int width);

/* AIC events through tracing the MMIO event address */
bool hv_trace_irq(u32 type, u32 num, u32 count, u32 flags);

/* Virtual peripherals */
void hv_vuart_poll(void);
void hv_map_vuart(u64 base, int irq, iodev_id_t iodev);

/* Exceptions */
void hv_exc_proxy(struct exc_info *ctx, uartproxy_boot_reason_t reason, u32 type, void *extra);
void hv_set_time_stealing(bool enabled, bool reset);

/* WDT */
void hv_wdt_pet(void);
void hv_wdt_suspend(void);
void hv_wdt_resume(void);
void hv_wdt_init(void);
void hv_wdt_start(int cpu);
void hv_wdt_stop(void);
void hv_wdt_breadcrumb(char c);

/* Utilities */
void hv_write_hcr(u64 val);
u64 hv_get_spsr(void);
void hv_set_spsr(u64 val);
u64 hv_get_esr(void);
u64 hv_get_far(void);
u64 hv_get_elr(void);
u64 hv_get_afsr1(void);
void hv_set_elr(u64 val);

/* HV main */
void hv_init(void);
void hv_start(void *entry, u64 regs[4]);
void hv_start_secondary(int cpu, void *entry, u64 regs[4]);
void hv_rendezvous(void);
bool hv_switch_cpu(int cpu);
void hv_pin_cpu(int cpu);
void hv_arm_tick(void);
void hv_rearm(void);
void hv_maybe_exit(void);
void hv_tick(struct exc_info *ctx);

#endif

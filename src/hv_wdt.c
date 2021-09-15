/* SPDX-License-Identifier: MIT */

#include "hv.h"
#include "adt.h"
#include "smp.h"
#include "uart.h"
#include "utils.h"

#define WDT_TIMEOUT 1

static bool hv_wdt_active = false;
static bool hv_wdt_enabled = false;
static volatile u64 hv_wdt_timestamp = 0;
static u64 hv_wdt_timeout = 0;
static volatile u64 hv_wdt_breadcrumbs;

static int hv_wdt_cpu;

static u64 cpu_dbg_base = 0;

void hv_wdt_bark(void)
{
    u64 tmp = hv_wdt_breadcrumbs;
    uart_puts("HV watchdog: bark!");

    uart_printf("Breadcrumbs: ");
    for (int i = 56; i >= 0; i -= 8) {
        char c = (tmp >> i) & 0xff;
        if (c)
            uart_putchar(c);
    }
    uart_putchar('\n');

    uart_puts("Attempting to enter proxy");

    struct uartproxy_msg_start start = {
        .reason = START_HV,
        .code = HV_WDT_BARK,
    };

    uartproxy_run(&start);
    reboot();
}

void hv_wdt_main(void)
{
    while (hv_wdt_active) {
        if (hv_wdt_enabled) {
            sysop("dmb ish");
            u64 timestamp = hv_wdt_timestamp;
            sysop("isb");
            u64 now = mrs(CNTPCT_EL0);
            sysop("isb");
            if ((now - timestamp) > hv_wdt_timeout)
                hv_wdt_bark();
        }

        udelay(1000);

        sysop("dmb ish");
    }
}

void hv_wdt_pet(void)
{
    hv_wdt_timestamp = mrs(CNTPCT_EL0);
    sysop("dmb ish");
}

void hv_wdt_suspend(void)
{
    hv_wdt_enabled = false;
    sysop("dsb ish");
}

void hv_wdt_resume(void)
{
    hv_wdt_pet();
    hv_wdt_enabled = true;
    sysop("dsb ish");
}

void hv_wdt_breadcrumb(char c)
{
    u64 tmp = hv_wdt_breadcrumbs;
    tmp <<= 8;
    tmp |= c;
    hv_wdt_breadcrumbs = tmp;
    sysop("dmb ish");
}

void hv_wdt_init(void)
{
    int node = adt_path_offset(adt, "/cpus/cpu0");
    if (node < 0) {
        printf("Error getting /cpus/cpu0 node\n");
        return;
    }

    u64 reg[2];
    if (ADT_GETPROP_ARRAY(adt, node, "cpu-uttdbg-reg", reg) < 0) {
        printf("Error getting cpu-uttdbg-reg property\n");
        return;
    }

    cpu_dbg_base = reg[0];
}

void hv_wdt_start(int cpu)
{
    if (hv_wdt_active)
        return;

    hv_wdt_cpu = cpu;
    hv_wdt_breadcrumbs = 0;
    hv_wdt_timeout = mrs(CNTFRQ_EL0) * WDT_TIMEOUT;
    hv_wdt_pet();
    hv_wdt_active = true;
    hv_wdt_enabled = true;
    smp_call4(hv_wdt_cpu, hv_wdt_main, 0, 0, 0, 0);
}

void hv_wdt_stop(void)
{
    if (!hv_wdt_active)
        return;

    hv_wdt_active = false;
    smp_wait(hv_wdt_cpu);
}

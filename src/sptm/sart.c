/* SPDX-License-Identifier: MIT */
#include "private.h"

int debug_printf(const char *fmt, ...);

static u32 sart_config_off(u32 idx) {
    return idx * 4U;
}

static u32 sart_paddr_off(u32 idx) {
    return 0x40U + idx * 4U;
}

static u32 sart_size_off(u32 idx) {
    return 0x80U + idx * 4U;
}

static bool_t sart_valid_index(u32 idx) {
    return idx < SART_C_MAX_ENTRIES;
}

static u32 sart_flags_for_perm(u32 perm) {
    if (perm > 1)
        return 0;

    if (g_state.sart.version == 2 || g_state.sart.version == 3) {
        u32 access = perm ? 3U : 2U;
        return 0xc0U | access | (access << 2) | (access << 4);
    }

    return g_state.sart.flags_allow;
}

static struct sart_c_entry sart_live_entry(u32 idx) {
    struct sart_c_entry ent;
    ent.paddr = 0;
    ent.size = 0;
    ent.flags = 0;
    ent.guard = 0;
    if (!g_state.sart.base_pa || !sart_valid_index(idx))
        return ent;

    u32 cfg = *(volatile u32 *)(g_state.sart.base_pa + sart_config_off(idx));
    u32 paddr_raw = *(volatile u32 *)(g_state.sart.base_pa + sart_paddr_off(idx));
    u32 size_raw;

    if (g_state.sart.version == 3) {
        ent.flags = cfg & 0xffU;
        size_raw = *(volatile u32 *)(g_state.sart.base_pa + sart_size_off(idx));
    } else if (g_state.sart.version == 2) {
        ent.flags = (cfg >> 24) & 0xffU;
        size_raw = cfg & ((1U << 24) - 1U);
    } else {
        ent.flags = (cfg >> 24) & 0x1fU;
        size_raw = cfg & ((1U << 19) - 1U);
    }
    if (ent.flags && !g_state.sart.exclusive_bounds)
        size_raw++;

    ent.paddr = (u64)paddr_raw << g_state.sart.paddr_shift;
    ent.size = (u64)size_raw << g_state.sart.size_shift;
    return ent;
}

static bool_t sart_write_entry(u32 idx, u64 paddr, u64 size, u32 flags) {
    if (!g_state.sart.base_pa || !sart_valid_index(idx))
        return 0;
    if ((paddr & ((1UL << g_state.sart.paddr_shift) - 1UL)) ||
        (size & ((1UL << g_state.sart.size_shift) - 1UL)))
        return 0;

    u32 paddr_raw = (u32)(paddr >> g_state.sart.paddr_shift);
    u32 size_raw = (u32)(size >> g_state.sart.size_shift);
    if (size_raw > g_state.sart.size_max)
        return 0;
    if (flags && !g_state.sart.exclusive_bounds) {
        if (size_raw == 0)
            return 0;
        size_raw--;
    }

    if (g_state.sart.version == 3) {
        *(volatile u32 *)(g_state.sart.base_pa + sart_paddr_off(idx)) = paddr_raw;
        *(volatile u32 *)(g_state.sart.base_pa + sart_size_off(idx)) = size_raw;
        *(volatile u32 *)(g_state.sart.base_pa + sart_config_off(idx)) =
            flags & g_state.sart.flags_allow;
    } else {
        u32 cfg = ((flags & g_state.sart.flags_allow) << 24) | size_raw;
        *(volatile u32 *)(g_state.sart.base_pa + sart_paddr_off(idx)) = paddr_raw;
        *(volatile u32 *)(g_state.sart.base_pa + sart_config_off(idx)) = cfg;
    }
    barrier();
    return 1;
}

static bool_t sart_power_canary_acquire(u32 guard) {
    if (guard != 1 || g_state.sart.power_canary_pa == 0)
        return 1;

    if (g_state.sart.power_canary_count == 0)
        *(volatile u32 *)(g_state.sart.power_canary_pa +
                          g_state.sart.power_canary_offset) = 0xabfedeedU;
    g_state.sart.power_canary_count++;
    if (g_state.sart.power_canary_count == 0)
        return 0;
    return 1;
}

static bool_t sart_power_canary_release(u32 guard) {
    if (guard != 1 || g_state.sart.power_canary_pa == 0)
        return 1;
    if (g_state.sart.power_canary_count == 0)
        return 0;
    if (*(volatile u32 *)(g_state.sart.power_canary_pa +
                          g_state.sart.power_canary_offset) != 0xabfedeedU)
        return 0;
    g_state.sart.power_canary_count--;
    return 1;
}

static bool_t sart_validate_range(u64 paddr, u64 size) {
    if (size == 0)
        return 0;
    if (size & ((1UL << g_state.sart.size_shift) - 1UL))
        return 0;
    if (paddr & ((1UL << g_state.sart.paddr_shift) - 1UL))
        return 0;
    if ((paddr + size) < paddr)
        return 0;
    if ((size >> g_state.sart.size_shift) > g_state.sart.size_max)
        return 0;
    return 1;
}

static int sart_find_exact(u64 paddr, u64 size, struct sart_c_entry *out) {
    for (u32 i = 0; i < SART_C_MAX_ENTRIES; i++) {
        struct sart_c_entry ent = g_state.sart.shadow[i];
        if (!ent.flags)
            ent = sart_live_entry(i);
        if (ent.flags && ent.paddr == paddr && ent.size == size) {
            if (out)
                *out = ent;
            return (int)i;
        }
    }
    return -1;
}

static int sart_find_free(void) {
    for (u32 i = 0; i < SART_C_MAX_ENTRIES; i++) {
        if (g_state.sart.protected_mask & (1U << i))
            continue;
        if (g_state.sart.shadow[i].flags)
            continue;
        struct sart_c_entry ent = sart_live_entry(i);
        if (!ent.flags)
            return (int)i;
    }
    return -1;
}

static u64 sart_map_region(u64 *regs) {
    u64 paddr = regs[0];
    u64 size = regs[1];
    u32 perm = (u32)regs[2];
    u32 guard = (u32)regs[3];

    if (!sart_validate_range(paddr, size))
        return 1;
    if (perm > 1 || guard > 1)
        return 1;

    u32 flags = sart_flags_for_perm(perm);
    if (flags == 0)
        return 1;

    int idx = sart_find_free();
    if (idx < 0)
        return 1;

    if (!sart_power_canary_acquire(guard))
        return 1;
    if (!sart_write_entry((u32)idx, paddr, size, flags)) {
        sart_power_canary_release(guard);
        return 1;
    }

    g_state.sart.shadow[idx].paddr = paddr;
    g_state.sart.shadow[idx].size = size;
    g_state.sart.shadow[idx].flags = flags;
    g_state.sart.shadow[idx].guard = guard;
    if (g_state.nvme.debug_flags & NVME_DBG_PRINT_CALLS) {
        u64 ring = (g_state.ring_idx - 1) & 0x7fUL;
        debug_printf("C-SART map idx=%d pa=0x%lx size=0x%lx perm=%u guard=%u flags=0x%x pc=0x%lx lr=0x%lx\n",
                     idx, paddr, size, perm, guard, flags,
                     g_state.ring[ring][6], g_state.ring[ring][7]);
    }
    return SPTM_SUCCESS;
}

static u64 sart_unmap_region(u64 *regs) {
    u64 paddr = regs[0];
    u64 size = regs[1];
    struct sart_c_entry ent;

    if (!sart_validate_range(paddr, size))
        return 1;

    int idx = sart_find_exact(paddr, size, &ent);
    if (idx < 0)
        return 1;

    if (g_state.sart.protected_mask & (1U << (u32)idx))
        return SPTM_SUCCESS;

    u32 guard = g_state.sart.shadow[idx].guard;

    if (!sart_write_entry((u32)idx, 0, 0, 0))
        return 1;
    if (!sart_power_canary_release(guard))
        return 1;
    g_state.sart.shadow[idx].paddr = 0;
    g_state.sart.shadow[idx].size = 0;
    g_state.sart.shadow[idx].flags = 0;
    g_state.sart.shadow[idx].guard = 0;
    if (g_state.nvme.debug_flags & NVME_DBG_PRINT_CALLS) {
        u64 ring = (g_state.ring_idx - 1) & 0x7fUL;
        debug_printf("C-SART unmap idx=%d pa=0x%lx size=0x%lx guard=%u pc=0x%lx lr=0x%lx\n",
                     idx, paddr, size, guard,
                     g_state.ring[ring][6], g_state.ring[ring][7]);
    }
    return SPTM_SUCCESS;
}

bool_t sart_handle_table5(u32 endpoint, u64 *regs) {
    u64 rc = 1;

    if (!g_state.sart.enabled)
        return 0;
    if (endpoint >= SART_C_MAX_ENDPOINTS)
        return 0;

    g_state.sart.total_calls++;
    g_state.sart.ep_count[endpoint]++;
    for (u32 i = 0; i < 8; i++)
        g_state.sart.last[i] = regs[i];

    switch (endpoint) {
        case 0:
            /* sptm_sart_set_state(bool). XNU reaches this through
             * sart_ioctl(cmd=0x5ab7), leaving cmd/len in x1/x3. */
            g_state.sart.active = (u32)(regs[0] & 1UL);
            rc = SPTM_SUCCESS;
            if (g_state.nvme.debug_flags & NVME_DBG_PRINT_CALLS) {
                u64 ring = (g_state.ring_idx - 1) & 0x7fUL;
                debug_printf("C-SART state active=%u arg=0x%lx pc=0x%lx lr=0x%lx\n",
                             g_state.sart.active, regs[0],
                             g_state.ring[ring][6], g_state.ring[ring][7]);
            }
            break;
        case 1:
            rc = sart_map_region(regs);
            break;
        case 2:
            rc = sart_unmap_region(regs);
            break;
    }

    g_state.sart.last_rc = (u32)rc;
    if (rc != SPTM_SUCCESS)
        g_state.sart.violations++;
    regs[0] = rc;
    g_state.sart.fast_path_calls++;
    g_state.fast_path_calls++;
    sev();
    return 1;
}

/* SPDX-License-Identifier: MIT */
#include "private.h"
#include "../memory.h"

int debug_printf(const char *fmt, ...);
extern u64 hv_translate(u64 addr, _Bool s1only, _Bool w, u64 *par_out);

#define NVME_NORMAL_BAR_FROM_NVMMU(nvmmu) ((nvmmu) - 0x28000UL)
#define NVME_NORMAL_BAR_UNKNOWN_CTRL      0x24008U
#define NVME_NORMAL_BAR_LINEAR_SQ_CTRL    0x24908U
#define NVME_NORMAL_BAR_MODESEL           0x1304U

static inline void nvme_record_last(u32 endpoint, u64 rc, u64 *regs) {
    g_state.nvme.last[0] = endpoint;
    g_state.nvme.last[1] = rc;
    g_state.nvme.last[2] = regs[0];
    g_state.nvme.last[3] = regs[1];
    g_state.nvme.last[4] = regs[2];
    g_state.nvme.last[5] = regs[3];
    g_state.nvme.last[6] = regs[4];
    g_state.nvme.last[7] = regs[5];
    g_state.nvme.last_rc = (u32)rc;
}

static inline u64 nvme_violation(u32 endpoint, u64 *regs, u32 reason) {
    g_state.nvme.violations++;
    g_state.nvme.last[8] = reason;
    nvme_record_last(endpoint, NVME_STATUS_VIOLATION, regs);
    return NVME_STATUS_VIOLATION;
}

static inline bool_t nvme_mmio_base_valid(u64 base) {
    return base != 0 && base != ~0UL;
}

static inline void nvme_mmio_write32(u64 base, u32 off, u32 val) {
    *(volatile u32 *)(base + off) = val;
}

static inline u32 nvme_mmio_read32(u64 base, u32 off) {
    return *(volatile u32 *)(base + off);
}

static inline u64 nvme_mmio_read64(u64 base, u32 off) {
    u64 lo = nvme_mmio_read32(base, off);
    u64 hi = nvme_mmio_read32(base, off + 4);
    return lo | (hi << 32);
}

static inline void nvme_bar_write32(u32 off, u32 val) {
    nvme_mmio_write32(g_state.nvme.bar_pa, off, val);
}

static inline void nvme_bar_write64(u32 off, u64 val) {
    nvme_bar_write32(off, (u32)(val & 0xffffffffUL));
    nvme_bar_write32(off + 4, (u32)(val >> 32));
}

static inline void nvme_nvmmu_write32(u32 off, u32 val) {
    nvme_mmio_write32(g_state.nvme.nvmmu_pa, off, val);
}

static inline void nvme_nvmmu_write64(u32 off, u64 val) {
    nvme_nvmmu_write32(off, (u32)(val & 0xffffffffUL));
    nvme_nvmmu_write32(off + 4, (u32)(val >> 32));
}

static inline u64 nvme_cntpct(void) {
    u64 val;
    __asm__ volatile("mrs %0, CNTPCT_EL0" : "=r"(val));
    return val;
}

static inline u64 nvme_cntfrq(void) {
    u64 val;
    __asm__ volatile("mrs %0, CNTFRQ_EL0" : "=r"(val));
    return val;
}

static inline void nvme_wfe(void) {
    __asm__ volatile("wfe" ::: "memory");
}

static inline void nvme_dsb_sy(void) {
    sysop("dsb sy");
}

static void nvme_diag_sart_live_entry(u32 idx, u64 *paddr, u64 *size,
                                      u32 *flags) {
    u32 cfg;
    u32 paddr_raw;
    u32 size_raw;

    *paddr = 0;
    *size = 0;
    *flags = 0;

    if (!g_state.sart.base_pa || idx >= SART_C_MAX_ENTRIES)
        return;

    cfg = *(volatile u32 *)(g_state.sart.base_pa + idx * 4U);
    paddr_raw = *(volatile u32 *)(g_state.sart.base_pa + 0x40U + idx * 4U);

    if (g_state.sart.version == 3) {
        *flags = cfg & 0xffU;
        size_raw = *(volatile u32 *)(g_state.sart.base_pa + 0x80U + idx * 4U);
    } else if (g_state.sart.version == 2) {
        *flags = (cfg >> 24) & 0xffU;
        size_raw = cfg & ((1U << 24) - 1U);
    } else {
        *flags = (cfg >> 24) & 0x1fU;
        size_raw = cfg & ((1U << 19) - 1U);
    }

    if (*flags && !g_state.sart.exclusive_bounds)
        size_raw++;

    *paddr = (u64)paddr_raw << g_state.sart.paddr_shift;
    *size = (u64)size_raw << g_state.sart.size_shift;
}

static void nvme_diag_sart_readback_once(void) {
    static u32 printed;

    if (printed)
        return;
    printed = 1;

    if (!(g_state.nvme.debug_flags & NVME_DBG_PRINT_CALLS))
        return;

    debug_printf("C-NVME sart enabled=%u active=%u base=0x%lx protected=0x%x total=%lu last_rc=0x%x\n",
                 g_state.sart.enabled, g_state.sart.active,
                 g_state.sart.base_pa, g_state.sart.protected_mask,
                 g_state.sart.total_calls, g_state.sart.last_rc);
    debug_printf("C-NVME ranges trusted=0x%lx..0x%lx secondary=0x%lx..0x%lx asq=0x%lx acq=0x%lx admin_kva=0x%lx/0x%lx\n",
                 g_state.nvme.trusted_io_base,
                 g_state.nvme.trusted_io_base + g_state.nvme.trusted_io_size,
                 g_state.nvme.secondary_io_base,
                 g_state.nvme.secondary_io_base + g_state.nvme.secondary_io_size,
                 g_state.nvme.asq_pa_cached, g_state.nvme.acq_pa_cached,
                 g_state.nvme.admin_asq_kva, g_state.nvme.admin_acq_kva);

    for (u32 i = 0; i < SART_C_MAX_ENTRIES; i++) {
        u64 live_pa, live_size;
        u32 live_flags;
        struct sart_c_entry shadow = g_state.sart.shadow[i];

        nvme_diag_sart_live_entry(i, &live_pa, &live_size, &live_flags);
        if (!live_flags && !shadow.flags)
            continue;

        debug_printf("C-NVME sart[%u] live=0x%lx+0x%lx f=0x%x shadow=0x%lx+0x%lx f=0x%x g=%u prot=%u\n",
                     i, live_pa, live_size, live_flags,
                     shadow.paddr, shadow.size, shadow.flags, shadow.guard,
                     (g_state.sart.protected_mask & (1U << i)) ? 1U : 0U);
    }
}

static bool_t nvme_guest_read64(u64 va, u64 *out) {
    u64 pa;

    if ((va >> 48) != 0xffff || (va & 7))
        return 0;

    pa = hv_translate(va, 0, 0, 0);
    if (!pa)
        return 0;

    *out = *(volatile u64 *)pa;
    return 1;
}

static inline u16 nvme_load_le16(u8 *p) {
    return (u16)p[0] | ((u16)p[1] << 8);
}

static inline u32 nvme_load_le32(u8 *p) {
    return (u32)p[0] | ((u32)p[1] << 8) | ((u32)p[2] << 16) |
           ((u32)p[3] << 24);
}

static void nvme_print_backtrace(u64 fp) {
    debug_printf(" fp=0x%lx bt=", fp);

    for (u32 depth = 0; depth < 8; depth++) {
        u64 saved_fp;
        u64 saved_lr;

        if (!nvme_guest_read64(fp, &saved_fp) ||
            !nvme_guest_read64(fp + 8, &saved_lr))
            break;

        debug_printf("%s0x%lx", depth ? "," : "", saved_lr);

        if (saved_fp == fp || saved_fp < fp)
            break;
        fp = saved_fp;
    }
}

static void nvme_diag_ep5_readback_once(void) {
    static u32 printed;

    if (printed)
        return;
    printed = 1;

    if (!nvme_mmio_base_valid(g_state.nvme.bar_pa) ||
        !nvme_mmio_base_valid(g_state.nvme.nvmmu_pa)) {
        debug_printf("C-NVME ep5rb missing bar=0x%lx nvmmu=0x%lx\n",
                     g_state.nvme.bar_pa, g_state.nvme.nvmmu_pa);
        return;
    }

    nvme_dsb_sy();
    u32 aqa = nvme_mmio_read32(g_state.nvme.bar_pa, NVME_BAR_AQA);
    u64 asq = nvme_mmio_read64(g_state.nvme.bar_pa, NVME_BAR_ASQ);
    u64 acq = nvme_mmio_read64(g_state.nvme.bar_pa, NVME_BAR_ACQ);
    u32 ioqa = nvme_mmio_read32(g_state.nvme.bar_pa, NVME_BAR_IOQA);
    u32 cg = nvme_mmio_read32(g_state.nvme.nvmmu_pa, NVME_BAR_COASTGUARD);
    u64 cgasq = nvme_mmio_read64(g_state.nvme.nvmmu_pa, NVME_BAR_CG_ASQ);
    u64 cgacq = nvme_mmio_read64(g_state.nvme.nvmmu_pa, NVME_BAR_CG_ACQ);
    u64 normal_bar = NVME_NORMAL_BAR_FROM_NVMMU(g_state.nvme.nvmmu_pa);
    u32 unknown_ctrl = nvme_mmio_read32(normal_bar,
                                        NVME_NORMAL_BAR_UNKNOWN_CTRL);
    u32 linear_sq_ctrl = nvme_mmio_read32(normal_bar,
                                          NVME_NORMAL_BAR_LINEAR_SQ_CTRL);
    u32 modesel = nvme_mmio_read32(normal_bar, NVME_NORMAL_BAR_MODESEL);

    g_state.nvme.last[9] = 0xe5;
    g_state.nvme.last[10] = ((u64)aqa << 32) | ioqa;
    g_state.nvme.last[11] = asq;
    g_state.nvme.last[12] = acq;
    g_state.nvme.last[13] = ((u64)cg << 32) | unknown_ctrl;
    g_state.nvme.last[14] = cgasq;
    g_state.nvme.last[15] = cgacq;

    if (!(g_state.nvme.debug_flags &
          (NVME_DBG_PRINT_CALLS | NVME_DBG_PRINT_MINIMAL)))
        return;

    if (g_state.nvme.debug_flags & NVME_DBG_PRINT_MINIMAL) {
        debug_printf("C-NVME ep5min allowed=0x%x aqa=0x%x asq=0x%lx acq=0x%lx ioqa=0x%x csts=0x%x\n",
                     g_state.nvme.allowed_functions, aqa, asq, acq, ioqa,
                     nvme_mmio_read32(normal_bar, 0x1c));
    }

    if (g_state.nvme.debug_flags & NVME_DBG_PRINT_CALLS) {
        debug_printf("C-NVME ep5rb bar=0x%lx nvmmu=0x%lx allowed=0x%x\n",
                     g_state.nvme.bar_pa, g_state.nvme.nvmmu_pa,
                     g_state.nvme.allowed_functions);
        debug_printf("C-NVME ep5rb aqa=0x%x asq=0x%lx acq=0x%lx ioqa=0x%x\n",
                     aqa, asq, acq, ioqa);
        debug_printf("C-NVME ep5rb cg=0x%x cgasq=0x%lx cgacq=0x%lx cached aqa=0x%x ioqa=0x%x\n",
                     cg, cgasq, cgacq, g_state.nvme.aqa_cached,
                     g_state.nvme.ioqa_cached);
        debug_printf("C-NVME ep5rb normal unknown=0x%x linear=0x%x modesel=0x%x\n",
                     unknown_ctrl, linear_sq_ctrl, modesel);
        nvme_diag_sart_readback_once();
    }
}

static void nvme_diag_ep1_readback(u32 qid, u32 cid, u32 count, u16 nlb,
                                   u16 dir_bits, u8 mode, u64 first,
                                   u64 second_or_list) {
    u64 tcb_base = 0;
    u16 word0 = 0;
    u16 word1 = 0;
    u16 word2 = 0;
    u16 word3 = 0;

    if (qid < 2 && g_state.nvme.tcb_kva[qid] != 0) {
        tcb_base = g_state.nvme.tcb_kva[qid] + (u64)cid * 0x80UL;
        word0 = *(volatile u16 *)(tcb_base + 0);
        word1 = *(volatile u16 *)(tcb_base + 2);
        word2 = *(volatile u16 *)(tcb_base + 4);
        word3 = *(volatile u16 *)(tcb_base + 6);
    }

    g_state.nvme.last[9] = 0xe1;
    g_state.nvme.last[10] = ((u64)qid << 48) | ((u64)cid << 32) |
                             ((u64)count << 16) | nlb;
    g_state.nvme.last[11] = ((u64)dir_bits << 32) | mode;
    g_state.nvme.last[12] = first;
    g_state.nvme.last[13] = second_or_list;
    g_state.nvme.last[14] = tcb_base;
    g_state.nvme.last[15] = ((u64)word0 << 48) | ((u64)word1 << 32) |
                             ((u64)word2 << 16) | word3;

    if (!(g_state.nvme.debug_flags & NVME_DBG_PRINT_CALLS))
        return;

    debug_printf("C-NVME ep1rb qid=%u cid=%u count=%u nlb=0x%x dir=0x%x mode=%u\n",
                 qid, cid, count, nlb, dir_bits, mode);
    debug_printf("C-NVME ep1rb first=0x%lx second_or_list=0x%lx tcb=0x%lx words=%x,%x,%x,%x\n",
                 first, second_or_list, tcb_base, word0, word1, word2, word3);
}

static void nvme_diag_cmd_map(u32 qid, u32 cid, u32 count, u16 nlb,
                              u16 dir_bits, u8 mode, u64 first,
                              u64 second_or_list, u64 template_pa,
                              u64 seglist_pa, u8 *tmpl) {
    if (!(g_state.nvme.debug_flags & NVME_DBG_CMD_TRACE))
        return;

    debug_printf("C-NVME cmd map qid=%u cid=%u count=%u nlb=0x%x dir=0x%x mode=%u tpl=0x%lx seg=0x%lx prp1=0x%lx prp2=0x%lx\n",
                 qid, cid, count, nlb, dir_bits, mode, template_pa, seglist_pa,
                 first, second_or_list);
    debug_printf("C-NVME cmd map words=%x,%x,%x,%x,%x,%x,%x,%x cdw10=%x cdw11=%x cdw12=%x cdw13=%x\n",
                 nvme_load_le16(&tmpl[0x00]), nvme_load_le16(&tmpl[0x02]),
                 nvme_load_le16(&tmpl[0x04]), nvme_load_le16(&tmpl[0x06]),
                 nvme_load_le16(&tmpl[0x08]), nvme_load_le16(&tmpl[0x0a]),
                 nvme_load_le16(&tmpl[0x0c]), nvme_load_le16(&tmpl[0x0e]),
                 nvme_load_le32(&tmpl[0x28]), nvme_load_le32(&tmpl[0x2c]),
                 nvme_load_le32(&tmpl[0x30]), nvme_load_le32(&tmpl[0x34]));
}

static void nvme_diag_ep2_prp_readback(u32 qid, u32 cid, u32 count,
                                       u16 dir_bits, u8 mode, u64 first) {
    static u32 printed;
    u64 q0 = 0;
    u64 q1 = 0;
    u64 q2 = 0;
    u64 q3 = 0;
    u64 q178 = 0;
    u64 q180 = 0;
    u64 q188 = 0;
    u8 b180 = 0;

    if (!(g_state.nvme.debug_flags & NVME_DBG_PRINT_CALLS) ||
        printed >= 8 || count == 0 || first == 0)
        return;
    printed++;

    q0 = *(volatile u64 *)(first + 0x00);
    q1 = *(volatile u64 *)(first + 0x08);
    q2 = *(volatile u64 *)(first + 0x10);
    q3 = *(volatile u64 *)(first + 0x18);
    if (g_state.nvme.debug_flags & NVME_DBG_PRP_WINDOW) {
        q178 = *(volatile u64 *)(first + 0x178);
        q180 = *(volatile u64 *)(first + 0x180);
        q188 = *(volatile u64 *)(first + 0x188);
        b180 = *(volatile u8 *)(first + 0x180);
    }

    g_state.nvme.last[9] = 0xe2;
    g_state.nvme.last[10] = ((u64)qid << 48) | ((u64)cid << 32) |
                             ((u64)count << 16) | dir_bits;
    g_state.nvme.last[11] = ((u64)mode << 56) | first;
    g_state.nvme.last[12] = q0;
    g_state.nvme.last[13] = q1;
    g_state.nvme.last[14] = q2;
    g_state.nvme.last[15] = q3;

    debug_printf("C-NVME ep2rb qid=%u cid=%u count=%u dir=0x%x mode=%u prp1=0x%lx q=%lx,%lx,%lx,%lx\n",
                 qid, cid, count, dir_bits, mode, first, q0, q1, q2, q3);
    if (g_state.nvme.debug_flags & NVME_DBG_PRP_WINDOW) {
        debug_printf("C-NVME ep2rb180 qid=%u cid=%u prp1=0x%lx b180=0x%x q178=%lx q180=%lx q188=%lx\n",
                     qid, cid, first, b180, q178, q180, q188);
    }
}

static void nvme_diag_cmd_unmap(u32 qid, u32 cid, u32 retry, u32 count,
                                u16 dir_bits, u8 mode, u64 first,
                                u64 second_or_list) {
    if (!(g_state.nvme.debug_flags & NVME_DBG_CMD_TRACE))
        return;

    debug_printf("C-NVME cmd unmap qid=%u cid=%u retry=%u count=%u dir=0x%x mode=%u prp1=0x%lx prp2=0x%lx\n",
                 qid, cid, retry, count, dir_bits, mode, first,
                 second_or_list);
}

static inline bool_t nvme_range_contains(u64 base, u64 size, u64 pa, u64 len) {
    if (base == 0 || size == 0)
        return 0;
    if (len == 0)
        len = 1;
    if (pa < base)
        return 0;
    if ((pa - base) > size)
        return 0;
    if (len > (size - (pa - base)))
        return 0;
    return 1;
}

static inline bool_t nvme_in_trusted_io(u64 pa, u64 len) {
    if (nvme_range_contains(g_state.nvme.trusted_io_base,
                            g_state.nvme.trusted_io_size, pa, len))
        return 1;
    if (nvme_range_contains(g_state.nvme.secondary_io_base,
                            g_state.nvme.secondary_io_size, pa, len))
        return 1;
    if (g_state.nvme.trusted_io_base == 0 && g_state.nvme.trusted_io_size == 0 &&
        g_state.nvme.secondary_io_base == 0 && g_state.nvme.secondary_io_size == 0)
        return 1;
    return 0;
}

static inline bool_t nvme_validate_page_pa(u64 pa, u64 page_size) {
    if (pa == 0)
        return 0;
    if (pa & (page_size - 1))
        return 0;
    if (!nvme_in_trusted_io(pa, page_size))
        return 0;
    return 1;
}

static inline bool_t nvme_validate_ans_sha_page_pa(u64 pa) {
    if (!nvme_validate_page_pa(pa, NVME_PRP_PAGE_SIZE))
        return 0;
    if (pa & 0x3000UL)
        return 0;
    return 1;
}

static inline bool_t nvme_validate_buffer(u64 pa, u64 len) {
    if (pa == 0)
        return 0;
    return nvme_in_trusted_io(pa, len ? len : 1);
}

static inline bool_t nvme_in_main_ram(u64 pa, u64 len) {
    return nvme_range_contains(g_state.nvme.secondary_io_base,
                               g_state.nvme.secondary_io_size,
                               pa, len ? len : 1);
}

static inline bool_t nvme_validate_guest_copy_buffer(u64 pa, u64 len) {
    if (pa == 0 || len == 0)
        return 0;
    if (!nvme_in_main_ram(pa, len))
        return 0;
    if (((pa & (NVME_PAGE_SIZE - 1)) + len) > NVME_PAGE_SIZE)
        return 0;
    return 1;
}

static inline bool_t nvme_validate_prp(u64 pa, bool_t allow_offset) {
    if (!nvme_validate_buffer(pa, 1))
        return 0;
    if (!allow_offset && (pa & (NVME_PRP_PAGE_SIZE - 1)))
        return 0;
    return 1;
}

static inline bool_t nvme_func_enter(u32 idx) {
    if (idx >= 16)
        return 0;
    if (g_state.nvme.func_state[idx] == 1)
        return 0;
    g_state.nvme.func_state[idx] = 1;
    return 1;
}

static inline void nvme_func_exit(u32 idx) {
    if (idx < 16)
        g_state.nvme.func_state[idx] = 0;
}

static inline bool_t nvme_cid_enter(u32 cid) {
    if (cid >= g_state.nvme.max_cid || cid >= NVME_C_MAX_CID)
        return 0;
    if (g_state.nvme.cid_mode[cid] != NVME_CID_AVAILABLE)
        return 0;
    g_state.nvme.cid_mode[cid] = NVME_CID_BUSY;
    return 1;
}

static inline void nvme_cid_clear(u32 cid) {
    if (cid < g_state.nvme.max_cid && cid < NVME_C_MAX_CID)
        g_state.nvme.cid_mode[cid] = NVME_CID_AVAILABLE;
}

static void nvme_diag_queue_summary(u32 event, u32 qid, u32 cid, u64 rc) {
    static u64 last_map1;
    static u64 last_unmap1;
    u32 zero = 0;
    u32 busy = 0;
    u32 active0 = 0;
    u32 active1 = 0;
    u32 retry0 = 0;
    u32 retry1 = 0;
    u32 other = 0;
    u32 max_cid = g_state.nvme.max_cid;
    bool_t force;

    if (!(g_state.nvme.debug_flags & NVME_DBG_SUMMARY))
        return;

    if (max_cid > NVME_C_MAX_CID)
        max_cid = NVME_C_MAX_CID;

    force = (event >= 3U);
    if (!force) {
        if (event == 1U && qid == 1) {
            u64 n = g_state.nvme.ep_count[10];
            if ((n & 31UL) != 0 || n == last_map1)
                return;
            last_map1 = n;
        } else if (event == 2U && qid == 1) {
            u64 n = g_state.nvme.ep_count[12];
            if ((n & 31UL) != 0 || n == last_unmap1)
                return;
            last_unmap1 = n;
        } else {
            return;
        }
    }

    for (u32 i = 0; i < max_cid; i++) {
        switch (g_state.nvme.cid_mode[i]) {
            case NVME_CID_AVAILABLE: zero++; break;
            case NVME_CID_BUSY: busy++; break;
            case 0x03: active0++; break;
            case 0x13: active1++; break;
            case 0x04: retry0++; break;
            case 0x14: retry1++; break;
            default: other++; break;
        }
    }

    debug_printf("C-NVME qsum ev=%u qid=%u cid=%u rc=0x%lx "
                 "map0=%lu map1=%lu unmap0=%lu unmap1=%lu "
                 "retry=%lu mapfail=%lu unmapfail=%lu "
                 "zero=%u busy=%u act0=%u act1=%u retry0=%u retry1=%u other=%u "
                 "tl=%u viol=%u\n",
                 event, qid, cid, rc,
                 g_state.nvme.ep_count[9], g_state.nvme.ep_count[10],
                 g_state.nvme.ep_count[11], g_state.nvme.ep_count[12],
                 g_state.nvme.ep_count[13], g_state.nvme.ep_count[14],
                 g_state.nvme.ep_count[15],
                 zero, busy, active0, active1, retry0, retry1, other,
                 g_state.nvme.tl_timeouts, g_state.nvme.violations);
}

static inline u32 nvme_ft_read_u32(u64 pa, u64 off) {
    u64 idx;
    if (!ft_get_idx(pa, &idx))
        return 0;
    volatile u32 *cnt =
        (volatile u32 *)(g_state.frame_table_base + idx * 16 + off);
    return *cnt;
}

static void nvme_diag_iommu_ref(const char *op, u64 pa, u8 mode,
                                u32 before, u32 after) {
    static u32 printed;
    u64 idx = 0;

    if (!(g_state.nvme.debug_flags & NVME_DBG_IOMMU))
        return;
    if (printed >= 96)
        return;
    printed++;

    bool_t indexed = ft_get_idx(pa, &idx);
    debug_printf("C-NVME iommu %s pa=0x%lx mode=%u indexed=%u idx=0x%lx "
                 "type=0x%x page_ref=%u table_ref=%u ro=%u rw=%u "
                 "before=%u after=%u\n",
                 op, pa, mode, indexed, idx, ft_get_type(pa),
                 ft_read_u16(pa, 4), ft_read_u16(pa, 8),
                 nvme_ft_read_u32(pa, 8), nvme_ft_read_u32(pa, 12),
                 before, after);
}

static inline bool_t nvme_iommu_acquire(u64 pa, u8 mode) {
    u64 off = (mode == NVME_IOMMU_RO) ? 8 : 12;
    u32 before = nvme_ft_read_u32(pa, off);
    if (mode == NVME_IOMMU_RO)
        ft_inc_u32(pa, 8);
    else
        ft_inc_u32(pa, 12);
    nvme_diag_iommu_ref("acq", pa, mode, before, nvme_ft_read_u32(pa, off));
    return 1;
}

static inline void nvme_iommu_release_mode(u64 pa, u8 mode) {
    if (pa == 0)
        return;
    u64 off = (mode == NVME_IOMMU_RO) ? 8 : 12;
    u32 before = nvme_ft_read_u32(pa, off);
    if (mode == NVME_IOMMU_RO)
        ft_dec_u32(pa, 8);
    else
        ft_dec_u32(pa, 12);
    nvme_diag_iommu_ref("rel", pa, mode, before, nvme_ft_read_u32(pa, off));
}

static inline void nvme_store_le64(u8 *p, u64 v) {
    for (u32 i = 0; i < 8; i++)
        p[i] = (u8)(v >> (i * 8));
}

static bool_t nvme_tl_wa_wait(u32 qid, u32 cid, u16 dir_bits, bool_t retry) {
    if (!(g_state.nvme.quirks & NVME_QUIRK_TL_WA) || !(dir_bits & 0x300U))
        return 1;
    if (!nvme_mmio_base_valid(g_state.nvme.tl_status_pa) ||
        !nvme_mmio_base_valid(g_state.nvme.tl_mask_pa) ||
        !nvme_mmio_base_valid(g_state.nvme.tl_ctrl_pa))
        return 0;
    if (g_state.nvme.tl_num_sl > 16)
        return 0;

    if (!retry) {
        bool_t h2f = (dir_bits & 0x100U) != 0;
        u32 mask = h2f ? 0x800000U : 0x80U;
        u32 ctrl = h2f ? 0x400000U : 0x40U;

        nvme_mmio_write32(g_state.nvme.tl_mask_pa, 0x4, mask);
        nvme_mmio_write32(g_state.nvme.tl_mask_pa, 0xc, mask);
        nvme_mmio_write32(g_state.nvme.tl_ctrl_pa, 0x4, ctrl);
        g_state.nvme.tl_slot_done[cid] = 0;
    }

    nvme_dsb_sy();
    u64 start = nvme_cntpct();
    u64 freq = nvme_cntfrq();
    u64 timeout = (freq & ~0x1fUL) / 4000;
    u64 nap_threshold = (freq & ~0x1fUL) / 100000;
    u64 nap_period = (freq & ~0x7fUL) / 10000000;
    if (timeout == 0)
        timeout = 1;
    if (nap_threshold == 0)
        nap_threshold = 1;
    if (nap_period == 0)
        nap_period = 1;

    for (;;) {
        u16 done = g_state.nvme.tl_slot_done[cid];
        u32 complete = 0;

        for (u32 slot = 0; slot < g_state.nvme.tl_num_sl; slot++) {
            u16 bit = (u16)(1U << slot);

            if (done & bit) {
                complete++;
                continue;
            }

            u32 status = nvme_mmio_read32(g_state.nvme.tl_status_pa,
                                          slot * 0x10000U);
            u32 pending;
            if (dir_bits & 0x100U)
                pending = (~status) & 0xffU;
            else
                pending = (~status) & 0x7f0000U;
            if (pending == 0) {
                done |= bit;
                complete++;
            }
        }
        g_state.nvme.tl_slot_done[cid] = done;

        if (complete == g_state.nvme.tl_num_sl) {
            nvme_mmio_write32(g_state.nvme.tl_mask_pa, 0x4, 0x800080U);
            nvme_mmio_write32(g_state.nvme.tl_mask_pa, 0xc, 0x800080U);
            nvme_mmio_write32(g_state.nvme.tl_ctrl_pa, 0x4, 0x400040U);
            g_state.nvme.tl_slot_done[cid] = 0;
            return 1;
        }

        nvme_dsb_sy();
        u64 elapsed = nvme_cntpct() - start;
        if (elapsed >= timeout)
            break;
        if (elapsed > nap_threshold) {
            nvme_dsb_sy();
            u64 nap = nvme_cntpct();
            while ((nvme_cntpct() - nap) < nap_period) {
                nvme_dsb_sy();
                nvme_wfe();
            }
        }
    }

    g_state.nvme.tl_timeouts++;
    g_state.nvme.cid_mode[cid] = (u8)((qid << 4) | 0x4U);
    return 0;
}

static u64 nvme_ep3_validate(u64 *regs) {
    u32 queue_entries = (u32)regs[0];
    u32 proto = (u32)regs[1];
    u32 expected_proto = g_state.nvme.linear_sq ? 2U : 1U;

    if (!(g_state.nvme.allowed_functions & NVME_AF_QUEUE_VALIDATE))
        return nvme_violation(NVME_FN_VALIDATE_QENTRIES, regs, 1);
    if (queue_entries != g_state.nvme.queue_count || proto != expected_proto)
        return nvme_violation(NVME_FN_VALIDATE_QENTRIES, regs, 3);
    return SPTM_SUCCESS;
}

static u64 nvme_ep0_enable_coastguard(u64 *regs) {
    if (!(g_state.nvme.allowed_functions & NVME_AF_ENABLE_COASTGUARD))
        return nvme_violation(NVME_FN_ENABLE_COASTGUARD, regs, 1);
    if (g_state.nvme.admin_asq_kva == 0 || g_state.nvme.admin_acq_kva == 0)
        return nvme_violation(NVME_FN_ENABLE_COASTGUARD, regs, 2);
    if (!nvme_mmio_base_valid(g_state.nvme.nvmmu_pa))
        return nvme_violation(NVME_FN_ENABLE_COASTGUARD, regs, 3);

    nvme_nvmmu_write64(NVME_BAR_CG_ASQ, g_state.nvme.admin_asq_kva);
    nvme_nvmmu_write64(NVME_BAR_CG_ACQ, g_state.nvme.admin_acq_kva);
    nvme_nvmmu_write32(NVME_BAR_COASTGUARD, NVME_COASTGUARD_VALUE);
    nvme_dsb_sy();

    if (g_state.nvme.packed_writes_present)
        g_state.nvme.allowed_functions |= NVME_AF_BAR_ADMIN_Q;
    else
        g_state.nvme.allowed_functions |= (NVME_AF_TCB_REGISTER |
                                           NVME_AF_TCB_INVALIDATE);
    return SPTM_SUCCESS;
}

static u64 nvme_ep4_admin_queue(u64 *regs) {
    u64 asq_pa = regs[0];
    u32 asq_size = (u32)regs[1];
    u64 acq_pa = regs[2];
    u32 acq_size = (u32)regs[3];
    u32 aqa;
    u64 rc = NVME_STATUS_VIOLATION;
    bool_t new_asq = 0;
    bool_t new_acq = 0;

    if (!(g_state.nvme.allowed_functions & NVME_AF_BAR_ADMIN_Q))
        return nvme_violation(NVME_FN_BAR_ADMIN_QUEUE_REGS, regs, 1);
    if (!nvme_func_enter(4))
        return nvme_violation(NVME_FN_BAR_ADMIN_QUEUE_REGS, regs, 2);
    if (!nvme_mmio_base_valid(g_state.nvme.bar_pa))
        goto out;

    if (asq_size > NVME_QSIZE_MAX || acq_size > NVME_QSIZE_MAX)
        goto out;
    aqa = (asq_size & 0xfffU) | ((acq_size & 0xfffU) << 16);
    if (g_state.nvme.aqa_cached != ~0U &&
        g_state.nvme.aqa_cached != aqa)
        goto out;
    if (g_state.nvme.asq_pa_cached != ~0UL &&
        g_state.nvme.asq_pa_cached != asq_pa)
        goto out;
    if (g_state.nvme.acq_pa_cached != ~0UL &&
        g_state.nvme.acq_pa_cached != acq_pa)
        goto out;
    if (!nvme_validate_page_pa(asq_pa, NVME_PRP_PAGE_SIZE) ||
        !nvme_validate_page_pa(acq_pa, NVME_PRP_PAGE_SIZE))
        goto out;
    new_asq = g_state.nvme.asq_pa_cached == ~0UL;
    new_acq = g_state.nvme.acq_pa_cached == ~0UL;
    if (new_asq && !nvme_iommu_acquire(asq_pa, NVME_IOMMU_RW))
        goto out;
    if (new_acq && !nvme_iommu_acquire(acq_pa, NVME_IOMMU_RW)) {
        if (new_asq)
            nvme_iommu_release_mode(asq_pa, NVME_IOMMU_RW);
        goto out;
    }
    nvme_bar_write32(NVME_BAR_AQA, aqa);
    nvme_bar_write64(NVME_BAR_ASQ, asq_pa);
    nvme_bar_write64(NVME_BAR_ACQ, acq_pa);
    barrier();

    g_state.nvme.aqa_cached = aqa;
    g_state.nvme.asq_pa_cached = asq_pa;
    g_state.nvme.acq_pa_cached = acq_pa;
    g_state.nvme.allowed_functions |= (NVME_AF_TCB_REGISTER |
                                       NVME_AF_TCB_INVALIDATE |
                                       NVME_AF_BAR_IOQA);
    rc = SPTM_SUCCESS;
out:
    nvme_func_exit(4);
    if (rc != SPTM_SUCCESS)
        return nvme_violation(NVME_FN_BAR_ADMIN_QUEUE_REGS, regs, 3);
    return rc;
}

static u64 nvme_ep5_ioqa(u64 *regs) {
    u32 iosq_size = (u32)regs[0];
    u32 iocq_size = (u32)regs[1];
    u32 ioqa;
    u64 rc = NVME_STATUS_VIOLATION;

    if (!(g_state.nvme.allowed_functions & NVME_AF_BAR_IOQA))
        return nvme_violation(NVME_FN_BAR_IOQA_REG, regs, 1);
    if (!nvme_func_enter(5))
        return nvme_violation(NVME_FN_BAR_IOQA_REG, regs, 2);
    if (!nvme_mmio_base_valid(g_state.nvme.bar_pa))
        goto out;

    if (iosq_size > g_state.nvme.queue_count ||
        iocq_size > g_state.nvme.queue_count)
        goto out;
    ioqa = (iosq_size & 0xffffU) | ((iocq_size & 0xffffU) << 16);
    if (g_state.nvme.ioqa_cached != ~0U && g_state.nvme.ioqa_cached != ioqa)
        goto out;
    nvme_bar_write32(NVME_BAR_IOQA, ioqa);
    barrier();
    g_state.nvme.ioqa_cached = ioqa;
    if (g_state.nvme.packed_writes_present)
        g_state.nvme.allowed_functions |= NVME_AF_BAR_IOCQ;
    rc = SPTM_SUCCESS;
out:
    nvme_func_exit(5);
    if (rc != SPTM_SUCCESS)
        return nvme_violation(NVME_FN_BAR_IOQA_REG, regs, 3);
    return rc;
}

static u64 nvme_ep6_iosq(u64 *regs) {
    u64 iosq_pa = regs[0];
    u64 rc = NVME_STATUS_VIOLATION;

    if (!(g_state.nvme.allowed_functions & NVME_AF_BAR_IOSQ))
        return nvme_violation(NVME_FN_BAR_IOSQ_REG, regs, 1);
    if (!nvme_func_enter(6))
        return nvme_violation(NVME_FN_BAR_IOSQ_REG, regs, 2);
    if (!nvme_mmio_base_valid(g_state.nvme.bar_pa))
        goto out;
    if (!nvme_validate_page_pa(iosq_pa, NVME_PRP_PAGE_SIZE))
        goto out;
    if (g_state.nvme.iosq_pa_cached != ~0UL &&
        g_state.nvme.iosq_pa_cached != iosq_pa)
        goto out;
    if (g_state.nvme.iosq_pa_cached == ~0UL &&
        !nvme_iommu_acquire(iosq_pa, NVME_IOMMU_RW))
        goto out;
    nvme_bar_write64(NVME_BAR_IOSQ_BASE, iosq_pa);
    barrier();
    g_state.nvme.iosq_pa_cached = iosq_pa;
    rc = SPTM_SUCCESS;
out:
    nvme_func_exit(6);
    if (rc != SPTM_SUCCESS)
        return nvme_violation(NVME_FN_BAR_IOSQ_REG, regs, 3);
    return rc;
}

static u64 nvme_ep7_iocq(u64 *regs) {
    u64 iocq_pa = regs[0];
    u64 rc = NVME_STATUS_VIOLATION;

    if (!(g_state.nvme.allowed_functions & NVME_AF_BAR_IOCQ))
        return nvme_violation(NVME_FN_BAR_IOCQ_REG, regs, 1);
    if (!nvme_func_enter(7))
        return nvme_violation(NVME_FN_BAR_IOCQ_REG, regs, 2);
    if (!nvme_mmio_base_valid(g_state.nvme.bar_pa))
        goto out;
    if (!nvme_validate_page_pa(iocq_pa, NVME_PRP_PAGE_SIZE))
        goto out;
    if (g_state.nvme.iocq_pa_cached != ~0UL &&
        g_state.nvme.iocq_pa_cached != iocq_pa)
        goto out;
    if (g_state.nvme.iocq_pa_cached == ~0UL &&
        !nvme_iommu_acquire(iocq_pa, NVME_IOMMU_RW))
        goto out;
    nvme_bar_write64(NVME_BAR_IOCQ_BASE, iocq_pa);
    barrier();
    g_state.nvme.iocq_pa_cached = iocq_pa;
    if (g_state.nvme.packed_writes_present)
        g_state.nvme.allowed_functions |= NVME_AF_BAR_IOSQ;
    rc = SPTM_SUCCESS;
out:
    nvme_func_exit(7);
    if (rc != SPTM_SUCCESS)
        return nvme_violation(NVME_FN_BAR_IOCQ_REG, regs, 3);
    return rc;
}

static u64 nvme_ep8_ans_sha(u64 *regs) {
    u64 ans_sha_pa = regs[0];
    u64 ans_sha_size = regs[1];
    u32 pwc = (u32)regs[2];
    u32 pwc_mask = pwc & 3U;
    u64 rc = NVME_STATUS_VIOLATION;

    if (!(g_state.nvme.allowed_functions & NVME_AF_ANS_SHA))
        return nvme_violation(NVME_FN_ANS_SHA_REG, regs, 1);
    if (!g_state.nvme.ans_sha_present)
        return nvme_violation(NVME_FN_ANS_SHA_REG, regs, 2);
    if (!nvme_func_enter(8))
        return nvme_violation(NVME_FN_ANS_SHA_REG, regs, 3);
    if (ans_sha_size != (u64)g_state.nvme.queue_count * NVME_PAGE_SIZE)
        goto out;
    if (g_state.nvme.ans_sha_pa_cached != ~0UL &&
        (g_state.nvme.ans_sha_pa_cached != ans_sha_pa ||
         g_state.nvme.ans_sha_pwc_cached != pwc_mask))
        goto out;
    if (g_state.nvme.ans_sha_pwc_cached != ~0U &&
        g_state.nvme.ans_sha_pwc_cached != pwc_mask)
        goto out;
    for (u64 off = 0; off < ans_sha_size; off += NVME_PAGE_SIZE) {
        if (!nvme_validate_ans_sha_page_pa(ans_sha_pa + off))
            goto out;
    }
    if (g_state.nvme.ans_sha_pa_cached == ~0UL) {
        for (u64 off = 0; off < ans_sha_size; off += NVME_PAGE_SIZE) {
            if (!nvme_iommu_acquire(ans_sha_pa + off, NVME_IOMMU_RW))
                goto out;
        }
    }
    if (g_state.nvme.ans_sha_kva != 0) {
        if (g_state.nvme.ans_sha_pwc_cached == ~0U)
            g_state.nvme.ans_sha_pwc_cached = pwc_mask;
        *(volatile u32 *)(g_state.nvme.ans_sha_kva + 0x0) =
            (u32)(ans_sha_pa >> 14);
        *(volatile u32 *)(g_state.nvme.ans_sha_kva + 0x4) =
            g_state.nvme.ans_sha_pwc_cached;
    } else {
        goto out;
    }
    barrier();
    g_state.nvme.ans_sha_pa_cached = ans_sha_pa;
    rc = SPTM_SUCCESS;
out:
    nvme_func_exit(8);
    if (rc != SPTM_SUCCESS)
        return nvme_violation(NVME_FN_ANS_SHA_REG, regs, 4);
    return rc;
}

static u64 nvme_ep1_map_pages(u64 *regs) {
    u32 qid = (u32)regs[0];
    u32 cid = (u32)regs[1];
    u64 template_pa = regs[2];
    u64 seglist_pa = regs[3];
    u32 count = (u32)regs[4];
    u8 tmpl[0x80];
    u16 nlb;
    u16 dir_bits;
    u8 mode;
    u64 first = 0, second = 0, second_or_list = 0;
    u32 acquired_count = 0;
    bool_t cid_entered = 0;

    if (!(g_state.nvme.allowed_functions & NVME_AF_TCB_REGISTER))
        return nvme_violation(NVME_FN_MAP_PAGES, regs, 1);
    if (qid > 1 || cid >= g_state.nvme.queue_count ||
        cid >= g_state.nvme.max_cid || cid >= NVME_C_MAX_CID ||
        count > 0x101U)
        return nvme_violation(NVME_FN_MAP_PAGES, regs, 2);
    if (!nvme_cid_enter(cid))
        return nvme_violation(NVME_FN_MAP_PAGES, regs, 3);
    cid_entered = 1;

    if (!nvme_validate_guest_copy_buffer(template_pa, 0x80))
        goto fail;
    for (u32 i = 0; i < 0x80; i++)
        tmpl[i] = *(volatile u8 *)(template_pa + i);

    nlb = nvme_load_le16(&tmpl[4]);
    dir_bits = nvme_load_le16(&tmpl[0]) & 0x1f00U;
    if ((g_state.nvme.quirks & NVME_QUIRK_TL_WA) &&
        (dir_bits & 0x300U) == 0x300U)
        goto fail;
    mode = (dir_bits & 0x100U) ? NVME_IOMMU_RW : NVME_IOMMU_RO;
    g_state.nvme.tcb_dir[cid] = dir_bits;
    g_state.nvme.tcb_nlb[cid] = nlb;
    for (u32 i = 0x18; i < 0x28; i++)
        tmpl[i] = 0;

    if (count == 0) {
        if (nlb != 0)
            goto fail;
    } else {
        bool_t first_aligned;
        u32 expected_nlb;

        if (!nvme_validate_guest_copy_buffer(seglist_pa, (u64)count * 8UL))
            goto fail;
        first = *(volatile u64 *)seglist_pa;
        first_aligned = ((first & (NVME_PRP_PAGE_SIZE - 1)) == 0);
        if (!first_aligned && count == 1)
            goto fail;
        expected_nlb = count - (first_aligned ? 1U : 2U);
        if (expected_nlb != nlb)
            goto fail;
        if (!nvme_validate_prp(first, 1) ||
            !nvme_iommu_acquire(first, mode))
            goto fail;
        acquired_count = 1;
        nvme_store_le64(&tmpl[0x18], first);

        if (count >= 2) {
            second = *(volatile u64 *)(seglist_pa + 8);
            if (!nvme_validate_prp(second, 0) ||
                !nvme_iommu_acquire(second, mode))
                goto fail;
            acquired_count = 2;
            if (count == 2) {
                second_or_list = second;
                nvme_store_le64(&tmpl[0x20], second);
            } else {
                u64 prp_list = g_state.nvme.prp_list_kva + (u64)cid * 0x800UL;
                if (g_state.nvme.prp_list_kva == 0)
                    goto fail;
                second_or_list = prp_list;
                nvme_store_le64(&tmpl[0x20], prp_list);
                for (u32 i = 1; i < count; i++) {
                    u64 pa = *(volatile u64 *)(seglist_pa + (u64)i * 8UL);
                    if (!nvme_validate_prp(pa, 0))
                        goto fail;
                    if (i > 1) {
                        if (!nvme_iommu_acquire(pa, mode))
                            goto fail;
                        acquired_count++;
                    }
                    *(volatile u64 *)(prp_list + (u64)(i - 1) * 8UL) = pa;
                }
            }
        }
    }

    tmpl[0] = 0;
    tmpl[1] = 0;

    if (g_state.nvme.tcb_kva[qid] != 0) {
        u64 tcb_base = g_state.nvme.tcb_kva[qid] + (u64)cid * 0x80UL;
        if (*(volatile u16 *)tcb_base != 0 ||
            *(volatile u16 *)(tcb_base + 4) != 0)
            goto fail;
        for (u32 i = 0; i < 0x80; i++)
            *(volatile u8 *)(tcb_base + i) = tmpl[i];
        *(volatile u16 *)(tcb_base + 2) = (u16)cid;
        if (g_state.nvme.linear_sq) {
            barrier();
            *(volatile u16 *)tcb_base = dir_bits;
        }
    }

    if ((g_state.nvme.quirks & NVME_QUIRK_PRP_FLUSH_WA) && count > 0x10U) {
        u64 prp_list = g_state.nvme.prp_list_kva + (u64)cid * 0x800UL;
        u32 flush_len = 0x1000U;

        if (count < 0x100U)
            flush_len = ((count * 8U) + 0x7fU) & 0x1f80U;
        sysop("dsb sy");
        if (flush_len != 0)
            dc_civac_range((void *)prp_list, flush_len);
    }

    g_state.nvme.tcb_count[cid] = count;
    g_state.nvme.tcb_mode[cid] = mode;
    g_state.nvme.tcb_qid[cid] = (u8)qid;
    g_state.nvme.tcb_prp1[cid] = first;
    g_state.nvme.tcb_prp2[cid] = second_or_list;
    g_state.nvme.cid_mode[cid] =
        (u8)((qid << 4) | (g_state.nvme.linear_sq ? 0x3U : 0x2U));
    barrier();
    if (qid < 2)
        g_state.nvme.ep_count[9 + qid]++;
    nvme_diag_queue_summary(1, qid, cid, SPTM_SUCCESS);
    nvme_diag_cmd_map(qid, cid, count, nlb, dir_bits, mode, first,
                      second_or_list, template_pa, seglist_pa, tmpl);
    nvme_diag_ep1_readback(qid, cid, count, nlb, dir_bits, mode, first,
                           second_or_list);
    return SPTM_SUCCESS;

fail:
    if (cid_entered)
        nvme_cid_clear(cid);
    if (acquired_count >= 1)
        nvme_iommu_release_mode(first, mode);
    if (acquired_count >= 2)
        nvme_iommu_release_mode(second, mode);
    for (u32 i = 2; i < acquired_count; i++) {
        u64 pa = *(volatile u64 *)(seglist_pa + (u64)i * 8UL);
        nvme_iommu_release_mode(pa, mode);
    }
    g_state.nvme.ep_count[14]++;
    nvme_diag_queue_summary(3, qid, cid, NVME_STATUS_VIOLATION);
    return nvme_violation(NVME_FN_MAP_PAGES, regs, 4);
}

static u64 nvme_ep2_violation(u64 *regs, u32 qid, u32 cid, u32 reason) {
    g_state.nvme.ep_count[15]++;
    nvme_diag_queue_summary(4, qid, cid, NVME_STATUS_VIOLATION);
    return nvme_violation(NVME_FN_UNMAP_PAGES, regs, reason);
}

static u64 nvme_ep2_unmap_pages(u64 *regs) {
    u32 qid = (u32)regs[0];
    u32 cid = (u32)regs[1];
    u32 retry = (u32)regs[2] & 1U;
    u8 cur;
    u8 expected;
    u32 count;
    u16 dir_bits;

    if (!(g_state.nvme.allowed_functions & NVME_AF_TCB_INVALIDATE))
        return nvme_ep2_violation(regs, qid, cid, 1);
    if (qid > 1 || cid >= g_state.nvme.queue_count ||
        cid >= g_state.nvme.max_cid || cid >= NVME_C_MAX_CID)
        return nvme_ep2_violation(regs, qid, cid, 2);
    if (retry)
        g_state.nvme.ep_count[13]++;
    cur = g_state.nvme.cid_mode[cid];
    expected = (u8)((qid << 4) | (retry ? 0x4U : 0x3U));
    if (cur != expected)
        return nvme_ep2_violation(regs, qid, cid, 3);
    g_state.nvme.cid_mode[cid] = NVME_CID_BUSY;

    count = g_state.nvme.tcb_count[cid];
    dir_bits = g_state.nvme.tcb_dir[cid];

    if (!retry) {
        if (g_state.nvme.tcb_kva[qid] != 0) {
            u64 tcb_base = g_state.nvme.tcb_kva[qid] + (u64)cid * 0x80UL;
            *(volatile u16 *)tcb_base = 0;
        }
        if ((g_state.nvme.quirks & NVME_QUIRK_VDMA_WA) &&
            (!nvme_mmio_base_valid(g_state.nvme.vdma_status_pa) ||
             (*(volatile u32 *)(g_state.nvme.vdma_status_pa +
                                (u64)cid * 0x20UL) & 0x300U) != 0))
            return nvme_ep2_violation(regs, qid, cid, 5);
        if (!nvme_mmio_base_valid(g_state.nvme.nvmmu_pa))
            return nvme_ep2_violation(regs, qid, cid, 6);
        barrier();
        nvme_nvmmu_write32(NVME_BAR_TCB_INVALIDATE, cid);
        u32 stat = nvme_mmio_read32(g_state.nvme.nvmmu_pa,
                                    ((cid >> 2) & 0x3fffU) * 4U);
        u32 shift = (cid & 3U) | ((cid & 3U) << 2);
        if (((stat >> shift) & 0xfU) != 0)
            return nvme_ep2_violation(regs, qid, cid, 7);
    }

    if (!nvme_tl_wa_wait(qid, cid, dir_bits, retry)) {
        g_state.nvme.ep_count[15]++;
        nvme_diag_queue_summary(5, qid, cid, 0);
        return 0;
    }

    nvme_diag_cmd_unmap(qid, cid, retry, count, dir_bits,
                        g_state.nvme.tcb_mode[cid],
                        g_state.nvme.tcb_prp1[cid],
                        g_state.nvme.tcb_prp2[cid]);
    nvme_diag_ep2_prp_readback(qid, cid, count, dir_bits,
                               g_state.nvme.tcb_mode[cid],
                               g_state.nvme.tcb_prp1[cid]);

    if (count >= 1)
        nvme_iommu_release_mode(g_state.nvme.tcb_prp1[cid],
                                g_state.nvme.tcb_mode[cid]);
    if (count == 2) {
        nvme_iommu_release_mode(g_state.nvme.tcb_prp2[cid],
                                g_state.nvme.tcb_mode[cid]);
    } else if (count > 2) {
        u64 prp_list = g_state.nvme.prp_list_kva ?
                       g_state.nvme.prp_list_kva + (u64)cid * 0x800UL :
                       g_state.nvme.tcb_prp2[cid];
        for (u32 i = 0; i < count - 1; i++) {
            u64 pa = *(volatile u64 *)(prp_list + (u64)i * 8UL);
            nvme_iommu_release_mode(pa, g_state.nvme.tcb_mode[cid]);
        }
        for (u32 i = 0; i < count - 1; i++)
            *(volatile u64 *)(prp_list + (u64)i * 8UL) = 0;
    }

    if (g_state.nvme.tcb_kva[qid] != 0) {
        u64 tcb_base = g_state.nvme.tcb_kva[qid] + (u64)cid * 0x80UL;
        for (u32 i = 0; i < 0x80; i++)
            *(volatile u8 *)(tcb_base + i) = 0;
    }
    if ((g_state.nvme.quirks & NVME_QUIRK_PRP_FLUSH_WA) && count > 0xffU) {
        u64 prp_list = g_state.nvme.tcb_prp2[cid];

        sysop("dsb sy");
        if (prp_list != 0)
            dc_civac_range((void *)(prp_list + 0x800UL), 0x800);
    }

    g_state.nvme.tcb_count[cid] = 0;
    g_state.nvme.tcb_prp1[cid] = 0;
    g_state.nvme.tcb_prp2[cid] = 0;
    g_state.nvme.tcb_dir[cid] = 0;
    nvme_cid_clear(cid);
    barrier();
    if (qid < 2)
        g_state.nvme.ep_count[11 + qid]++;
    nvme_diag_queue_summary(2, qid, cid, 1);
    /* sptm_nvme_unmap_pages is the odd table-6 endpoint whose RE'd return is
     * boolean-like: 1 means success, 0 is the retry-path failure value. Keep
     * this as 1 even though most SPTM endpoints use SPTM_SUCCESS == 0. */
    return 1;
}

bool_t nvme_handle_table6(u32 endpoint, u64 *regs) {
    u64 rc = NVME_STATUS_VIOLATION;
    u64 orig0 = regs[0];
    u64 orig1 = regs[1];
    u64 orig2 = regs[2];
    u64 orig3 = regs[3];

    if (!g_state.nvme.enabled)
        return 0;

    g_state.nvme.total_calls++;
    if (endpoint < 16)
        g_state.nvme.ep_count[endpoint]++;

    switch (endpoint) {
        case NVME_FN_ENABLE_COASTGUARD:    rc = nvme_ep0_enable_coastguard(regs); break;
        case NVME_FN_MAP_PAGES:            rc = nvme_ep1_map_pages(regs); break;
        case NVME_FN_UNMAP_PAGES:          rc = nvme_ep2_unmap_pages(regs); break;
        case NVME_FN_VALIDATE_QENTRIES:    rc = nvme_ep3_validate(regs); break;
        case NVME_FN_BAR_ADMIN_QUEUE_REGS: rc = nvme_ep4_admin_queue(regs); break;
        case NVME_FN_BAR_IOQA_REG:         rc = nvme_ep5_ioqa(regs); break;
        case NVME_FN_BAR_IOSQ_REG:         rc = nvme_ep6_iosq(regs); break;
        case NVME_FN_BAR_IOCQ_REG:         rc = nvme_ep7_iocq(regs); break;
        case NVME_FN_ANS_SHA_REG:          rc = nvme_ep8_ans_sha(regs); break;
        default:
            rc = nvme_violation(endpoint, regs, 0xff);
            break;
    }

    nvme_record_last(endpoint, rc, regs);
    if (endpoint == NVME_FN_BAR_IOQA_REG && rc == SPTM_SUCCESS)
        nvme_diag_ep5_readback_once();
    if (g_state.nvme.debug_flags & NVME_DBG_PRINT_MINIMAL) {
        if (endpoint == NVME_FN_ENABLE_COASTGUARD ||
            endpoint == NVME_FN_MAP_PAGES ||
            endpoint == NVME_FN_UNMAP_PAGES ||
            endpoint == NVME_FN_VALIDATE_QENTRIES ||
            endpoint == NVME_FN_BAR_ADMIN_QUEUE_REGS ||
            endpoint == NVME_FN_BAR_IOQA_REG ||
            endpoint == NVME_FN_BAR_IOSQ_REG ||
            endpoint == NVME_FN_BAR_IOCQ_REG) {
            debug_printf("C-NVME min ep=%u rc=0x%lx allowed=0x%x args=%lx,%lx,%lx,%lx\n",
                         endpoint, rc, g_state.nvme.allowed_functions,
                         orig0, orig1, orig2, orig3);
        }
    }
    if ((g_state.nvme.debug_flags & NVME_DBG_PRINT_CALLS) &&
        (g_state.nvme.total_calls <= 128 ||
        endpoint == NVME_FN_BAR_IOSQ_REG ||
        endpoint == NVME_FN_BAR_IOCQ_REG ||
        (rc != SPTM_SUCCESS &&
         !(endpoint == NVME_FN_UNMAP_PAGES && rc == 1)))) {
        u64 elr;
        __asm__ volatile("mrs %0, elr_el2" : "=r"(elr));
        debug_printf("C-NVME ep=%u rc=0x%lx allowed=0x%x pc=0x%lx lr=0x%lx args=%lx,%lx,%lx,%lx",
                     endpoint, rc, g_state.nvme.allowed_functions,
                     elr, regs[30], orig0, orig1, orig2, orig3);
        nvme_print_backtrace(regs[29]);
        debug_printf("\n");
    }
    regs[0] = rc;
    g_state.nvme.fast_path_calls++;
    g_state.fast_path_calls++;
    sev();
    return 1;
}

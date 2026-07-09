/* SPDX-License-Identifier: MIT */
#include "private.h"

#define TXM_SYNTH_RESERVED_TOP          0x200UL

static inline bool_t txm_synth_pa_for_va(u64 va, u64 *pa_out) {
    if (g_state.txm.synth_base_va == 0 || g_state.txm.synth_base_pa == 0)
        return 0;
    if (va < g_state.txm.synth_base_va)
        return 0;
    u64 off = va - g_state.txm.synth_base_va;
    if (off >= g_state.txm.synth_size)
        return 0;
    *pa_out = g_state.txm.synth_base_pa + off;
    return 1;
}

static inline void txm_synth_write8(u64 va, u8 value) {
    u64 pa;
    if (!txm_synth_pa_for_va(va, &pa))
        return;
    *(volatile u8 *)pa = value;
    clean_range((void *)(pa & ~63UL), 64);
}

static inline void txm_synth_write16(u64 va, u16 value) {
    u64 pa;
    if (!txm_synth_pa_for_va(va, &pa))
        return;
    *(volatile u16 *)pa = value;
    clean_range((void *)(pa & ~63UL), 64);
}

static inline void txm_synth_write32(u64 va, u32 value) {
    u64 pa;
    if (!txm_synth_pa_for_va(va, &pa))
        return;
    *(volatile u32 *)pa = value;
    clean_range((void *)(pa & ~63UL), 64);
}

static inline void txm_synth_write64(u64 va, u64 value) {
    u64 pa;
    if (!txm_synth_pa_for_va(va, &pa))
        return;
    *(volatile u64 *)pa = value;
    clean_range((void *)(pa & ~63UL), 64);
}

static inline u64 txm_alloc_synth(u64 size, u64 fallback_va) {
    if (g_state.txm.synth_base_va == 0 || g_state.txm.synth_size == 0)
        return fallback_va;

    size = (size + (TXM_C_SYNTH_ALIGN - 1)) & ~(TXM_C_SYNTH_ALIGN - 1);
    u64 off = (g_state.txm.synth_next_off + (TXM_C_SYNTH_ALIGN - 1)) &
              ~(TXM_C_SYNTH_ALIGN - 1);
    u64 limit = g_state.txm.synth_size;
    if (limit > TXM_SYNTH_RESERVED_TOP)
        limit -= TXM_SYNTH_RESERVED_TOP;
    if (off + size > limit)
        return fallback_va ? fallback_va : g_state.txm.synth_base_va;

    g_state.txm.synth_next_off = off + size;
    return g_state.txm.synth_base_va + off;
}

/* Offsets verified against KDK 26.5_25F71 private TXM/libCodeSignature headers. */
#define TXM_SYNTH_TRUST_CACHE_OFF       0x200UL
#define TXM_SYNTH_TRUST_CACHE_SIZE      0x200UL
#define TXM_SYNTH_TC_OBJECT_OFF         0x000UL
#define TXM_SYNTH_TC_MODULE_OFF         0x080UL
#define TXM_SYNTH_TC_ENTRY_OFF          0x098UL
#define TXM_TRUSTCACHE_TYPE_OFF         0x008UL
#define TXM_TRUSTCACHE_MODULE_SIZE_OFF  0x010UL
#define TXM_TRUSTCACHE_MODULE_OFF       0x018UL
#define TXM_MODULE1_NUM_ENTRIES_OFF     0x014UL
#define TXM_MODULE1_ENTRIES_OFF         0x018UL
#define TXM_ENTRY1_HASH_TYPE_OFF        0x014UL
#define TXM_ENTRY1_FLAGS_OFF            0x015UL
#define TXM_CODE_SIGNATURE_SIZE         0x180UL
#define TXM_CODE_SIGNATURE_TRUST_OFF    0x132UL
#define TXM_ASPACE_MAIN_REGION_OFF      0x040UL
#define TXM_ASPACE_SYNTH_REGION_SIZE    0x080UL
#define TXM_CS_TRUST_STATIC_TC          9U
#define TXM_TC_TYPE_STATIC              0U
#define TXM_TC_TYPE_LTRS                4U
#define TXM_TC_QUERY_LOADABLE           2U
#define TXM_TC_HASH_SHA256_TRUNCATED    3U
#define TXM_TC_CAP_HASH_TYPE            (1UL << 0)
#define TXM_TC_CAP_FLAGS                (1UL << 1)

static bool_t txm_fake_trust_cache_token(u64 query_type, u64 *tc_va, u64 *entry_va) {
    if (g_state.txm.synth_base_va == 0 ||
        g_state.txm.synth_size < TXM_SYNTH_TRUST_CACHE_SIZE)
        return 0;

    u64 base = g_state.txm.synth_base_va + g_state.txm.synth_size -
               TXM_SYNTH_TRUST_CACHE_OFF;
    u64 tc = base + TXM_SYNTH_TC_OBJECT_OFF;
    u64 module = base + TXM_SYNTH_TC_MODULE_OFF;
    u64 entry = base + TXM_SYNTH_TC_ENTRY_OFF;
    u8 tc_type = (query_type == TXM_TC_QUERY_LOADABLE) ? TXM_TC_TYPE_LTRS :
                                                      TXM_TC_TYPE_STATIC;

    /* TrustCache_t: next=0, type, tombstoned=0, moduleSize, module pointer. */
    txm_synth_write64(tc + 0x00, 0);
    txm_synth_write8(tc + TXM_TRUSTCACHE_TYPE_OFF, tc_type);
    txm_synth_write8(tc + TXM_TRUSTCACHE_TYPE_OFF + 1, 0);
    txm_synth_write64(tc + TXM_TRUSTCACHE_MODULE_SIZE_OFF, 0x18 + 0x16);
    txm_synth_write64(tc + TXM_TRUSTCACHE_MODULE_OFF, module);

    /* TrustCacheModule1_t with one synthetic entry. */
    txm_synth_write32(module + 0x00, 1);
    txm_synth_write32(module + TXM_MODULE1_NUM_ENTRIES_OFF, 1);
    txm_synth_write8(entry + TXM_ENTRY1_HASH_TYPE_OFF,
                     TXM_TC_HASH_SHA256_TRUNCATED);
    txm_synth_write8(entry + TXM_ENTRY1_FLAGS_OFF, 0);

    *tc_va = tc;
    *entry_va = entry;
    return 1;
}

static inline void txm_record_call(u32 selector, u64 x16, u64 *regs) {
    g_state.txm.total_calls++;
    g_state.total_calls++;
    g_state.last_x16 = x16;
    g_state.last_endpoint = selector;
    g_state.txm.last_selector = selector;
    g_state.txm.last_stack_pa = regs[0];
    g_state.txm.last_x16 = x16;
    for (u32 i = 0; i < 8; i++)
        g_state.txm.last_args[i] = regs[i];
    if (selector < TXM_C_MAX_ENDPOINTS)
        g_state.txm.ep_count[selector]++;
}

static bool_t txm_write_stack_return(u64 stack_pa, u64 rc,
                                     const u64 *words, u64 nwords) {
    if (stack_pa == 0 || nwords > TXM_STACK_RETURN_WORDS)
        return 0;

    u64 shared = stack_pa + TXM_THREAD_STACK_SHARED_OFF;
    *(volatile u64 *)(shared + TXM_SHARED_RETURN_CODE_OFF) = rc;
    *(volatile u8  *)(shared + TXM_SHARED_RETURN_TYPE_OFF) = 0; /* words */
    *(volatile u64 *)(shared + TXM_SHARED_NUM_WORDS_OFF) = nwords;
    for (u64 i = 0; i < TXM_STACK_RETURN_WORDS; i++) {
        u64 value = (i < nwords) ? words[i] : 0;
        *(volatile u64 *)(shared + TXM_SHARED_WORDS_OFF + i * 8UL) = value;
        g_state.txm.last_words[i] = value;
    }

    g_state.txm.last_rc = rc;
    clean_range((void *)shared, 0x80);
    barrier();
    return 1;
}

static bool_t txm_finish(u32 selector, u64 *regs, u64 rc,
                         const u64 *words, u64 nwords) {
    if (!txm_write_stack_return(regs[0], rc, words, nwords)) {
        g_state.txm.violations++;
        return 0;
    }
    regs[0] = rc;
    g_state.txm.fast_path_calls++;
    g_state.fast_path_calls++;
    sev();
    (void)selector;
    return 1;
}

static bool_t txm_success0(u32 selector, u64 *regs) {
    u64 words[TXM_STACK_RETURN_WORDS] = {0, 0, 0, 0, 0, 0};
    return txm_finish(selector, regs, TXM_SUCCESS, words, 0);
}

static bool_t txm_failure(u32 selector, u64 *regs, u64 rc) {
    u64 words[TXM_STACK_RETURN_WORDS] = {0, 0, 0, 0, 0, 0};
    return txm_finish(selector, regs, rc, words, 0);
}

bool_t txm_handle_selector(u32 selector, u64 x16, u64 *regs) {
    u64 words[TXM_STACK_RETURN_WORDS] = {0, 0, 0, 0, 0, 0};

    if (!g_state.txm.enabled)
        return 0;

    txm_record_call(selector, x16, regs);

    switch (selector) {
        case 0:
            /* Selector 0 belongs to the SPTM-facing TXM table, not XNU table 0. */
            return txm_failure(selector, regs, TXM_RETURN_GENERIC);

        case TXM_SEL_GET_LOG_INFO:
            words[0] = g_state.txm.log_page_va;
            words[1] = g_state.txm.log_head_va;
            words[2] = g_state.txm.log_sync_va;
            return txm_finish(selector, regs, TXM_SUCCESS, words, 3);

        case TXM_SEL_GET_CODE_SIGNING_INFO:
            words[0] = g_state.txm.txm_rw_data_va + 0x690UL;
            words[1] = g_state.txm.developer_mode_flag_va;
            words[2] = g_state.txm.txm_rw_data_va + 0x918UL;
            words[3] = g_state.txm.managed_signature_size;
            words[4] = g_state.txm.txm_ro_data_va + 0x190UL;
            words[5] = g_state.txm.txm_ro_data_va;
            return txm_finish(selector, regs, TXM_SUCCESS, words, 6);

        case TXM_SEL_GET_TRUST_CACHE_INFO:
            words[0] = g_state.txm.trust_cache_runtime_va;
            words[1] = g_state.txm.trust_cache_static_count;
            words[2] = g_state.txm.trust_cache_caps0;
            words[3] = g_state.txm.trust_cache_caps1;
            return txm_finish(selector, regs, TXM_SUCCESS, words, 4);

        case 4: /* GetBuildVariant */
            words[0] = 0; /* release */
            return txm_finish(selector, regs, TXM_SUCCESS, words, 1);

        case 5:  /* EnterLockdownMode */
        case 6:  /* EnableRestrictedMode */
        case 8:  /* UpdateDeviceState */
        case 9:  /* CompleteSecurityBootMode */
            return txm_success0(selector, regs);

        case TXM_SEL_GET_SECURE_CHANNEL:
            words[0] = g_state.txm.secure_chan_pa;
            words[1] = g_state.txm.secure_chan_size;
            return txm_finish(selector, regs, TXM_SUCCESS, words, 2);

        case TXM_SEL_ADD_FREE_LIST_PAGE:
            if (regs[1] == 0)
                return txm_failure(selector, regs, TXM_RETURN_GENERIC);
            if (g_state.txm.free_count < TXM_C_TRACK_SLOTS)
                g_state.txm.free_pages[g_state.txm.free_count++] = regs[1];
            return txm_success0(selector, regs);

        case TXM_SEL_GET_FREE_LIST_PAGE:
            if (g_state.txm.free_count == 0)
                return txm_failure(selector, regs, TXM_RETURN_NOT_FOUND);
            words[0] = g_state.txm.free_pages[--g_state.txm.free_count];
            return txm_finish(selector, regs, TXM_SUCCESS, words, 1);

        case TXM_SEL_LOAD_TRUST_CACHE:
            if (g_state.txm.loaded_tc_count < TXM_C_TRACK_SLOTS)
                g_state.txm.loaded_tc[g_state.txm.loaded_tc_count++] = regs[1];
            /* Return payload VA so xnu can reclaim its temporary copy. */
            words[0] = regs[1];
            return txm_finish(selector, regs, TXM_SUCCESS, words, 1);

        case 13: /* UnloadTrustCache */
            return txm_success0(selector, regs);

        case TXM_SEL_QUERY_TRUST_CACHE:
            if (!txm_fake_trust_cache_token(regs[1], &words[0], &words[1]))
                return txm_failure(selector, regs, TXM_RETURN_NOT_FOUND);
            return txm_finish(selector, regs, TXM_SUCCESS, words, 2);

        case TXM_SEL_QUERY_TC_REM:
            words[0] = 0;
            return txm_finish(selector, regs, TXM_SUCCESS, words, 1);

        case TXM_SEL_CHECK_TC_UUID:
            return txm_failure(selector, regs, TXM_RETURN_NOT_FOUND);

        case TXM_SEL_REGISTER_PROFILE:
            words[0] = txm_alloc_synth(0x100, g_state.txm.default_profile_va);
            return txm_finish(selector, regs, TXM_SUCCESS, words, 1);

        case 18: /* TrustProvisioningProfile */
        case 20: /* AssociateProvisioningProfile */
        case 21: /* DisassociateProvisioningProfile */
            return txm_success0(selector, regs);

        case TXM_SEL_UNREGISTER_PROFILE:
            words[0] = 0;
            words[1] = 0;
            return txm_finish(selector, regs, TXM_SUCCESS, words, 2);

        case TXM_SEL_REGISTER_SIGNATURE: {
            u64 obj = txm_alloc_synth(TXM_CODE_SIGNATURE_SIZE,
                                      g_state.txm.default_signature_va);
            txm_synth_write8(obj + TXM_CODE_SIGNATURE_TRUST_OFF,
                             TXM_CS_TRUST_STATIC_TC);
            words[0] = obj;
            words[1] = regs[1];
            return txm_finish(selector, regs, TXM_SUCCESS, words, 2);
        }

        case TXM_SEL_UNREGISTER_SIGNATURE:
        case TXM_SEL_RECONSTITUTE_SIG:
            words[0] = 0;
            words[1] = 0;
            return txm_finish(selector, regs, TXM_SUCCESS, words, 2);

        case 26: /* SetLocalSigningPublicKey */
        case 28: /* AuthorizeLocalSigningCDHash */
        case 29: /* AuthorizeCompilationServiceCDHash */
        case 31: /* DeveloperModeToggle */
        case 33: /* AssociateKernelEntitlements */
        case 36: /* UnregisterAddressSpace */
        case 37: /* SetupNestedAddressSpace */
        case 39: /* AllowJITRegion */
        case 40: /* AssociateJITRegion */
        case 42: /* AssociateDebugRegion */
            return txm_success0(selector, regs);

        case 24: /* ValidateCodeSignature */
            txm_synth_write8(regs[1] + TXM_CODE_SIGNATURE_TRUST_OFF,
                             TXM_CS_TRUST_STATIC_TC);
            return txm_success0(selector, regs);

        case 38: { /* AssociateCodeSignature */
            u64 region = txm_alloc_synth(TXM_ASPACE_SYNTH_REGION_SIZE, regs[2]);
            txm_synth_write64(regs[1] + TXM_ASPACE_MAIN_REGION_OFF, region);
            return txm_success0(selector, regs);
        }

        case TXM_SEL_GET_LOCAL_PUBKEY:
            words[0] = g_state.txm.local_signing_pubkey_va;
            return txm_finish(selector, regs, TXM_SUCCESS, words, 1);

        case TXM_SEL_MATCH_COMPILATION:
            return txm_failure(selector, regs, TXM_RETURN_NOT_FOUND);

        case TXM_SEL_ACQUIRE_SIGNING_ID:
            words[0] = g_state.txm.signing_id_va;
            return txm_finish(selector, regs, TXM_SUCCESS, words, 1);

        case TXM_SEL_ACCEL_ENTITLEMENTS:
            /* Route entitlement evaluation to XNU's non-monitor path. Returning
             * NOT_SUPPORTED (what csm_enabled()==false yields) makes
             * accelerate_entitlement_queries() (ubc_subr.c:4441) take the
             * adjustContextWithoutMonitor branch, which parses the on-disk
             * csb_entitlements_blob directly. Previously we returned a NULL
             * monitor ce_ctx, which made every per-binary entitlement query
             * (incl. com.apple.security.get-movable-control-port) read as absent,
             * forcing IMMOVABLE_HARD control ports system-wide and breaking the
             * mode-3 cross-task task-port send. See docs/mode3_txm_stub_audit.md. */
            return txm_failure(selector, regs, TXM_RETURN_NOT_SUPPORTED);

        case TXM_SEL_GET_ENTITLEMENTS_CTX:
            words[0] = g_state.txm.ce_ctx_va;
            return txm_finish(selector, regs, TXM_SUCCESS, words, 1);

        case TXM_SEL_REGISTER_ASPACE: {
            u64 obj = txm_alloc_synth(0x100, g_state.txm.default_address_space_va);
            /* Offsets verified from KDK 26.5 TXMAddressSpace_t. */
            txm_synth_write64(obj + 0x18, regs[2]);       /* addrSpaceFlags */
            txm_synth_write16(obj + 0x24, (u16)regs[1]);  /* identifier */
            txm_synth_write16(obj + 0x26, 0);             /* type=AddressSpace */
            words[0] = obj;
            return txm_finish(selector, regs, TXM_SUCCESS, words, 1);
        }

        case 41: /* AllowInvalidCode */
            txm_synth_write8(regs[1] + 0x30, 1); /* allowsInvalidCode */
            return txm_success0(selector, regs);

        case TXM_SEL_RESOLVE_KENT_ASPACE:
            return txm_failure(selector, regs, TXM_RETURN_NOT_FOUND);

        case TXM_SEL_IMAGE4_DISPATCH:
            return txm_success0(selector, regs);

        case TXM_SEL_IMAGE4_GET_EXPORTS:
        case 47: /* Image4SetReleaseType */
        case 48: /* Image4SetBootNonceShadow */
        case 49: /* Image4SetNonce */
        case 50: /* Image4RollNonce */
        case TXM_SEL_IMAGE4_GET_NONCE:
            /* The mixed Python/C reference matched the T8140 TXM binary here:
             * selectors 46..51 go through the default-fail trampoline and
             * return kTXMReturnNotPermitted, not success or synthetic pointers.
             */
            return txm_failure(selector, regs, TXM_RETURN_NOT_PERMITTED);

        default:
            return txm_failure(selector, regs, TXM_RETURN_NOT_SUPPORTED);
    }
}

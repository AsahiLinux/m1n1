/* SPDX-License-Identifier: MIT */

#include "proxy.h"
#include "exception.h"
#include "heapblock.h"
#include "kboot.h"
#include "malloc.h"
#include "memory.h"
#include "smp.h"
#include "types.h"
#include "uart.h"
#include "utils.h"
#include "xnuboot.h"

#include "minilzlib/minlzma.h"
#include "tinf/tinf.h"

int proxy_process(ProxyRequest *request, ProxyReply *reply)
{
    enum exc_guard_t guard_save = exc_guard;

    callfunc *f;

    reply->opcode = request->opcode;
    reply->status = S_OK;
    reply->retval = 0;
    switch (request->opcode) {
        case P_NOP:
            break;
        case P_EXIT:
            return 0;
        case P_CALL:
            f = (callfunc *)request->args[0];
            reply->retval =
                f(request->args[1], request->args[2], request->args[3], request->args[4]);
            break;
        case P_GET_BOOTARGS:
            reply->retval = boot_args_addr;
            break;
        case P_GET_BASE:
            reply->retval = (u64)_base;
            break;
        case P_SET_BAUD: {
            int cnt = request->args[1];
            printf("Changing baud rate to %d...\n", request->args[0]);
            uart_setbaud(request->args[0]);
            while (cnt--) {
                uart_putbyte(request->args[2]);
                uart_putbyte(request->args[2] >> 8);
                uart_putbyte(request->args[2] >> 16);
                uart_putbyte(request->args[2] >> 24);
            }
            break;
        }
        case P_UDELAY:
            udelay(request->args[0]);
            break;
        case P_SET_EXC_GUARD:
            exc_count = 0;
            guard_save = request->args[0];
            break;
        case P_GET_EXC_COUNT:
            reply->retval = exc_count;
            exc_count = 0;
            break;

        case P_WRITE64:
            exc_guard = GUARD_SKIP;
            write64(request->args[0], request->args[1]);
            break;
        case P_WRITE32:
            exc_guard = GUARD_SKIP;
            write32(request->args[0], request->args[1]);
            break;
        case P_WRITE16:
            exc_guard = GUARD_SKIP;
            write16(request->args[0], request->args[1]);
            break;
        case P_WRITE8:
            exc_guard = GUARD_SKIP;
            write8(request->args[0], request->args[1]);
            break;

        case P_READ64:
            exc_guard = GUARD_MARK;
            reply->retval = read64(request->args[0]);
            break;
        case P_READ32:
            exc_guard = GUARD_MARK;
            reply->retval = read32(request->args[0]);
            break;
        case P_READ16:
            exc_guard = GUARD_MARK;
            reply->retval = read16(request->args[0]);
            break;
        case P_READ8:
            exc_guard = GUARD_MARK;
            reply->retval = read8(request->args[0]);
            break;

        case P_SET64:
            exc_guard = GUARD_MARK;
            reply->retval = set64(request->args[0], request->args[1]);
            break;
        case P_SET32:
            exc_guard = GUARD_MARK;
            reply->retval = set32(request->args[0], request->args[1]);
            break;
        case P_SET16:
            exc_guard = GUARD_MARK;
            reply->retval = set16(request->args[0], request->args[1]);
            break;
        case P_SET8:
            exc_guard = GUARD_MARK;
            reply->retval = set8(request->args[0], request->args[1]);
            break;

        case P_CLEAR64:
            exc_guard = GUARD_MARK;
            reply->retval = clear64(request->args[0], request->args[1]);
            break;
        case P_CLEAR32:
            exc_guard = GUARD_MARK;
            reply->retval = clear32(request->args[0], request->args[1]);
            break;
        case P_CLEAR16:
            exc_guard = GUARD_MARK;
            reply->retval = clear16(request->args[0], request->args[1]);
            break;
        case P_CLEAR8:
            exc_guard = GUARD_MARK;
            reply->retval = clear8(request->args[0], request->args[1]);
            break;

        case P_MASK64:
            exc_guard = GUARD_MARK;
            reply->retval = mask64(request->args[0], request->args[1], request->args[2]);
            break;
        case P_MASK32:
            exc_guard = GUARD_MARK;
            reply->retval = mask32(request->args[0], request->args[1], request->args[2]);
            break;
        case P_MASK16:
            exc_guard = GUARD_MARK;
            reply->retval = mask16(request->args[0], request->args[1], request->args[2]);
            break;
        case P_MASK8:
            exc_guard = GUARD_MARK;
            reply->retval = mask8(request->args[0], request->args[1], request->args[2]);
            break;

        case P_MEMCPY64:
            exc_guard = GUARD_RETURN;
            memcpy64((void *)request->args[0], (void *)request->args[1], request->args[2]);
            break;
        case P_MEMCPY32:
            exc_guard = GUARD_RETURN;
            memcpy32((void *)request->args[0], (void *)request->args[1], request->args[2]);
            break;
        case P_MEMCPY16:
            exc_guard = GUARD_RETURN;
            memcpy16((void *)request->args[0], (void *)request->args[1], request->args[2]);
            break;
        case P_MEMCPY8:
            exc_guard = GUARD_RETURN;
            memcpy8((void *)request->args[0], (void *)request->args[1], request->args[2]);
            break;

        case P_MEMSET64:
            exc_guard = GUARD_RETURN;
            memset64((void *)request->args[0], request->args[1], request->args[2]);
            break;
        case P_MEMSET32:
            exc_guard = GUARD_RETURN;
            memset32((void *)request->args[0], request->args[1], request->args[2]);
            break;
        case P_MEMSET16:
            exc_guard = GUARD_RETURN;
            memset16((void *)request->args[0], request->args[1], request->args[2]);
            break;
        case P_MEMSET8:
            exc_guard = GUARD_RETURN;
            memset8((void *)request->args[0], request->args[1], request->args[2]);
            break;

        case P_IC_IALLUIS:
            ic_ialluis();
            break;
        case P_IC_IALLU:
            ic_iallu();
            break;
        case P_IC_IVAU:
            ic_ivau_range((void *)request->args[0], request->args[1]);
            break;
        case P_DC_IVAC:
            dc_ivac_range((void *)request->args[0], request->args[1]);
            break;
        case P_DC_ISW:
            dc_isw((void *)request->args[0]);
            break;
        case P_DC_CSW:
            dc_csw((void *)request->args[0]);
            break;
        case P_DC_CISW:
            dc_cisw((void *)request->args[0]);
            break;
        case P_DC_ZVA:
            dc_zva_range((void *)request->args[0], request->args[1]);
            break;
        case P_DC_CVAC:
            dc_cvac_range((void *)request->args[0], request->args[1]);
            break;
        case P_DC_CVAU:
            dc_cvau_range((void *)request->args[0], request->args[1]);
            break;
        case P_DC_CIVAC:
            dc_civac_range((void *)request->args[0], request->args[1]);
            break;
        case P_MMU_SHUTDOWN:
            mmu_shutdown();
            break;

        case P_XZDEC: {
            uint32_t destlen, srclen;
            destlen = request->args[3];
            srclen = request->args[1];
            if (XzDecode((void *)request->args[0], &srclen, (void *)request->args[2], &destlen))
                reply->retval = destlen;
            else
                reply->retval = ~0L;
            break;
        }
        case P_GZDEC: {
            unsigned int destlen, srclen;
            destlen = request->args[3];
            srclen = request->args[1];
            size_t ret = tinf_gzip_uncompress((void *)request->args[2], &destlen,
                                              (void *)request->args[0], &srclen);
            if (ret != TINF_OK)
                reply->retval = ret;
            else
                reply->retval = destlen;
            break;
        }

        case P_SMP_START_SECONDARIES:
            smp_start_secondaries();
            break;
        case P_SMP_CALL:
            smp_call4(request->args[0], (void *)request->args[1], request->args[2],
                      request->args[3], request->args[4], request->args[5]);
            break;
        case P_SMP_CALL_SYNC:
            smp_call4(request->args[0], (void *)request->args[1], request->args[2],
                      request->args[3], request->args[4], request->args[5]);
            reply->retval = smp_wait(request->args[0]);
            break;

        case P_HEAPBLOCK_ALLOC:
            reply->retval = (u64)heapblock_alloc(request->args[0]);
            break;
        case P_MALLOC:
            reply->retval = (u64)malloc(request->args[0]);
            break;
        case P_MEMALIGN:
            reply->retval = (u64)memalign(request->args[0], request->args[1]);
            break;
        case P_FREE:
            free((void *)request->args[0]);
            break;

        case P_KBOOT_BOOT:
            kboot_boot((void *)request->args[0]);
            break;
        case P_KBOOT_SET_BOOTARGS:
            kboot_set_bootargs((void *)request->args[0]);
            break;
        case P_KBOOT_SET_INITRD:
            kboot_set_initrd((void *)request->args[0], request->args[1]);
            break;
        case P_KBOOT_PREPARE_DT:
            reply->retval = kboot_prepare_dt((void *)request->args[0]);
            break;

        default:
            reply->status = S_BADCMD;
            break;
    }
    exc_guard = guard_save;
    return 1;
}

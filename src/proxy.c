#include "proxy.h"
#include "memory.h"
#include "minilzlib/minlzma.h"
#include "tinf/tinf.h"
#include "types.h"
#include "uart.h"
#include "utils.h"
#include "xnuboot.h"

int proxy_process(ProxyRequest *request, ProxyReply *reply)
{
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
            reply->retval = f(request->args[1], request->args[2],
                              request->args[3], request->args[4]);
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

        case P_WRITE64:
            write64(request->args[0], request->args[1]);
            break;
        case P_WRITE32:
            write32(request->args[0], request->args[1]);
            break;
        case P_WRITE16:
            write16(request->args[0], request->args[1]);
            break;
        case P_WRITE8:
            write8(request->args[0], request->args[1]);
            break;

        case P_READ64:
            reply->retval = read64(request->args[0]);
            break;
        case P_READ32:
            reply->retval = read32(request->args[0]);
            break;
        case P_READ16:
            reply->retval = read16(request->args[0]);
            break;
        case P_READ8:
            reply->retval = read8(request->args[0]);
            break;

        case P_SET64:
            reply->retval = set64(request->args[0], request->args[1]);
            break;
        case P_SET32:
            reply->retval = set32(request->args[0], request->args[1]);
            break;
        case P_SET16:
            reply->retval = set16(request->args[0], request->args[1]);
            break;
        case P_SET8:
            reply->retval = set8(request->args[0], request->args[1]);
            break;

        case P_CLEAR64:
            reply->retval = clear64(request->args[0], request->args[1]);
            break;
        case P_CLEAR32:
            reply->retval = clear32(request->args[0], request->args[1]);
            break;
        case P_CLEAR16:
            reply->retval = clear16(request->args[0], request->args[1]);
            break;
        case P_CLEAR8:
            reply->retval = clear8(request->args[0], request->args[1]);
            break;

        case P_MASK64:
            reply->retval =
                mask64(request->args[0], request->args[1], request->args[2]);
            break;
        case P_MASK32:
            reply->retval =
                mask32(request->args[0], request->args[1], request->args[2]);
            break;
        case P_MASK16:
            reply->retval =
                mask16(request->args[0], request->args[1], request->args[2]);
            break;
        case P_MASK8:
            reply->retval =
                mask8(request->args[0], request->args[1], request->args[2]);
            break;

        case P_MEMCPY64:
            memcpy64((void *)request->args[0], (void *)request->args[1],
                     request->args[2]);
            break;
        case P_MEMCPY32:
            memcpy32((void *)request->args[0], (void *)request->args[1],
                     request->args[2]);
            break;
        case P_MEMCPY16:
            memcpy16((void *)request->args[0], (void *)request->args[1],
                     request->args[2]);
            break;
        case P_MEMCPY8:
            memcpy8((void *)request->args[0], (void *)request->args[1],
                    request->args[2]);
            break;

        case P_MEMSET64:
            memset64((void *)request->args[0], request->args[1],
                     request->args[2]);
            break;
        case P_MEMSET32:
            memset32((void *)request->args[0], request->args[1],
                     request->args[2]);
            break;
        case P_MEMSET16:
            memset16((void *)request->args[0], request->args[1],
                     request->args[2]);
            break;
        case P_MEMSET8:
            memset8((void *)request->args[0], request->args[1],
                    request->args[2]);
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

        case P_XZDEC: {
            u32 output_size = request->args[3];
            if (XzDecode((void *)request->args[0], request->args[1],
                        (void *)request->args[2], &output_size))
                reply->retval = output_size;
            else
                reply->retval = ~0L;
            break;
        }
        case P_GZDEC: {
            unsigned int destlen, srclen;
            destlen = request->args[3];
            srclen = request->args[1];
            size_t ret = tinf_gzip_uncompress((void *)request->args[2], &destlen,
                        (void *)request->args[0], srclen);
            if (ret != TINF_OK)
                reply->retval = ret;
            else
                reply->retval = destlen;
            break;
        }

        default:
            reply->status = S_BADCMD;
            break;
    }
    return 1;
}

#include "proxy.h"
#include "types.h"
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

            /*
                    case P_DC_FLUSHRANGE: dc_flushrange((void*)request->args[0],
               request->args[1]); break; case P_DC_INVALRANGE:
               dc_invalidaterange((void*)request->args[0], request->args[1]);
               break; case P_DC_FLUSHALL: dc_flushall(); break; case
               P_IC_INVALALL: ic_invalidateall(); break;
            */

        default:
            reply->status = S_BADCMD;
            break;
    }
    return 1;
}

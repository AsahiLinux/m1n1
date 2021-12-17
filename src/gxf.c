/* SPDX-License-Identifier: MIT */

#include "cpu_regs.h"
#include "exception.h"
#include "gxf.h"
#include "malloc.h"
#include "memory.h"
#include "smp.h"
#include "uart.h"
#include "utils.h"

uint64_t gxf_enter(void *func, uint64_t a, uint64_t b, uint64_t c, uint64_t d);

void _gxf_init(void *gl2_stack, void *gl1_stack);

u8 *gl1_stack[MAX_CPUS];
u8 *gl2_stack[MAX_CPUS];

void gxf_init(void)
{
    int cpu = smp_id();

    if (!gl2_stack[cpu])
        gl2_stack[cpu] = memalign(0x4000, GL_STACK_SIZE);
    if (in_el2() && !gl1_stack[cpu])
        gl1_stack[cpu] = memalign(0x4000, GL_STACK_SIZE);

    _gxf_init(gl2_stack[cpu], gl1_stack[cpu]);
}

bool gxf_enabled(void)
{
    if (!(mrs(SYS_IMP_APL_SPRR_CONFIG_EL1) & SPRR_CONFIG_EN))
        return false;

    return (mrs(SYS_IMP_APL_GXF_CONFIG_EL1) & GXF_CONFIG_EN);
}

bool in_gl12(void)
{
    if (!gxf_enabled())
        return false;

    return (mrs(SYS_IMP_APL_GXF_STATUS_EL1) & GXF_STATUS_GUARDED);
}

static uint64_t gl_call(void *func, uint64_t a, uint64_t b, uint64_t c, uint64_t d)
{
    // disable the MMU first since enabling SPRR will change the meaning of all
    // pagetable permission bits and also prevent us from having rwx pages
    u64 sprr_state = mrs(SYS_IMP_APL_SPRR_CONFIG_EL1);
    if (!(sprr_state & SPRR_CONFIG_EN))
        reg_set_sync(SYS_IMP_APL_SPRR_CONFIG_EL1, sprr_state | SPRR_CONFIG_EN);

    u64 gxf_state = mrs(SYS_IMP_APL_GXF_CONFIG_EL1);
    if (!(gxf_state & GXF_CONFIG_EN))
        reg_set_sync(SYS_IMP_APL_GXF_CONFIG_EL1, gxf_state | GXF_CONFIG_EN);

    uint64_t ret = gxf_enter(func, a, b, c, d);

    if (!(gxf_state & GXF_CONFIG_EN))
        msr_sync(SYS_IMP_APL_GXF_CONFIG_EL1, gxf_state);
    if (!(sprr_state & SPRR_CONFIG_EN))
        msr_sync(SYS_IMP_APL_SPRR_CONFIG_EL1, sprr_state);

    return ret;
}

uint64_t gl2_call(void *func, uint64_t a, uint64_t b, uint64_t c, uint64_t d)
{
    if (mrs(CurrentEL) != 0x8)
        return -1;
    return gl_call(func, a, b, c, d);
}

struct gl_call_argv {
    void *func;
    uint64_t a, b, c, d;
};

static uint64_t gl_call_wrapper(struct gl_call_argv *args)
{
    return gl_call(args->func, args->a, args->b, args->c, args->d);
}

uint64_t gl1_call(void *func, uint64_t a, uint64_t b, uint64_t c, uint64_t d)
{
    if (mrs(CurrentEL) == 0x4)
        return gl_call(func, a, b, c, d);

    struct gl_call_argv args;
    args.func = func;
    args.a = a;
    args.b = b;
    args.c = c;
    args.d = d;

    // enable EL1 here since once GXF has been enabled HCR_EL2 writes are only possible from GL2
    if (mrs(HCR_EL2) & HCR_TGE)
        reg_clr(HCR_EL2, HCR_TGE);

    u64 sprr_state = mrs(SYS_IMP_APL_SPRR_CONFIG_EL1) & SPRR_CONFIG_EN;
    reg_set_sync(SYS_IMP_APL_SPRR_CONFIG_EL1, SPRR_CONFIG_EN);

    u64 gxf_state = mrs(SYS_IMP_APL_GXF_CONFIG_EL1) & GXF_CONFIG_EN;
    reg_set_sync(SYS_IMP_APL_GXF_CONFIG_EL1, GXF_CONFIG_EN);

    uint64_t ret = el1_call(gl_call_wrapper, (uint64_t)&args, 0, 0, 0);

    msr_sync(SYS_IMP_APL_GXF_CONFIG_EL1, gxf_state);
    msr_sync(SYS_IMP_APL_SPRR_CONFIG_EL1, sprr_state);

    return ret;
}

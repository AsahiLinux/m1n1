/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "assert.h"
#include "malloc.h"
#include "nvme.h"
#include "pmgr.h"
#include "rtkit.h"
#include "sart.h"
#include "string.h"
#include "utils.h"

#define NVME_TIMEOUT          1000000
#define NVME_ENABLE_TIMEOUT   5000000
#define NVME_SHUTDOWN_TIMEOUT 5000000
#define NVME_QUEUE_SIZE       64

#define NVME_CC            0x14
#define NVME_CC_SHN        GENMASK(15, 14)
#define NVME_CC_SHN_NONE   0
#define NVME_CC_SHN_NORMAL 1
#define NVME_CC_SHN_ABRUPT 2
#define NVME_CC_EN         BIT(0)

#define NVME_CSTS             0x1c
#define NVME_CSTS_SHST        GENMASK(3, 2)
#define NVME_CSTS_SHST_NORMAL 0
#define NVME_CSTS_SHST_BUSY   1
#define NVME_CSTS_SHST_DONE   2
#define NVME_CSTS_RDY         BIT(0)

#define NVME_AQA 0x24
#define NVME_ASQ 0x28
#define NVME_ACQ 0x30

#define NVME_DB_ACQ  0x1004
#define NVME_DB_IOCQ 0x100c

#define NVME_BOOT_STATUS    0x1300
#define NVME_BOOT_STATUS_OK 0xde71ce55

#define NVME_LINEAR_SQ_CTRL    0x24908
#define NVME_LINEAR_SQ_CTRL_EN BIT(0)

#define NVME_UNKNONW_CTRL                0x24008
#define NVME_UNKNONW_CTRL_PRP_NULL_CHECK BIT(11)

#define NVME_MAX_PEND_CMDS_CTRL 0x1210
#define NVME_DB_LINEAR_ASQ      0x2490c
#define NVME_DB_LINEAR_IOSQ     0x24910

#define NVMMU_NUM       0x28100
#define NVMMU_ASQ_BASE  0x28108
#define NVMMU_IOSQ_BASE 0x28110
#define NVMMU_TCB_INVAL 0x28118
#define NVMMU_TCB_STAT  0x29120

#define NVME_ADMIN_CMD_DELETE_SQ 0x00
#define NVME_ADMIN_CMD_CREATE_SQ 0x01
#define NVME_ADMIN_CMD_DELETE_CQ 0x04
#define NVME_ADMIN_CMD_CREATE_CQ 0x05
#define NVME_QUEUE_CONTIGUOUS    BIT(0)

#define NVME_CMD_FLUSH 0x00
#define NVME_CMD_WRITE 0x01
#define NVME_CMD_READ  0x02

struct nvme_command {
    u8 opcode;
    u8 flags;
    u8 tag;
    u8 rsvd; // normal NVMe has tag as u16
    u32 nsid;
    u32 cdw2;
    u32 cdw3;
    u64 metadata;
    u64 prp1;
    u64 prp2;
    u32 cdw10;
    u32 cdw11;
    u32 cdw12;
    u32 cdw13;
    u32 cdw14;
    u32 cdw15;
};

struct nvme_completion {
    u64 result;
    u32 rsvd; // normal NVMe has the sq_head and sq_id here
    u16 tag;
    u16 status;
};

struct apple_nvmmu_tcb {
    u8 opcode;
    u8 dma_flags;
    u8 slot_id;
    u8 unk0;
    u32 len;
    u64 unk1[2];
    u64 prp1;
    u64 prp2;
    u64 unk2[2];
    u8 aes_iv[8];
    u8 _aes_unk[64];
};

struct nvme_queue {
    struct apple_nvmmu_tcb *tcbs;
    struct nvme_command *cmds;
    struct nvme_completion *cqes;

    u8 cq_head;
    u8 cq_phase;

    bool adminq;
};

static_assert(sizeof(struct nvme_command) == 64, "invalid nvme_command size");
static_assert(sizeof(struct nvme_completion) == 16, "invalid nvme_completion size");
static_assert(sizeof(struct apple_nvmmu_tcb) == 128, "invalid apple_nvmmu_tcb size");

static bool nvme_initialized = false;
static u8 nvme_die;

static asc_dev_t *nvme_asc = NULL;
static rtkit_dev_t *nvme_rtkit = NULL;
static sart_dev_t *nvme_sart = NULL;

static u64 nvme_base;

static struct nvme_queue adminq, ioq;

static bool alloc_queue(struct nvme_queue *q)
{
    memset(q, 0, sizeof(*q));

    q->tcbs = memalign(SZ_16K, NVME_QUEUE_SIZE * sizeof(*q->tcbs));
    if (!q->tcbs)
        return false;

    q->cmds = memalign(SZ_16K, NVME_QUEUE_SIZE * sizeof(*q->cmds));
    if (!q->cmds)
        goto free_tcbs;

    q->cqes = memalign(SZ_16K, NVME_QUEUE_SIZE * sizeof(*q->cqes));
    if (!q->cqes)
        goto free_cmds;

    memset(q->tcbs, 0, NVME_QUEUE_SIZE * sizeof(*q->tcbs));
    memset(q->cmds, 0, NVME_QUEUE_SIZE * sizeof(*q->cmds));
    memset(q->cqes, 0, NVME_QUEUE_SIZE * sizeof(*q->cqes));
    q->cq_head = 0;
    q->cq_phase = 1;
    return true;

free_cmds:
    free(q->cmds);
free_tcbs:
    free(q->tcbs);
    return false;
}

static void free_queue(struct nvme_queue *q)
{
    free(q->cmds);
    free(q->tcbs);
    free(q->cqes);
}

static void nvme_poll_syslog(void)
{
    struct rtkit_message msg;
    rtkit_recv(nvme_rtkit, &msg);
}

static bool nvme_ctrl_disable(void)
{
    u64 timeout = timeout_calculate(NVME_TIMEOUT);

    clear32(nvme_base + NVME_CC, NVME_CC_EN);
    while (read32(nvme_base + NVME_CSTS) & NVME_CSTS_RDY && !timeout_expired(timeout))
        nvme_poll_syslog();

    return !(read32(nvme_base + NVME_CSTS) & NVME_CSTS_RDY);
}

static bool nvme_ctrl_enable(void)
{
    u64 timeout = timeout_calculate(NVME_ENABLE_TIMEOUT);

    mask32(nvme_base + NVME_CC, NVME_CC_SHN, NVME_CC_EN);
    while (!(read32(nvme_base + NVME_CSTS) & NVME_CSTS_RDY) && !timeout_expired(timeout))
        nvme_poll_syslog();

    return read32(nvme_base + NVME_CSTS) & NVME_CSTS_RDY;
}

static bool nvme_ctrl_shutdown(void)
{
    u64 timeout = timeout_calculate(NVME_SHUTDOWN_TIMEOUT);

    mask32(nvme_base + NVME_CC, NVME_CC_SHN, FIELD_PREP(NVME_CC_SHN, NVME_CC_SHN_NORMAL));
    while (FIELD_GET(NVME_CSTS_SHST, read32(nvme_base + NVME_CSTS)) != NVME_CSTS_SHST_DONE &&
           !timeout_expired(timeout))
        nvme_poll_syslog();

    return FIELD_GET(NVME_CSTS_SHST, read32(nvme_base + NVME_CSTS)) == NVME_CSTS_SHST_DONE;
}

static bool nvme_exec_command(struct nvme_queue *q, struct nvme_command *cmd, u64 *result)
{
    bool found = false;
    u64 timeout;
    u8 tag = 0;
    struct nvme_command *queue_cmd = &q->cmds[tag];
    struct apple_nvmmu_tcb *tcb = &q->tcbs[tag];

    memcpy(queue_cmd, cmd, sizeof(*cmd));
    queue_cmd->tag = tag;

    memset(tcb, 0, sizeof(*tcb));
    tcb->opcode = queue_cmd->opcode;
    tcb->dma_flags = 3; // always allow read+write to the PRP pages
    tcb->slot_id = tag;
    tcb->len = queue_cmd->cdw12;
    tcb->prp1 = queue_cmd->prp1;
    tcb->prp2 = queue_cmd->prp2;

    /* make sure ANS2 can see the command and tcb before triggering it */
    dma_wmb();

    nvme_poll_syslog();
    if (q->adminq)
        write32(nvme_base + NVME_DB_LINEAR_ASQ, tag);
    else
        write32(nvme_base + NVME_DB_LINEAR_IOSQ, tag);
    nvme_poll_syslog();

    timeout = timeout_calculate(NVME_TIMEOUT);
    struct nvme_completion cqe;
    while (!timeout_expired(timeout)) {
        nvme_poll_syslog();

        /* we need a DMA read barrier here since the CQ will be updated using DMA */
        dma_rmb();
        memcpy(&cqe, &q->cqes[q->cq_head], sizeof(cqe));
        if ((cqe.status & 1) != q->cq_phase)
            continue;

        if (cqe.tag == tag) {
            found = true;
            if (result)
                *result = cqe.result;
        } else {
            printf("nvme: invalid tag in CQ: expected %d but got %d\n", tag, cqe.tag);
        }

        write32(nvme_base + NVMMU_TCB_INVAL, cqe.tag);
        if (read32(nvme_base + NVMMU_TCB_STAT))
            printf("nvme: NVMMU invalidation for tag %d failed\n", cqe.tag);

        /* increment head and switch phase once the end of the queue has been reached */
        q->cq_head += 1;
        if (q->cq_head == NVME_QUEUE_SIZE) {
            q->cq_head = 0;
            q->cq_phase ^= 1;
        }

        if (q->adminq)
            write32(nvme_base + NVME_DB_ACQ, q->cq_head);
        else
            write32(nvme_base + NVME_DB_IOCQ, q->cq_head);
        break;
    }

    if (!found) {
        printf("nvme: could not find command completion in CQ\n");
        return false;
    }

    cqe.status >>= 1;
    if (cqe.status) {
        printf("nvme: command failed with status %d\n", cqe.status);
        return false;
    }

    return true;
}

bool nvme_init(void)
{
    if (nvme_initialized) {
        printf("nvme: already initialized\n");
        return true;
    }

    int adt_path[8];
    int node = adt_path_offset_trace(adt, "/arm-io/ans", adt_path);
    if (node < 0) {
        printf("nvme: Error getting NVMe node /arm-io/ans\n");
        return NULL;
    }

    u32 cg;
    if (ADT_GETPROP(adt, node, "clock-gates", &cg) < 0) {
        printf("nvme: Error getting NVMe clock-gates\n");
        return NULL;
    }
    nvme_die = FIELD_GET(PMGR_DIE_ID, cg);
    printf("nvme: ANS is on die %d\n", nvme_die);

    if (adt_get_reg(adt, adt_path, "reg", 3, &nvme_base, NULL) < 0) {
        printf("nvme: Error getting NVMe base address.\n");
        return NULL;
    }

    if (!alloc_queue(&adminq)) {
        printf("nvme: Error allocating admin queue\n");
        return NULL;
    }
    if (!alloc_queue(&ioq)) {
        printf("nvme: Error allocating admin queue\n");
        goto out_adminq;
    }

    ioq.adminq = false;
    adminq.adminq = true;

    nvme_asc = asc_init("/arm-io/ans");
    if (!nvme_asc)
        goto out_ioq;

    nvme_sart = sart_init("/arm-io/sart-ans");
    if (!nvme_sart)
        goto out_asc;

    nvme_rtkit = rtkit_init("nvme", nvme_asc, NULL, NULL, nvme_sart);
    if (!nvme_rtkit)
        goto out_sart;

    if (!rtkit_boot(nvme_rtkit))
        goto out_rtkit;

    if (poll32(nvme_base + NVME_BOOT_STATUS, 0xffffffff, NVME_BOOT_STATUS_OK, USEC_PER_SEC) < 0) {
        printf("nvme: ANS did not boot correctly.\n");
        goto out_shutdown;
    }

    /* setup controller and NVMMU for linear submission queue */
    set32(nvme_base + NVME_LINEAR_SQ_CTRL, NVME_LINEAR_SQ_CTRL_EN);
    clear32(nvme_base + NVME_UNKNONW_CTRL, NVME_UNKNONW_CTRL_PRP_NULL_CHECK);
    write32(nvme_base + NVME_MAX_PEND_CMDS_CTRL,
            ((NVME_QUEUE_SIZE - 1) << 16) | (NVME_QUEUE_SIZE - 1));
    write32(nvme_base + NVMMU_NUM, NVME_QUEUE_SIZE - 1);
    write64_lo_hi(nvme_base + NVMMU_ASQ_BASE, (u64)adminq.tcbs);
    write64_lo_hi(nvme_base + NVMMU_IOSQ_BASE, (u64)ioq.tcbs);

    /* setup admin queue */
    if (!nvme_ctrl_disable()) {
        printf("nvme: timeout while waiting for CSTS.RDY to clear\n");
        goto out_shutdown;
    }
    write64_lo_hi(nvme_base + NVME_ASQ, (u64)adminq.cmds);
    write64_lo_hi(nvme_base + NVME_ACQ, (u64)adminq.cqes);
    write32(nvme_base + NVME_AQA, ((NVME_QUEUE_SIZE - 1) << 16) | (NVME_QUEUE_SIZE - 1));
    if (!nvme_ctrl_enable()) {
        printf("nvme: timeout while waiting for CSTS.RDY to be set\n");
        goto out_disable_ctrl;
    }

    /* setup IO queue */
    struct nvme_command cmd;

    memset(&cmd, 0, sizeof(cmd));
    cmd.opcode = NVME_ADMIN_CMD_CREATE_CQ;
    cmd.prp1 = (u64)ioq.cqes;
    cmd.cdw10 = 1; // cq id
    cmd.cdw10 |= (NVME_QUEUE_SIZE - 1) << 16;
    cmd.cdw11 = NVME_QUEUE_CONTIGUOUS;
    if (!nvme_exec_command(&adminq, &cmd, NULL)) {
        printf("nvme: create cq command failed\n");
        goto out_disable_ctrl;
    }

    memset(&cmd, 0, sizeof(cmd));
    cmd.opcode = NVME_ADMIN_CMD_CREATE_SQ;
    cmd.prp1 = (u64)ioq.cmds;
    cmd.cdw10 = 1; // sq id
    cmd.cdw10 |= (NVME_QUEUE_SIZE - 1) << 16;
    cmd.cdw11 = NVME_QUEUE_CONTIGUOUS;
    cmd.cdw11 |= 1 << 16; // cq id for this sq
    if (!nvme_exec_command(&adminq, &cmd, NULL)) {
        printf("nvme: create sq command failed\n");
        goto out_delete_cq;
    }

    nvme_initialized = true;
    printf("nvme: initialized at 0x%lx\n", nvme_base);
    return true;

out_delete_cq:
    memset(&cmd, 0, sizeof(cmd));
    cmd.opcode = NVME_ADMIN_CMD_DELETE_CQ;
    cmd.cdw10 = 1; // cq id
    if (!nvme_exec_command(&adminq, &cmd, NULL))
        printf("nvme: delete cq command failed\n");
out_disable_ctrl:
    nvme_ctrl_shutdown();
    nvme_ctrl_disable();
    nvme_poll_syslog();
out_shutdown:
    rtkit_sleep(nvme_rtkit);
    // Some machines call this ANS, some ANS2...
    pmgr_reset(nvme_die, "ANS");
    pmgr_reset(nvme_die, "ANS2");
out_rtkit:
    rtkit_free(nvme_rtkit);
out_sart:
    sart_free(nvme_sart);
out_asc:
    asc_free(nvme_asc);
out_ioq:
    free_queue(&ioq);
out_adminq:
    free_queue(&adminq);
    return false;
}

void nvme_shutdown(void)
{
    if (!nvme_initialized) {
        printf("nvme: trying to shut down but not initialized\n");
        return;
    }

    struct nvme_command cmd;

    memset(&cmd, 0, sizeof(cmd));
    cmd.opcode = NVME_ADMIN_CMD_DELETE_SQ;
    cmd.cdw10 = 1; // sq id
    if (!nvme_exec_command(&adminq, &cmd, NULL))
        printf("nvme: delete sq command failed\n");

    memset(&cmd, 0, sizeof(cmd));
    cmd.opcode = NVME_ADMIN_CMD_DELETE_CQ;
    cmd.cdw10 = 1; // cq id
    if (!nvme_exec_command(&adminq, &cmd, NULL))
        printf("nvme: delete cq command failed\n");

    if (!nvme_ctrl_shutdown())
        printf("nvme: timeout while waiting for controller shutdown\n");
    if (!nvme_ctrl_disable())
        printf("nvme: timeout while waiting for CSTS.RDY to clear\n");

    rtkit_sleep(nvme_rtkit);
    // Some machines call this ANS, some ANS2...
    pmgr_reset(nvme_die, "ANS");
    pmgr_reset(nvme_die, "ANS2");
    rtkit_free(nvme_rtkit);
    sart_free(nvme_sart);
    asc_free(nvme_asc);
    free_queue(&ioq);
    free_queue(&adminq);
    nvme_initialized = false;

    printf("nvme: shutdown done\n");
}

bool nvme_flush(u32 nsid)
{
    struct nvme_command cmd;

    if (!nvme_initialized)
        return false;

    memset(&cmd, 0, sizeof(cmd));
    cmd.opcode = NVME_CMD_FLUSH;
    cmd.nsid = nsid;

    return nvme_exec_command(&ioq, &cmd, NULL);
}

bool nvme_read(u32 nsid, u64 lba, void *buffer)
{
    struct nvme_command cmd;
    u64 buffer_addr = (u64)buffer;

    if (!nvme_initialized)
        return false;

    /* no need for 16K alignment here since the NVME page size is 4k */
    if (buffer_addr & (SZ_4K - 1))
        return false;

    memset(&cmd, 0, sizeof(cmd));
    cmd.opcode = NVME_CMD_READ;
    cmd.nsid = nsid;
    cmd.prp1 = (u64)buffer_addr;
    cmd.cdw10 = lba;
    cmd.cdw11 = lba >> 32;
    cmd.cdw12 = 1; // 4096 bytes

    return nvme_exec_command(&ioq, &cmd, NULL);
}

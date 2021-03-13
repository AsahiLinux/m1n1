/**
 * core.h - DesignWare USB3 DRD Core Header
 * linux commit 7bc5a6ba369217e0137833f5955cf0b0f08b0712 before
 * the switch to GPLv2 only
 *
 * Copyright (C) 2010-2011 Texas Instruments Incorporated - http://www.ti.com
 *
 * Authors: Felipe Balbi <balbi@ti.com>,
 *	    Sebastian Andrzej Siewior <bigeasy@linutronix.de>
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions, and the following disclaimer,
 *    without modification.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 * 3. The names of the above-listed copyright holders may not be used
 *    to endorse or promote products derived from this software without
 *    specific prior written permission.
 *
 * ALTERNATIVELY, this software may be distributed under the terms of the
 * GNU General Public License ("GPL") version 2, as published by the Free
 * Software Foundation.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
 * IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 * PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
 * LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
 * NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 * SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#ifndef __DRIVERS_USB_DWC3_CORE_H
#define __DRIVERS_USB_DWC3_CORE_H

#include "types.h"

/* Global constants */
#define DWC3_EP0_BOUNCE_SIZE    512
#define DWC3_ENDPOINTS_NUM      32
#define DWC3_XHCI_RESOURCES_NUM 2

#define DWC3_EVENT_SIZE         4  /* bytes */
#define DWC3_EVENT_MAX_NUM      64 /* 2 events/endpoint */
#define DWC3_EVENT_BUFFERS_SIZE (DWC3_EVENT_SIZE * DWC3_EVENT_MAX_NUM)
#define DWC3_EVENT_TYPE_MASK    0xfe

#define DWC3_EVENT_TYPE_DEV    0
#define DWC3_EVENT_TYPE_CARKIT 3
#define DWC3_EVENT_TYPE_I2C    4

#define DWC3_DEVICE_EVENT_DISCONNECT         0
#define DWC3_DEVICE_EVENT_RESET              1
#define DWC3_DEVICE_EVENT_CONNECT_DONE       2
#define DWC3_DEVICE_EVENT_LINK_STATUS_CHANGE 3
#define DWC3_DEVICE_EVENT_WAKEUP             4
#define DWC3_DEVICE_EVENT_HIBER_REQ          5
#define DWC3_DEVICE_EVENT_EOPF               6
#define DWC3_DEVICE_EVENT_SOF                7
#define DWC3_DEVICE_EVENT_ERRATIC_ERROR      9
#define DWC3_DEVICE_EVENT_CMD_CMPL           10
#define DWC3_DEVICE_EVENT_OVERFLOW           11

#define DWC3_GEVNTCOUNT_MASK 0xfffc
#define DWC3_GSNPSID_MASK    0xffff0000
#define DWC3_GSNPSREV_MASK   0xffff

/* DWC3 registers memory space boundries */
#define DWC3_XHCI_REGS_START    0x0
#define DWC3_XHCI_REGS_END      0x7fff
#define DWC3_GLOBALS_REGS_START 0xc100
#define DWC3_GLOBALS_REGS_END   0xc6ff
#define DWC3_DEVICE_REGS_START  0xc700
#define DWC3_DEVICE_REGS_END    0xcbff
#define DWC3_OTG_REGS_START     0xcc00
#define DWC3_OTG_REGS_END       0xccff

/* Global Registers */
#define DWC3_GSBUSCFG0     0xc100
#define DWC3_GSBUSCFG1     0xc104
#define DWC3_GTXTHRCFG     0xc108
#define DWC3_GRXTHRCFG     0xc10c
#define DWC3_GCTL          0xc110
#define DWC3_GEVTEN        0xc114
#define DWC3_GSTS          0xc118
#define DWC3_GSNPSID       0xc120
#define DWC3_GGPIO         0xc124
#define DWC3_GUID          0xc128
#define DWC3_GUCTL         0xc12c
#define DWC3_GBUSERRADDR0  0xc130
#define DWC3_GBUSERRADDR1  0xc134
#define DWC3_GPRTBIMAP0    0xc138
#define DWC3_GPRTBIMAP1    0xc13c
#define DWC3_GHWPARAMS0    0xc140
#define DWC3_GHWPARAMS1    0xc144
#define DWC3_GHWPARAMS2    0xc148
#define DWC3_GHWPARAMS3    0xc14c
#define DWC3_GHWPARAMS4    0xc150
#define DWC3_GHWPARAMS5    0xc154
#define DWC3_GHWPARAMS6    0xc158
#define DWC3_GHWPARAMS7    0xc15c
#define DWC3_GDBGFIFOSPACE 0xc160
#define DWC3_GDBGLTSSM     0xc164
#define DWC3_GPRTBIMAP_HS0 0xc180
#define DWC3_GPRTBIMAP_HS1 0xc184
#define DWC3_GPRTBIMAP_FS0 0xc188
#define DWC3_GPRTBIMAP_FS1 0xc18c

#define DWC3_GUSB2PHYCFG(n) (0xc200 + (n * 0x04))
#define DWC3_GUSB2I2CCTL(n) (0xc240 + (n * 0x04))

#define DWC3_GUSB2PHYACC(n) (0xc280 + (n * 0x04))

#define DWC3_GUSB3PIPECTL(n) (0xc2c0 + (n * 0x04))

#define DWC3_GTXFIFOSIZ(n) (0xc300 + (n * 0x04))
#define DWC3_GRXFIFOSIZ(n) (0xc380 + (n * 0x04))

#define DWC3_GEVNTADRLO(n) (0xc400 + (n * 0x10))
#define DWC3_GEVNTADRHI(n) (0xc404 + (n * 0x10))
#define DWC3_GEVNTSIZ(n)   (0xc408 + (n * 0x10))
#define DWC3_GEVNTCOUNT(n) (0xc40c + (n * 0x10))

#define DWC3_GHWPARAMS8 0xc600

/* Device Registers */
#define DWC3_DCFG          0xc700
#define DWC3_DCTL          0xc704
#define DWC3_DEVTEN        0xc708
#define DWC3_DSTS          0xc70c
#define DWC3_DGCMDPAR      0xc710
#define DWC3_DGCMD         0xc714
#define DWC3_DALEPENA      0xc720
#define DWC3_DEPCMDPAR2(n) (0xc800 + (n * 0x10))
#define DWC3_DEPCMDPAR1(n) (0xc804 + (n * 0x10))
#define DWC3_DEPCMDPAR0(n) (0xc808 + (n * 0x10))
#define DWC3_DEPCMD(n)     (0xc80c + (n * 0x10))

/* OTG Registers */
#define DWC3_OCFG   0xcc00
#define DWC3_OCTL   0xcc04
#define DWC3_OEVT   0xcc08
#define DWC3_OEVTEN 0xcc0C
#define DWC3_OSTS   0xcc10

/* Bit fields */

/* Global Configuration Register */
#define DWC3_GCTL_PWRDNSCALE(n) ((n) << 19)
#define DWC3_GCTL_U2RSTECN      (1 << 16)
#define DWC3_GCTL_RAMCLKSEL(x)  (((x)&DWC3_GCTL_CLK_MASK) << 6)
#define DWC3_GCTL_CLK_BUS       (0)
#define DWC3_GCTL_CLK_PIPE      (1)
#define DWC3_GCTL_CLK_PIPEHALF  (2)
#define DWC3_GCTL_CLK_MASK      (3)

#define DWC3_GCTL_PRTCAP(n)     (((n) & (3 << 12)) >> 12)
#define DWC3_GCTL_PRTCAPDIR(n)  ((n) << 12)
#define DWC3_GCTL_PRTCAP_HOST   1
#define DWC3_GCTL_PRTCAP_DEVICE 2
#define DWC3_GCTL_PRTCAP_OTG    3

#define DWC3_GCTL_CORESOFTRESET    (1 << 11)
#define DWC3_GCTL_SCALEDOWN(n)     ((n) << 4)
#define DWC3_GCTL_SCALEDOWN_MASK   DWC3_GCTL_SCALEDOWN(3)
#define DWC3_GCTL_DISSCRAMBLE      (1 << 3)
#define DWC3_GCTL_GBLHIBERNATIONEN (1 << 1)
#define DWC3_GCTL_DSBLCLKGTNG      (1 << 0)

/* Global USB2 PHY Configuration Register */
#define DWC3_GUSB2PHYCFG_PHYSOFTRST (1 << 31)
#define DWC3_GUSB2PHYCFG_SUSPHY     (1 << 6)

/* Global USB3 PIPE Control Register */
#define DWC3_GUSB3PIPECTL_PHYSOFTRST (1 << 31)
#define DWC3_GUSB3PIPECTL_SUSPHY     (1 << 17)

/* Global TX Fifo Size Register */
#define DWC3_GTXFIFOSIZ_TXFDEF(n)    ((n)&0xffff)
#define DWC3_GTXFIFOSIZ_TXFSTADDR(n) ((n)&0xffff0000)

/* Global HWPARAMS1 Register */
#define DWC3_GHWPARAMS1_EN_PWROPT(n)  (((n) & (3 << 24)) >> 24)
#define DWC3_GHWPARAMS1_EN_PWROPT_NO  0
#define DWC3_GHWPARAMS1_EN_PWROPT_CLK 1
#define DWC3_GHWPARAMS1_EN_PWROPT_HIB 2
#define DWC3_GHWPARAMS1_PWROPT(n)     ((n) << 24)
#define DWC3_GHWPARAMS1_PWROPT_MASK   DWC3_GHWPARAMS1_PWROPT(3)

/* Global HWPARAMS4 Register */
#define DWC3_GHWPARAMS4_HIBER_SCRATCHBUFS(n) (((n) & (0x0f << 13)) >> 13)
#define DWC3_MAX_HIBER_SCRATCHBUFS           15

/* Device Configuration Register */
#define DWC3_DCFG_LPM_CAP       (1 << 22)
#define DWC3_DCFG_DEVADDR(addr) ((addr) << 3)
#define DWC3_DCFG_DEVADDR_MASK  DWC3_DCFG_DEVADDR(0x7f)

#define DWC3_DCFG_SPEED_MASK (7 << 0)
#define DWC3_DCFG_SUPERSPEED (4 << 0)
#define DWC3_DCFG_HIGHSPEED  (0 << 0)
#define DWC3_DCFG_FULLSPEED2 (1 << 0)
#define DWC3_DCFG_LOWSPEED   (2 << 0)
#define DWC3_DCFG_FULLSPEED1 (3 << 0)

#define DWC3_DCFG_LPM_CAP (1 << 22)

/* Device Control Register */
#define DWC3_DCTL_RUN_STOP (1 << 31)
#define DWC3_DCTL_CSFTRST  (1 << 30)
#define DWC3_DCTL_LSFTRST  (1 << 29)

#define DWC3_DCTL_HIRD_THRES_MASK (0x1f << 24)
#define DWC3_DCTL_HIRD_THRES(n)   ((n) << 24)

#define DWC3_DCTL_APPL1RES (1 << 23)

/* These apply for core versions 1.87a and earlier */
#define DWC3_DCTL_TRGTULST_MASK     (0x0f << 17)
#define DWC3_DCTL_TRGTULST(n)       ((n) << 17)
#define DWC3_DCTL_TRGTULST_U2       (DWC3_DCTL_TRGTULST(2))
#define DWC3_DCTL_TRGTULST_U3       (DWC3_DCTL_TRGTULST(3))
#define DWC3_DCTL_TRGTULST_SS_DIS   (DWC3_DCTL_TRGTULST(4))
#define DWC3_DCTL_TRGTULST_RX_DET   (DWC3_DCTL_TRGTULST(5))
#define DWC3_DCTL_TRGTULST_SS_INACT (DWC3_DCTL_TRGTULST(6))

/* These apply for core versions 1.94a and later */
#define DWC3_DCTL_KEEP_CONNECT (1 << 19)
#define DWC3_DCTL_L1_HIBER_EN  (1 << 18)
#define DWC3_DCTL_CRS          (1 << 17)
#define DWC3_DCTL_CSS          (1 << 16)

#define DWC3_DCTL_INITU2ENA    (1 << 12)
#define DWC3_DCTL_ACCEPTU2ENA  (1 << 11)
#define DWC3_DCTL_INITU1ENA    (1 << 10)
#define DWC3_DCTL_ACCEPTU1ENA  (1 << 9)
#define DWC3_DCTL_TSTCTRL_MASK (0xf << 1)

#define DWC3_DCTL_ULSTCHNGREQ_MASK (0x0f << 5)
#define DWC3_DCTL_ULSTCHNGREQ(n)   (((n) << 5) & DWC3_DCTL_ULSTCHNGREQ_MASK)

#define DWC3_DCTL_ULSTCHNG_NO_ACTION   (DWC3_DCTL_ULSTCHNGREQ(0))
#define DWC3_DCTL_ULSTCHNG_SS_DISABLED (DWC3_DCTL_ULSTCHNGREQ(4))
#define DWC3_DCTL_ULSTCHNG_RX_DETECT   (DWC3_DCTL_ULSTCHNGREQ(5))
#define DWC3_DCTL_ULSTCHNG_SS_INACTIVE (DWC3_DCTL_ULSTCHNGREQ(6))
#define DWC3_DCTL_ULSTCHNG_RECOVERY    (DWC3_DCTL_ULSTCHNGREQ(8))
#define DWC3_DCTL_ULSTCHNG_COMPLIANCE  (DWC3_DCTL_ULSTCHNGREQ(10))
#define DWC3_DCTL_ULSTCHNG_LOOPBACK    (DWC3_DCTL_ULSTCHNGREQ(11))

/* Device Event Enable Register */
#define DWC3_DEVTEN_VNDRDEVTSTRCVEDEN   (1 << 12)
#define DWC3_DEVTEN_EVNTOVERFLOWEN      (1 << 11)
#define DWC3_DEVTEN_CMDCMPLTEN          (1 << 10)
#define DWC3_DEVTEN_ERRTICERREN         (1 << 9)
#define DWC3_DEVTEN_SOFEN               (1 << 7)
#define DWC3_DEVTEN_EOPFEN              (1 << 6)
#define DWC3_DEVTEN_HIBERNATIONREQEVTEN (1 << 5)
#define DWC3_DEVTEN_WKUPEVTEN           (1 << 4)
#define DWC3_DEVTEN_ULSTCNGEN           (1 << 3)
#define DWC3_DEVTEN_CONNECTDONEEN       (1 << 2)
#define DWC3_DEVTEN_USBRSTEN            (1 << 1)
#define DWC3_DEVTEN_DISCONNEVTEN        (1 << 0)

/* Device Status Register */
#define DWC3_DSTS_DCNRD (1 << 29)

/* This applies for core versions 1.87a and earlier */
#define DWC3_DSTS_PWRUPREQ (1 << 24)

/* These apply for core versions 1.94a and later */
#define DWC3_DSTS_RSS (1 << 25)
#define DWC3_DSTS_SSS (1 << 24)

#define DWC3_DSTS_COREIDLE   (1 << 23)
#define DWC3_DSTS_DEVCTRLHLT (1 << 22)

#define DWC3_DSTS_USBLNKST_MASK (0x0f << 18)
#define DWC3_DSTS_USBLNKST(n)   (((n)&DWC3_DSTS_USBLNKST_MASK) >> 18)

#define DWC3_DSTS_RXFIFOEMPTY (1 << 17)

#define DWC3_DSTS_SOFFN_MASK (0x3fff << 3)
#define DWC3_DSTS_SOFFN(n)   (((n)&DWC3_DSTS_SOFFN_MASK) >> 3)

#define DWC3_DSTS_CONNECTSPD (7 << 0)

#define DWC3_DSTS_SUPERSPEED (4 << 0)
#define DWC3_DSTS_HIGHSPEED  (0 << 0)
#define DWC3_DSTS_FULLSPEED2 (1 << 0)
#define DWC3_DSTS_LOWSPEED   (2 << 0)
#define DWC3_DSTS_FULLSPEED1 (3 << 0)

/* Device Generic Command Register */
#define DWC3_DGCMD_SET_LMP          0x01
#define DWC3_DGCMD_SET_PERIODIC_PAR 0x02
#define DWC3_DGCMD_XMIT_FUNCTION    0x03

/* These apply for core versions 1.94a and later */
#define DWC3_DGCMD_SET_SCRATCHPAD_ADDR_LO 0x04
#define DWC3_DGCMD_SET_SCRATCHPAD_ADDR_HI 0x05

#define DWC3_DGCMD_SELECTED_FIFO_FLUSH  0x09
#define DWC3_DGCMD_ALL_FIFO_FLUSH       0x0a
#define DWC3_DGCMD_SET_ENDPOINT_NRDY    0x0c
#define DWC3_DGCMD_RUN_SOC_BUS_LOOPBACK 0x10

#define DWC3_DGCMD_STATUS(n) (((n) >> 15) & 1)
#define DWC3_DGCMD_CMDACT    (1 << 10)
#define DWC3_DGCMD_CMDIOC    (1 << 8)

/* Device Generic Command Parameter Register */
#define DWC3_DGCMDPAR_FORCE_LINKPM_ACCEPT (1 << 0)
#define DWC3_DGCMDPAR_FIFO_NUM(n)         ((n) << 0)
#define DWC3_DGCMDPAR_RX_FIFO             (0 << 5)
#define DWC3_DGCMDPAR_TX_FIFO             (1 << 5)
#define DWC3_DGCMDPAR_LOOPBACK_DIS        (0 << 0)
#define DWC3_DGCMDPAR_LOOPBACK_ENA        (1 << 0)

/* Device Endpoint Command Register */
#define DWC3_DEPCMD_PARAM_SHIFT    16
#define DWC3_DEPCMD_PARAM(x)       ((x) << DWC3_DEPCMD_PARAM_SHIFT)
#define DWC3_DEPCMD_GET_RSC_IDX(x) (((x) >> DWC3_DEPCMD_PARAM_SHIFT) & 0x7f)
#define DWC3_DEPCMD_STATUS(x)      (((x) >> 15) & 1)
#define DWC3_DEPCMD_HIPRI_FORCERM  (1 << 11)
#define DWC3_DEPCMD_CMDACT         (1 << 10)
#define DWC3_DEPCMD_CMDIOC         (1 << 8)

#define DWC3_DEPCMD_DEPSTARTCFG    (0x09 << 0)
#define DWC3_DEPCMD_ENDTRANSFER    (0x08 << 0)
#define DWC3_DEPCMD_UPDATETRANSFER (0x07 << 0)
#define DWC3_DEPCMD_STARTTRANSFER  (0x06 << 0)
#define DWC3_DEPCMD_CLEARSTALL     (0x05 << 0)
#define DWC3_DEPCMD_SETSTALL       (0x04 << 0)
/* This applies for core versions 1.90a and earlier */
#define DWC3_DEPCMD_GETSEQNUMBER (0x03 << 0)
/* This applies for core versions 1.94a and later */
#define DWC3_DEPCMD_GETEPSTATE        (0x03 << 0)
#define DWC3_DEPCMD_SETTRANSFRESOURCE (0x02 << 0)
#define DWC3_DEPCMD_SETEPCONFIG       (0x01 << 0)

/* The EP number goes 0..31 so ep0 is always out and ep1 is always in */
#define DWC3_DALEPENA_EP(n) (1 << n)

#define DWC3_DEPCMD_TYPE_CONTROL 0
#define DWC3_DEPCMD_TYPE_ISOC    1
#define DWC3_DEPCMD_TYPE_BULK    2
#define DWC3_DEPCMD_TYPE_INTR    3

#define DWC3_EVENT_PENDING BIT(0)

#define DWC3_EP_FLAG_STALLED (1 << 0)
#define DWC3_EP_FLAG_WEDGED  (1 << 1)

#define DWC3_EP_DIRECTION_TX true
#define DWC3_EP_DIRECTION_RX false

#define DWC3_TRB_NUM  32
#define DWC3_TRB_MASK (DWC3_TRB_NUM - 1)

#define DWC3_EP_ENABLED         (1 << 0)
#define DWC3_EP_STALL           (1 << 1)
#define DWC3_EP_WEDGE           (1 << 2)
#define DWC3_EP_BUSY            (1 << 4)
#define DWC3_EP_PENDING_REQUEST (1 << 5)
#define DWC3_EP_MISSED_ISOC     (1 << 6)

/* This last one is specific to EP0 */
#define DWC3_EP0_DIR_IN (1 << 31)

enum dwc3_link_state {
    /* In SuperSpeed */
    DWC3_LINK_STATE_U0 = 0x00, /* in HS, means ON */
    DWC3_LINK_STATE_U1 = 0x01,
    DWC3_LINK_STATE_U2 = 0x02, /* in HS, means SLEEP */
    DWC3_LINK_STATE_U3 = 0x03, /* in HS, means SUSPEND */
    DWC3_LINK_STATE_SS_DIS = 0x04,
    DWC3_LINK_STATE_RX_DET = 0x05, /* in HS, means Early Suspend */
    DWC3_LINK_STATE_SS_INACT = 0x06,
    DWC3_LINK_STATE_POLL = 0x07,
    DWC3_LINK_STATE_RECOV = 0x08,
    DWC3_LINK_STATE_HRESET = 0x09,
    DWC3_LINK_STATE_CMPLY = 0x0a,
    DWC3_LINK_STATE_LPBK = 0x0b,
    DWC3_LINK_STATE_RESET = 0x0e,
    DWC3_LINK_STATE_RESUME = 0x0f,
    DWC3_LINK_STATE_MASK = 0x0f,
};

/* TRB Length, PCM and Status */
#define DWC3_TRB_SIZE_MASK      (0x00ffffff)
#define DWC3_TRB_SIZE_LENGTH(n) ((n)&DWC3_TRB_SIZE_MASK)
#define DWC3_TRB_SIZE_PCM1(n)   (((n)&0x03) << 24)
#define DWC3_TRB_SIZE_TRBSTS(n) (((n) & (0x0f << 28)) >> 28)

#define DWC3_TRBSTS_OK            0
#define DWC3_TRBSTS_MISSED_ISOC   1
#define DWC3_TRBSTS_SETUP_PENDING 2
#define DWC3_TRB_STS_XFER_IN_PROG 4

/* TRB Control */
#define DWC3_TRB_CTRL_HWO         (1 << 0)
#define DWC3_TRB_CTRL_LST         (1 << 1)
#define DWC3_TRB_CTRL_CHN         (1 << 2)
#define DWC3_TRB_CTRL_CSP         (1 << 3)
#define DWC3_TRB_CTRL_TRBCTL(n)   (((n)&0x3f) << 4)
#define DWC3_TRB_CTRL_ISP_IMI     (1 << 10)
#define DWC3_TRB_CTRL_IOC         (1 << 11)
#define DWC3_TRB_CTRL_SID_SOFN(n) (((n)&0xffff) << 14)

#define DWC3_TRBCTL_NORMAL            DWC3_TRB_CTRL_TRBCTL(1)
#define DWC3_TRBCTL_CONTROL_SETUP     DWC3_TRB_CTRL_TRBCTL(2)
#define DWC3_TRBCTL_CONTROL_STATUS2   DWC3_TRB_CTRL_TRBCTL(3)
#define DWC3_TRBCTL_CONTROL_STATUS3   DWC3_TRB_CTRL_TRBCTL(4)
#define DWC3_TRBCTL_CONTROL_DATA      DWC3_TRB_CTRL_TRBCTL(5)
#define DWC3_TRBCTL_ISOCHRONOUS_FIRST DWC3_TRB_CTRL_TRBCTL(6)
#define DWC3_TRBCTL_ISOCHRONOUS       DWC3_TRB_CTRL_TRBCTL(7)
#define DWC3_TRBCTL_LINK_TRB          DWC3_TRB_CTRL_TRBCTL(8)

/**
 * struct dwc3_trb - transfer request block (hw format)
 * @bpl: DW0-3
 * @bph: DW4-7
 * @size: DW8-B
 * @trl: DWC-F
 */
struct dwc3_trb {
    u32 bpl;
    u32 bph;
    u32 size;
    u32 ctrl;
} PACKED;

/* HWPARAMS0 */
#define DWC3_MODE(n) ((n)&0x7)

#define DWC3_MODE_DEVICE 0
#define DWC3_MODE_HOST   1
#define DWC3_MODE_DRD    2
#define DWC3_MODE_HUB    3

#define DWC3_MDWIDTH(n) (((n)&0xff00) >> 8)

/* HWPARAMS1 */
#define DWC3_NUM_INT(n) (((n) & (0x3f << 15)) >> 15)

/* HWPARAMS3 */
#define DWC3_NUM_IN_EPS_MASK (0x1f << 18)
#define DWC3_NUM_EPS_MASK    (0x3f << 12)
#define DWC3_NUM_EPS(p)      (((p)->hwparams3 & (DWC3_NUM_EPS_MASK)) >> 12)
#define DWC3_NUM_IN_EPS(p)   (((p)->hwparams3 & (DWC3_NUM_IN_EPS_MASK)) >> 18)

/* HWPARAMS7 */
#define DWC3_RAM1_DEPTH(n) ((n)&0xffff)

#define DWC3_REVISION_173A 0x5533173a
#define DWC3_REVISION_175A 0x5533175a
#define DWC3_REVISION_180A 0x5533180a
#define DWC3_REVISION_183A 0x5533183a
#define DWC3_REVISION_185A 0x5533185a
#define DWC3_REVISION_187A 0x5533187a
#define DWC3_REVISION_188A 0x5533188a
#define DWC3_REVISION_190A 0x5533190a
#define DWC3_REVISION_194A 0x5533194a
#define DWC3_REVISION_200A 0x5533200a
#define DWC3_REVISION_202A 0x5533202a
#define DWC3_REVISION_210A 0x5533210a
#define DWC3_REVISION_220A 0x5533220a
#define DWC3_REVISION_230A 0x5533230a
#define DWC3_REVISION_240A 0x5533240a
#define DWC3_REVISION_250A 0x5533250a

/* -------------------------------------------------------------------------- */

/* -------------------------------------------------------------------------- */

struct dwc3_event_type {
    u32 is_devspec : 1;
    u32 type : 7;
    u32 reserved8_31 : 24;
} PACKED;

#define DWC3_DEPEVT_XFERCOMPLETE   0x01
#define DWC3_DEPEVT_XFERINPROGRESS 0x02
#define DWC3_DEPEVT_XFERNOTREADY   0x03
#define DWC3_DEPEVT_RXTXFIFOEVT    0x04
#define DWC3_DEPEVT_STREAMEVT      0x06
#define DWC3_DEPEVT_EPCMDCMPLT     0x07

/**
 * struct dwc3_event_depvt - Device Endpoint Events
 * @one_bit: indicates this is an endpoint event (not used)
 * @endpoint_number: number of the endpoint
 * @endpoint_event: The event we have:
 *	0x00	- Reserved
 *	0x01	- XferComplete
 *	0x02	- XferInProgress
 *	0x03	- XferNotReady
 *	0x04	- RxTxFifoEvt (IN->Underrun, OUT->Overrun)
 *	0x05	- Reserved
 *	0x06	- StreamEvt
 *	0x07	- EPCmdCmplt
 * @reserved11_10: Reserved, don't use.
 * @status: Indicates the status of the event. Refer to databook for
 *	more information.
 * @parameters: Parameters of the current event. Refer to databook for
 *	more information.
 */
struct dwc3_event_depevt {
    u32 one_bit : 1;
    u32 endpoint_number : 5;
    u32 endpoint_event : 4;
    u32 reserved11_10 : 2;
    u32 status : 4;

/* Within XferNotReady */
#define DEPEVT_STATUS_TRANSFER_ACTIVE (1 << 3)

/* Within XferComplete */
#define DEPEVT_STATUS_BUSERR (1 << 0)
#define DEPEVT_STATUS_SHORT  (1 << 1)
#define DEPEVT_STATUS_IOC    (1 << 2)
#define DEPEVT_STATUS_LST    (1 << 3)

/* Stream event only */
#define DEPEVT_STREAMEVT_FOUND    1
#define DEPEVT_STREAMEVT_NOTFOUND 2

/* Control-only Status */
#define DEPEVT_STATUS_CONTROL_DATA   1
#define DEPEVT_STATUS_CONTROL_STATUS 2

    u32 parameters : 16;
} PACKED;

#define DWC3_DEVT_DISCONN         0x00
#define DWC3_DEVT_USBRST          0x01
#define DWC3_DEVT_CONNECTDONE     0x02
#define DWC3_DEVT_ULSTCHNG        0x03
#define DWC3_DEVT_WKUPEVT         0x04
#define DWC3_DEVT_EOPF            0x06
#define DWC3_DEVT_SOF             0x07
#define DWC3_DEVT_ERRTICERR       0x09
#define DWC3_DEVT_CMDCMPLT        0x0a
#define DWC3_DEVT_EVNTOVERFLOW    0x0b
#define DWC3_DEVT_VNDRDEVTSTRCVED 0x0c

/**
 * struct dwc3_event_devt - Device Events
 * @one_bit: indicates this is a non-endpoint event (not used)
 * @device_event: indicates it's a device event. Should read as 0x00
 * @type: indicates the type of device event.
 *	0	- DisconnEvt
 *	1	- USBRst
 *	2	- ConnectDone
 *	3	- ULStChng
 *	4	- WkUpEvt
 *	5	- Reserved
 *	6	- EOPF
 *	7	- SOF
 *	8	- Reserved
 *	9	- ErrticErr
 *	10	- CmdCmplt
 *	11	- EvntOverflow
 *	12	- VndrDevTstRcved
 * @reserved15_12: Reserved, not used
 * @event_info: Information about this event
 * @reserved31_24: Reserved, not used
 */
struct dwc3_event_devt {
    u32 one_bit : 1;
    u32 device_event : 7;
    u32 type : 4;
    u32 reserved15_12 : 4;
    u32 event_info : 8;
    u32 reserved31_24 : 8;
} PACKED;

/**
 * struct dwc3_event_gevt - Other Core Events
 * @one_bit: indicates this is a non-endpoint event (not used)
 * @device_event: indicates it's (0x03) Carkit or (0x04) I2C event.
 * @phy_port_number: self-explanatory
 * @reserved31_12: Reserved, not used.
 */
struct dwc3_event_gevt {
    u32 one_bit : 1;
    u32 device_event : 7;
    u32 phy_port_number : 4;
    u32 reserved31_12 : 20;
} PACKED;

union dwc3_event {
    u32 raw;
    struct dwc3_event_type type;
    struct dwc3_event_depevt depevt;
    struct dwc3_event_devt devt;
    struct dwc3_event_gevt gevt;
};

#define DWC3_DEPCFG_EP_TYPE(n)         (((n)&0x3) << 1)
#define DWC3_DEPCFG_EP_NUMBER(n)       (((n)&0x1f) << 25)
#define DWC3_DEPCFG_FIFO_NUMBER(n)     (((n)&0xf) << 17)
#define DWC3_DEPCFG_MAX_PACKET_SIZE(n) (((n)&0x7ff) << 3)

#define DWC3_DEPCFG_INT_NUM(n)          (((n)&0x1f) << 0)
#define DWC3_DEPCFG_XFER_COMPLETE_EN    BIT(8)
#define DWC3_DEPCFG_XFER_IN_PROGRESS_EN BIT(9)
#define DWC3_DEPCFG_XFER_NOT_READY_EN   BIT(10)
#define DWC3_DEPCFG_FIFO_ERROR_EN       BIT(11)
#define DWC3_DEPCFG_STREAM_EVENT_EN     BIT(13)
#define DWC3_DEPCFG_BINTERVAL_M1(n)     (((n)&0xff) << 16)
#define DWC3_DEPCFG_STREAM_CAPABLE      BIT(24)
#define DWC3_DEPCFG_EP_NUMBER(n)        (((n)&0x1f) << 25)
#define DWC3_DEPCFG_BULK_BASED          BIT(30)
#define DWC3_DEPCFG_FIFO_BASED          BIT(31)

#endif /* __DRIVERS_USB_DWC3_CORE_H */

# SPDX-License-Identifier: MIT

from enum import IntEnum
from m1n1.utils import *


class R_XHCI_USBCMD(Register32):
    EU3S = 11
    EWE = 10
    CRS = 9
    CSS = 8
    LHCRST = 7
    HSEE = 3
    INTE = 2
    HCRST = 1
    RS = 0


class R_XHCI_USBSTS(Register32):
    HCE = 12
    CNR = 11
    SRE = 10
    RSS = 9
    SSS = 8
    PCD = 4
    EINT = 3
    HSE = 2
    HCH = 0


class R_XHCI_CRCR_LO(Register32):
    CRP = 31, 6
    CRR = 3
    CA = 2
    CS = 1
    RCS = 0


class R_XHCI_DNCTRL(Register32):
    N0_N15 = 15, 0


class R_XHCI_DOORBELL(Register32):
    TASK_ID = 31, 16
    RSVD = 15, 8
    TARGET = 7, 0


class R_XHCI_PORTSC(Register32):
    CCS = 0
    PED = 1
    OCA = 3
    RESET = 4
    PLS = 8, 5
    PP = 9
    SPEED = 13, 10
    PIC = 15, 14
    LWS = 16
    CSC = 17
    PEC = 18
    WRC = 19
    OCC = 20
    PRC = 21
    PLC = 22
    CEC = 23
    CAS = 24
    WCE = 25
    WDE = 26
    WOE = 27
    DR = 30
    WPR = 31


class R_XHCI_PORTLI(Register32):
    ERROR_CNT = 15, 0
    RLC = 19, 16
    TLC = 23, 20
    RSV = 31, 24


class R_XHCI_IMAN(Register32):
    IP = 0
    IE = 1


class XhciRegs(RegMap):
    HCSPARAMS1 = 0x04, Register32
    HCSPARAMS2 = 0x08, Register32
    HCSPARAMS3 = 0x0C, Register32
    HCCPARAMS1 = 0x10, Register32
    DBOFF = 0x14, Register32
    RTSOFF = 0x18, Register32
    HCCPARAMS2 = 0x1C, Register32
    USBCMD = 0x20, R_XHCI_USBCMD
    USBSTS = 0x24, R_XHCI_USBSTS
    DNCTRL = 0x34, R_XHCI_DNCTRL
    CRCR_LO = 0x38, R_XHCI_CRCR_LO
    CRCR_HI = 0x3C, Register32
    DCBAAP_LO = 0x50, Register32
    DCBAAP_HI = 0x54, Register32

    PORTSC0 = 0x420, R_XHCI_PORTSC
    PORTPMSC0 = 0x424, Register32
    PORTLI0 = 0x428, R_XHCI_PORTLI
    PORTHLPMC0 = 0x42C, Register32

    PORTSC1 = 0x430, R_XHCI_PORTSC
    PORTPMSC1 = 0x434, Register32
    PORTLI1 = 0x438, R_XHCI_PORTLI
    PORTHLPMC1 = 0x43C, Register32

    MFINDEX = 0x440, Register32
    IMAN0 = 0x460 + 0x00, R_XHCI_IMAN
    IMOD0 = 0x460 + 0x04, Register32
    ERSTSZ0 = 0x460 + 0x08, Register32
    RSVD0 = 0x460 + 0x0C, Register32
    ERSTBA0 = 0x460 + 0x10, Register64
    ERDP0 = 0x460 + 0x18, Register64

    IMAN1 = 0x480 + 0x00, R_XHCI_IMAN
    IMOD1 = 0x480 + 0x04, Register32
    ERSTSZ1 = 0x480 + 0x08, Register32
    RSVD1 = 0x480 + 0x0C, Register32
    ERSTBA1 = 0x480 + 0x10, Register64
    ERDP1 = 0x480 + 0x18, Register64

    IMAN2 = 0x4A0 + 0x00, R_XHCI_IMAN
    IMOD2 = 0x4A0 + 0x04, Register32
    ERSTSZ2 = 0x4A0 + 0x08, Register32
    RSVD0 = 0x4A0 + 0x0C, Register32
    ERSTBA2 = 0x4A0 + 0x10, Register64
    ERDP2 = 0x4A0 + 0x18, Register64

    IMAN3 = 0x4C0 + 0x00, R_XHCI_IMAN
    IMOD3 = 0x4C0 + 0x04, Register32
    ERSTSZ3 = 0x4C0 + 0x08, Register32
    RSVD0 = 0x4C0 + 0x0C, Register32
    ERSTBA3 = 0x4C0 + 0x10, Register64
    ERDP3 = 0x4C0 + 0x18, Register64

    DOORBELL = irange(0x4E0, 256, 4), R_XHCI_DOORBELL


class R_GUSB3PIPECTL(Register32):
    PHYSOFTRST = 31
    U2SSINP3OK = 29
    DISRXDETINP3 = 28
    UX_EXIT_PX = 27
    REQP1P2P3 = 24
    DEPOCHANGE = 18
    SUSPHY = 17
    LFPSFILT = 9
    RX_DETOPOLL = 8


class R_GUSB2PHYCFG(Register32):
    PHYSOFTRST = 31
    U2_FREECLK_EXISTS = 30
    SUSPHY = 6
    ULPI_UTMI = 4
    ENBLSLPM = 8


class R_GCTL(Register32):
    U2RSTECN = 16
    PRTCAP = 14, 12
    CORESOFTRESET = 11
    SOFITPSYNC = 10
    SCALEDOWN = 6, 4
    DISSCRAMBLE = 3
    U2EXIT_LFPS = 2
    GBLHIBERNATIONEN = 1
    DSBLCLKGTNG = 0


class Dwc3CoreRegs(RegMap):
    GSBUSCFG0 = 0x100, Register32
    GSBUSCFG1 = 0x104, Register32
    GTXTHRCFG = 0x108, Register32
    GRXTHRCFG = 0x10C, Register32
    GCTL = 0x110, R_GCTL
    GEVTEN = 0x114, Register32
    GSTS = 0x118, Register32
    GUCTL1 = 0x11C, Register32
    GSNPSID = 0x120, Register32
    GGPIO = 0x124, Register32
    GUID = 0x128, Register32
    GUCTL = 0x12C, Register32
    GBUSERRADDR0 = 0x130, Register32
    GBUSERRADDR1 = 0x134, Register32
    GPRTBIMAP0 = 0x138, Register32
    GPRTBIMAP1 = 0x13C, Register32
    GHWPARAMS0 = 0x140, Register32
    GHWPARAMS1 = 0x144, Register32
    GHWPARAMS2 = 0x148, Register32
    GHWPARAMS3 = 0x14C, Register32
    GHWPARAMS4 = 0x150, Register32
    GHWPARAMS5 = 0x154, Register32
    GHWPARAMS6 = 0x158, Register32
    GHWPARAMS7 = 0x15C, Register32
    GDBGFIFOSPACE = 0x160, Register32
    GDBGLTSSM = 0x164, Register32
    GDBGBMU = 0x16C, Register32
    GDBGLSPMUX = 0x170, Register32
    GDBGLSP = 0x174, Register32
    GDBGEPINFO0 = 0x178, Register32
    GDBGEPINFO1 = 0x17C, Register32
    GPRTBIMAP_HS0 = 0x180, Register32
    GPRTBIMAP_HS1 = 0x184, Register32
    GPRTBIMAP_FS0 = 0x188, Register32
    GPRTBIMAP_FS1 = 0x18C, Register32
    GUCTL2 = 0x19C, Register32
    GUSB2PHYCFG = 0x200, R_GUSB2PHYCFG
    GUSB2I2CCTL = 0x240, Register32
    GUSB2PHYACC = 0x280, Register32
    GUSB3PIPECTL = 0x2C0, R_GUSB3PIPECTL
    DWC3_GHWPARAMS8 = 0x600, Register32
    DWC3_GUCTL3 = 0x60C, Register32
    DWC3_GFLADJ = 0x630, Register32
    DWC3_GHWPARAMS9 = 0x680, Register32


class R_PIPEHANDLER_OVERRIDE(Register32):
    RXVALID = 0
    RXDETECT = 2


class E_PIPEHANDLER_MUX_MODE(IntEnum):
    USB3_PHY = 0
    DUMMY_PHY = 1
    UNK2 = 2


class E_PIPEHANDLER_CLK_SELECT(IntEnum):
    UNK0 = 0
    USB3_PHY = 1
    DUMMY_PHY = 2
    UNK4 = 4


class R_PIPEHANDLER_MUX_CTRL(Register32):
    MUX_MODE = 1, 0, E_PIPEHANDLER_MUX_MODE
    CLK_SELECT = 5, 3, E_PIPEHANDLER_CLK_SELECT


class R_PIPEHANDLER_LOCK(Register32):
    LOCK_EN = 0


class R_PIPEHANDLER_AON_GEN(Register32):
    DWC3_FORCE_CLAMP_EN = 4
    DWC3_RESET_N = 0


class R_PIPEHANDLER_NONSELECTED_OVERRIDE(Register32):
    NATIVE_POWER_DOWN = 3, 0
    NATIVE_RESET = 12
    DUMMY_PHY_EN = 15


class PipehandlerRegs(RegMap):
    PIPEHANDLER_OVERRIDE = 0x00, R_PIPEHANDLER_OVERRIDE
    PIPEHANDLER_OVERRIDE_VALUES = 0x04, R_PIPEHANDLER_OVERRIDE
    PIPEHANDLER_MUX_CTRL = 0x0C, R_PIPEHANDLER_MUX_CTRL
    PIPEHANDLER_LOCK_REQ = 0x10, R_PIPEHANDLER_LOCK
    PIPEHANDLER_LOCK_ACK = 0x14, R_PIPEHANDLER_LOCK
    PIPEHANDLER_AON_GEN = 0x1C, R_PIPEHANDLER_AON_GEN
    PIPEHANDLER_NONSELECTED_OVERRIDE = 0x20, R_PIPEHANDLER_NONSELECTED_OVERRIDE

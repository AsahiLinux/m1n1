# SPDX-License-Identifier: MIT
from ..utils import *
from enum import IntEnum
from .dart import DART, DARTRegs
import struct
from enum import IntEnum


class AES_OPCODE(IntEnum):
    # 0 triggers an invalid command interrupt
    SET_KEY = 1
    SET_IV = 2
    # 0x03 seems to take three additional argument, function unknown
    # 0x04 seems to take one additional argument, function unknown
    CRYPT = 5
    GET_IV = 6
    # 0x07 takes one additional argument, function unknown
    BARRIER = 8  # can be used to trigger an IRQ but possibly also does more
    # > 8 trigger an invalid command interrupt


class AES_SET_KEY_LEN(IntEnum):
    AES128 = 0
    AES192 = 1
    AES256 = 2


class AES_SET_KEY_BLOCK_MODE(IntEnum):
    ECB = 0
    CBC = 1
    CTR = 2


class AESCommandBase(Register32):
    OPCODE = 31, 28, AES_OPCODE


class AESHwKey(IntEnum):
    SOFTWARE = 0
    UID = 1  # unique key for each chip
    GID0 = 2  # (probably) globally unique key within a chip family
    GID1 = 3  # globally unique key within a chip family
    # 4-7 are probably empty / reserved for future use


class AESSetKeyCommand(AESCommandBase):
    OPCODE = 31, 28, Constant(AES_OPCODE.SET_KEY)
    SLOT = 27, 27
    KEY_SELECT = 26, 24
    KEYLEN = 23, 22, AES_SET_KEY_LEN
    # setting bit 21 breaks the engine and sets two bits in the IRQ status
    ENCRYPT = 20, 20
    KEYGEN = 19, 18
    BLOCK_MODE = 17, 16, AES_SET_KEY_BLOCK_MODE
    # 15, 0 doesn't seem to have any effect


class AESCryptCommand(AESCommandBase):
    OPCODE = 31, 28, Constant(AES_OPCODE.CRYPT)
    KEY_SLOT = 27, 27
    IV_SLOT = 26, 25
    LEN = 24, 0


class AESBarrierCommand(AESCommandBase):
    OPCODE = 31, 28, Constant(AES_OPCODE.BARRIER)
    IRQ = 27, 27


class AESGetIVCommand(AESCommandBase):
    OPCODE = 31, 28, Constant(AES_OPCODE.GET_IV)


class AESSetIVCommand(AESCommandBase):
    OPCODE = 31, 28, Constant(AES_OPCODE.SET_IV)
    SLOT = 27, 26


class AESIrqReg(Register32):
    KEY1_EMPTY = 17, 17
    KEY1_INVALID = 13, 13
    KEY0_EMPTY = 11, 11
    KEY0_INVALID = 7, 7
    FLAG = 5, 5
    UNKNOWN_COMMAND = 2, 2
    FIFO_OVERFLOW = 1, 1


class AESControlReg(Register32):
    START = 0, 0
    STOP = 1, 1
    CLEAR_FIFO = 2, 2
    # TOOD: not convinced about RESET anymore, I remember this un-broke the engine once but I can't reproduce that anymore
    RESET = 3, 3


class AESFifoStatusReg(Register32):
    FIFO_WRITE_PTR = 31, 24
    FIFO_READ_PTR = 23, 16
    FIFO_LEVEL = 15, 8
    FIFO_FULL = 2, 2
    FIFO_EMPTY = 1, 1


class AESRegs(RegMap):
    R_CONTROL = 0x08, AESControlReg
    R_IRQ_STATUS = 0x18, AESIrqReg
    R_IRQ_ENABLE = 0x1C, AESIrqReg
    R_FIFO_STATUS = 0x24, AESFifoStatusReg
    R_CMD_FIFO = 0x200, Register32

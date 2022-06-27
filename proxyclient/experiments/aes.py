# SPDX-License-Identifier: MIT
import sys, pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.setup import *
from m1n1.shell import run_shell
from m1n1.hw.dart import DART
from m1n1.hw.dart8110 import DART8110
from m1n1.hw.aes import *

def aes_set_custom_key(
    aes,
    key,
    encrypt=True,
    mode=AES_SET_KEY_BLOCK_MODE.CTR,
    keyslot=0,
    keygen=0,
):
    keylen = {
        16: AES_SET_KEY_LEN.AES128,
        24: AES_SET_KEY_LEN.AES192,
        32: AES_SET_KEY_LEN.AES256,
    }[len(key)]

    aes.R_CMD_FIFO = AESSetKeyCommand(
        KEY_SELECT=0,
        KEYLEN=keylen,
        ENCRYPT=1 if encrypt else 0,
        BLOCK_MODE=mode,
        SLOT=keyslot,
        KEYGEN=keygen,
    ).value

    for i in range(0, len(key), 4):
        aes.R_CMD_FIFO = struct.unpack(">I", key[i : i + 4])[0]


def aes_set_hw_key(
    aes,
    key,
    keylen=AES_SET_KEY_LEN.AES128,
    encrypt=True,
    mode=AES_SET_KEY_BLOCK_MODE.CTR,
    slot=0,
    keygen=0,
):
    aes.R_CMD_FIFO = AESSetKeyCommand(
        KEY_SELECT=key,
        KEYLEN=keylen,
        ENCRYPT=1 if encrypt else 0,
        BLOCK_MODE=mode,
        SLOT=slot,
        KEYGEN=keygen,
    ).value


def aes_set_iv(aes, iv, slot=0):
    assert len(iv) == 16
    aes.R_CMD_FIFO = AESSetIVCommand(SLOT=slot)

    for i in range(0, len(iv), 4):
        aes.R_CMD_FIFO = struct.unpack(">I", iv[i : i + 4])[0]


def aes_crypt(aes, dart, data, key_slot=0, iv_slot=0):
    assert len(data) % 16 == 0

    bfr = p.memalign(0x4000, len(data))
    iova = dart.iomap(1, bfr, len(data))
    dart.iowrite(1, iova, data)

    aes.R_CMD_FIFO = AESCryptCommand(LEN=len(data), KEY_SLOT=key_slot, IV_SLOT=iv_slot)
    aes.R_CMD_FIFO = 0  # actually upper bits of addr
    aes.R_CMD_FIFO = iova  # src
    aes.R_CMD_FIFO = iova  # dst

    aes.R_CMD_FIFO = AESBarrierCommand(IRQ=1).value
    time.sleep(0.1)
    # while aes.R_IRQ_STATUS.reg.FLAG != 1:
    #    pass
    # aes.dump_regs()
    aes.R_IRQ_STATUS = aes.R_IRQ_STATUS.val

    res = dart.ioread(1, iova, len(data))
    return res


def test_hw_key(key, keylen, keygen=0):
    aes.R_IRQ_STATUS = aes.R_IRQ_STATUS.val
    aes.R_CONTROL.set(CLEAR_FIFO=1)
    aes.R_CONTROL.set(RESET=1)
    aes.R_CONTROL.set(START=1)
    # aes.dump_regs()
    aes_set_hw_key(aes, key, keylen, slot=0, keygen=keygen)
    # print(aes.R_IRQ_STATUS)
    aes_set_iv(aes, b"\x00" * 16, slot=0)
    chexdump(aes_crypt(aes, dart, b"\x00" * 16, key_slot=0, iv_slot=1))
    # aes.dump_regs()
    aes.R_CONTROL.set(STOP=1)


def test_custom_key(key, keygen=0):
    aes.R_IRQ_STATUS = aes.R_IRQ_STATUS.val
    aes.R_CONTROL.set(CLEAR_FIFO=1)
    aes.R_CONTROL.set(RESET=1)
    aes.R_CONTROL.set(START=1)
    # aes.dump_regs()
    aes_set_custom_key(aes, key, keyslot=0, keygen=keygen)
    aes_set_iv(aes, b"\x00" * 16)
    aes_set_iv(aes, b"\x11" * 16, slot=1)
    chexdump(aes_crypt(aes, dart, b"\x00" * 16, key_slot=0, iv_slot=0))
    # aes.dump_regs()
    aes.R_CONTROL.set(STOP=1)


p.pmgr_adt_clocks_enable("/arm-io/aes")

dart_path = "/arm-io/dart-sio"

if u.adt[dart_path].compatible[0] == "dart,t8110":
    dart = DART8110.from_adt(u, dart_path)
else:
    dart = DART.from_adt(u, dart_path)

dart.initialize()

aes_base, _ = u.adt["/arm-io/aes"].get_reg(0)
aes = AESRegs(u, aes_base)
aes.dump_regs()

dart.dump_all()

for keygen in range(4):
    print(f"zero key, keygen={keygen}", end="")
    test_custom_key(b"\x00" * 16, keygen=keygen)

for keygen in range(4):
    print("#" * 10)
    for keylen in [
        AES_SET_KEY_LEN.AES128,
        AES_SET_KEY_LEN.AES192,
        AES_SET_KEY_LEN.AES256,
    ]:
        for i in (1, 3):
            print(f"key = {i}, keylen={keylen}, keygen={keygen}", end="")
            test_hw_key(i, keylen, keygen=keygen)

dart.dump_all()

run_shell(globals(), msg="Have fun!")

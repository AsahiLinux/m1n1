# SPDX-License-Identifier: MIT
from ...utils import *
from contextlib import contextmanager

PPL_MAGIC = 0x4b1d000000000002

class GFXHandoffStruct(RegMap):
    MAGIC_AP    = 0x0, Register64
    MAGIC_FW    = 0x8, Register64

    LOCK_AP     = 0x10, Register8
    LOCK_FW     = 0x11, Register8
    TURN        = 0x14, Register32

    CUR_CTX     = 0x18, Register32

    FLUSH_STATE = irange(0x20, 0x41, 0x18), Register64
    FLUSH_ADDR  = irange(0x28, 0x41, 0x18), Register64
    FLUSH_SIZE  = irange(0x30, 0x41, 0x18), Register64

    UNK2        = 0x638, Register8
    UNK3        = 0x640, Register64

class GFXHandoff:
    def __init__(self, u):
        self.u = u
        self.sgx_dev = self.u.adt["/arm-io/sgx"]
        self.base = self.sgx_dev.gfx_handoff_base
        self.reg = GFXHandoffStruct(u, self.base)
        self.is_locked = False
        self.initialized = False

    @contextmanager
    def lock(self):
        """Dekker's algorithm lock"""
        assert not self.is_locked

        # Note: This *absolutely* needs barriers everywhere.
        # Those are implicit in proxyclient for every operation.

        self.reg.LOCK_AP.val = 1
        while self.reg.LOCK_FW.val != 0:
            if self.reg.TURN != 0:
                self.reg.LOCK_AP = 0
                while self.reg.TURN != 0:
                    pass
                self.reg.LOCK_AP = 1

        self.is_locked = True
        try:
            yield
        finally:
            self.reg.TURN.val = 1
            self.reg.LOCK_AP.val = 0
            self.is_locked = False

    def initialize(self):
        if self.initialized:
            return

        print("[Handoff] Initializing...")

        self.reg.MAGIC_AP.val = PPL_MAGIC
        self.reg.UNK = 0xffffffff
        self.reg.UNK3 = 0

        with self.lock():
            print("[Handoff] Waiting for FW PPL init...")
            while self.reg.MAGIC_FW.val != PPL_MAGIC:
                pass

        for i in range(0x41):
            self.reg.FLUSH_STATE[i].val = 0
            self.reg.FLUSH_ADDR[i].val = 0
            self.reg.FLUSH_SIZE[i].val = 0

        self.initialized = True
        print("[Handoff] Initialized!")

    # The order here is:
    # - Remap memory as shared
    # - TLBI
    # - prepare_cacheflush()
    # - issue FWCtl request
    # - wait for completion (ring or wait_cacheflush?)
    # - Unmap memory
    # - TLBI
    # - complete_cacheflush()
    def prepare_cacheflush(self, base, size, context=0x40):
        assert self.reg.FLUSH_STATE[context].val == 0

        self.reg.FLUSH_ADDR[context].val = base
        self.reg.FLUSH_SIZE[context].val = size
        self.reg.FLUSH_STATE[context].val = 1

    def wait_cacheflush(self, context=0x40):
        while self.reg.FLUSH_STATE[context].val == 1:
            pass

    def complete_cacheflush(self, context=0x40):
        assert self.reg.FLUSH_STATE[context].val == 2
        self.reg.FLUSH_STATE[context].val = 0

    # probably not necessary?
    # order is:
    # - Remap memory as shared
    # - (no TLBI?)
    # - prepare_unmap()
    # - unmap
    # - TLBI
    # - complete_unmap()
    def prepare_unmap(self, base, size, context):
        assert self.reg.FLUSH_STATE[context].val == 0
        self.reg.FLUSH_ADDR[context].val = 0xdead000000000000 | (base & 0xffffffffffff)
        self.reg.FLUSH_SIZE[context].val = size
        self.reg.FLUSH_STATE[context].val = 2

    def complete_unmap(self, context):
        assert self.reg.FLUSH_STATE[context].val == 2
        self.reg.FLUSH_STATE[context].val = 0

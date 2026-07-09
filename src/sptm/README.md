# SPTM Emulator

This directory is tainted bringup code. Keep reverse-engineered SPTM endpoint
behavior here while the generic hypervisor and loader plumbing stay separate.

The emulator is linked into the streamed stage2 image when `SPTM_EMUL=1`; the
stage1 boot object does not include it.

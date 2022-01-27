#[inline]
pub unsafe fn write32(addr: u64, data: u32) {
    unsafe { core::ptr::write_volatile(addr as *mut _, data) };
}

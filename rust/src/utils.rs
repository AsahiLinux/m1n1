macro_rules! gen_write {
    ($name:tt, $size:tt) => {
        #[inline]
        pub unsafe fn $name(addr: u64, data: $size) {
            unsafe { core::ptr::write_volatile(addr as *mut _, data) };
        }
    };
}

gen_write!(write64, u64);
gen_write!(write32, u32);
gen_write!(write16, u16);
gen_write!(write8, u8);

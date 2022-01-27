use core::ffi::c_void;
use core::ptr::null_mut;

extern "C" {
    static mut adt: *mut c_void;

    fn adt_path_offset_trace(adt: *const c_void, path: *const i8, offsets: *mut i32) -> isize;
    fn adt_get_reg(
        adt: *const c_void,
        path: *const i32,
        prop: *const i8,
        idx: isize,
        addr: *mut u64,
        size: *mut u64,
    ) -> isize;
}

#[repr(C)]
pub struct Adt {
    name: [i8; 32],
    size: u32,
    value: *mut u8,
}

impl Adt {
    pub unsafe fn get_default() -> &'static mut Self {
        unsafe { core::mem::transmute(adt) }
    }

    pub fn get_reg(
        &self,
        path: &[i32],
        prop: &[u8],
        idx: isize,
        addr: &mut u64,
        size: Option<&mut u64>,
    ) -> isize {
        let size = if let Some(size) = size {
            size as *mut u64
        } else {
            null_mut()
        };

        unsafe {
            adt_get_reg(
                self.as_ptr(),
                path.as_ptr(),
                prop.as_ptr() as *const i8,
                idx,
                addr as *mut u64,
                size,
            )
        }
    }

    // TODO: return error with some sort of Error type
    pub fn path_offset_trace(&self, path: &[u8], offsets: &mut [i32]) -> isize {
        unsafe {
            adt_path_offset_trace(
                self.as_ptr(),
                path.as_ptr() as *const i8,
                offsets.as_mut_ptr(),
            )
        }
    }

    pub fn get_reg_addr(&self, path: &[i32], prop: &[u8], idx: isize) -> Result<u64, ()> {
        let mut addr = 0;

        let ret = self.get_reg(path, prop, idx, &mut addr, None);
        if ret < 0 {
            return Err(());
        }

        Ok(addr)
    }

    pub fn as_ptr(&self) -> *const c_void {
        self as *const _ as *const c_void
    }

    pub fn as_mut_ptr(&mut self) -> *mut c_void {
        self as *mut _ as *mut c_void
    }
}

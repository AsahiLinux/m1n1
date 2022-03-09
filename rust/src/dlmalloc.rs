// SPDX-License-Identifier: MIT

use core::alloc::{GlobalAlloc, Layout};
use core::ffi::c_void;
use core::ptr;
use cty::*;

extern "C" {
    pub fn malloc(size: size_t) -> *mut c_void;
    pub fn realloc(p: *mut c_void, size: size_t) -> *mut c_void;
    pub fn free(p: *mut c_void);
    pub fn posix_memalign(p: *mut *mut c_void, alignment: size_t, size: size_t) -> c_int;
}

pub struct DLMalloc;

unsafe impl GlobalAlloc for DLMalloc {
    #[inline]
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let mut ptr = ptr::null_mut();
        let ret = unsafe {
            posix_memalign(
                &mut ptr,
                layout.align().max(core::mem::size_of::<usize>()),
                layout.size(),
            )
        };
        if ret == 0 {
            ptr as *mut u8
        } else {
            ptr::null_mut()
        }
    }

    #[inline]
    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        // Unfortunately, calloc doesn't make any alignment guarantees, so the memory
        // has to be manually zeroed-out.
        let ptr = unsafe { self.alloc(layout) };
        if !ptr.is_null() {
            unsafe { ptr::write_bytes(ptr, 0, layout.size()) };
        }
        ptr
    }

    #[inline]
    unsafe fn dealloc(&self, ptr: *mut u8, _layout: Layout) {
        unsafe {
            free(ptr as *mut c_void);
        }
    }

    #[inline]
    unsafe fn realloc(&self, ptr: *mut u8, _layout: Layout, new_size: usize) -> *mut u8 {
        unsafe { realloc(ptr as *mut c_void, new_size) as *mut u8 }
    }
}

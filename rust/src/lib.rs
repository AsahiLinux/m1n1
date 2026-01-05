// SPDX-License-Identifier: MIT
#![cfg_attr(not(test), no_std)]
#![deny(unsafe_op_in_unsafe_fn)]
#![feature(cfg_version)]
#![feature(alloc_error_handler)]
#![cfg_attr(not(version("1.82")), feature(new_uninit))]
#![feature(stmt_expr_attributes)]
#![cfg_attr(all(version("1.82"), not(version("1.92"))), feature(new_zeroed_alloc))]

#[macro_use]
extern crate alloc;

pub mod adt;
pub mod chainload;
pub mod dlmalloc;
pub mod float;
pub mod gpt;
pub mod gpu;
pub mod nvme;
pub mod print;

#[cfg(not(test))]
use crate::dlmalloc::DLMalloc;

// This is unstable in core::ffi, let's just declare it ourselves
#[allow(non_camel_case_types)]
type c_size_t = usize;

#[cfg(not(test))]
#[global_allocator]
static GLOBAL: DLMalloc = dlmalloc::DLMalloc;

extern "C" {
    fn flush_and_reboot();
}

#[cfg(not(test))]
#[panic_handler]
fn panic(info: &::core::panic::PanicInfo) -> ! {
    println!("{}", info);
    unsafe { flush_and_reboot() };
    loop {}
}

#[cfg(not(test))]
#[alloc_error_handler]
fn alloc_error(layout: core::alloc::Layout) -> ! {
    panic!("memory allocation of {} bytes failed", layout.size())
}

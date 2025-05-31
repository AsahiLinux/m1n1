// SPDX-License-Identifier: MIT
#![no_std]
#![deny(unsafe_op_in_unsafe_fn)]
#![feature(cfg_version)]
#![feature(alloc_error_handler)]
#![feature(new_uninit)]
#![cfg_attr(version("1.82"), feature(new_zeroed_alloc))]

#[macro_use]
extern crate alloc;

pub mod adt;
pub mod chainload;
pub mod dlmalloc;
pub mod gpt;
pub mod nvme;
pub mod print;

use crate::dlmalloc::DLMalloc;

// This is unstable in core::ffi, let's just declare it ourselves
#[allow(non_camel_case_types)]
type c_size_t = usize;

#[global_allocator]
static GLOBAL: DLMalloc = dlmalloc::DLMalloc;

extern "C" {
    fn flush_and_reboot();
}

#[panic_handler]
fn panic(info: &::core::panic::PanicInfo) -> ! {
    println!("{}", info);
    unsafe { flush_and_reboot() };
    loop {}
}

#[alloc_error_handler]
fn alloc_error(layout: core::alloc::Layout) -> ! {
    panic!("memory allocation of {} bytes failed", layout.size())
}

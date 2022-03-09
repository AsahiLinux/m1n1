// SPDX-License-Identifier: MIT
#![no_std]
#![deny(unsafe_op_in_unsafe_fn)]
#![feature(alloc_error_handler)]
#![feature(mixed_integer_ops)]
#![feature(new_uninit)]

#[macro_use]
extern crate alloc;

pub mod chainload;
pub mod dlmalloc;
pub mod gpt;
pub mod nvme;
pub mod print;

use crate::dlmalloc::DLMalloc;

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

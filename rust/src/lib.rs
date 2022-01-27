#![no_std]
#![deny(unsafe_op_in_unsafe_fn)]

pub mod adt;
pub mod print;
pub mod utils;
pub mod wdt;

#[panic_handler]
fn panic(_: &::core::panic::PanicInfo) -> ! {
    unsafe { wdt::wdt_reboot() };
    loop {}
}

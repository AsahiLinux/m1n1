#![no_std]
#![deny(unsafe_op_in_unsafe_fn)]

pub mod adt;
pub mod print;
pub mod utils;
pub mod wdt;

#[panic_handler]
fn panic(info: &::core::panic::PanicInfo) -> ! {
    println!("{}", info);
    unsafe { wdt::wdt_reboot() };
    loop {}
}

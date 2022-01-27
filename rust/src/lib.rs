#![no_std]

pub mod adt;
pub mod utils;
pub mod wdt;

#[panic_handler]
fn panic(_: &::core::panic::PanicInfo) -> ! {
    unsafe { wdt::wdt_reboot() };
    loop {}
}

use crate::adt::Adt;
use crate::println;
use crate::utils::write32;
use core::num::NonZeroU64;

const WDT_COUNT: u64 = 0x10;
const WDT_ALARM: u64 = 0x14;
const WDT_CTL: u64 = 0x1c;

static mut WDT_ADDR: Option<NonZeroU64> = None;

#[no_mangle]
pub unsafe extern "C" fn wdt_disable() {
    let mut path = [0isize; 8];
    let adt = unsafe { Adt::get_default() };
    let node = adt.path_offset_trace(b"/arm-io/wdt", &mut path);
    if node < 0 {
        println!("WDT node not found!");
        return;
    }

    let addr = adt.get_reg_addr(&path, b"reg", 0);
    if addr.is_err() {
        println!("Failed to get WDT reg property!");
        return;
    }
    let addr = addr.unwrap();
    unsafe { WDT_ADDR = NonZeroU64::new(addr) };

    println!("WDT registers @ {:#02x?}", addr);

    unsafe { write32(addr + WDT_CTL, 0) };

    println!("WDT disabled\n");
}

#[no_mangle]
pub unsafe extern "C" fn wdt_reboot() {
    let wdt_base = unsafe { WDT_ADDR };

    if let Some(wdt_base) = wdt_base {
        let wdt_base = wdt_base.get();
        unsafe {
            write32(wdt_base + WDT_ALARM, 0x100000);
            write32(wdt_base + WDT_COUNT, 0);
            write32(wdt_base + WDT_CTL, 4);
        }
    }
}

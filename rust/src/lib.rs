#![no_std]
#![deny(unsafe_op_in_unsafe_fn)]

pub mod adt;
pub mod print;
pub mod utils;
pub mod wdt;
pub mod nvme;
pub mod gpt;

use nvme::NvmeBlockDevice;
use fat32::volume::Volume;
use ed25519_dalek::{Signature, PublicKey};

const MINI_PUBLIC_KEY: [u8; 32] = [253,193,94,124,18,80,246,35,42,67,3,45,86,30,97,16,136,22,37,164,55,44,70,107,52,170,174,57,239,50,216,38];

#[panic_handler]
fn panic(info: &::core::panic::PanicInfo) -> ! {
    println!("{}", info);
    unsafe { wdt::wdt_reboot() };
    loop {}
}

#[no_mangle]
extern "C" fn prepare_chainload() -> usize {
    let disk = NvmeBlockDevice::new(1);
    let esp = match gpt::find_and_open_esp(disk) {
        Err(_) => return 0,
        Ok(esp) => esp
    };
    let volume = Volume::new(esp);
    let root = volume.root_dir();
    let file = match root.open_file("m1n1.bin") {
        Err(_) => return 0,
        Ok(file) => file
    };
    file.length()
}

#[no_mangle]
extern "C" fn chainload_get_bytes(ptr: *mut u8, size: usize) -> bool {
    //SAFETY: We trust the C code to pass it in correctly
    let mut buf = unsafe {
        core::slice::from_raw_parts_mut(ptr, size)
    };
    let disk = NvmeBlockDevice::new(1);
    let esp = match gpt::find_and_open_esp(disk) {
        Err(_) => return false,
        Ok(esp) => esp
    };
    let volume = Volume::new(esp);
    let root = volume.root_dir();
    let exe_file = match root.open_file("m1n1.bin") {
        Err(_) => return false,
        Ok(file) => file
    };
    let sig_file = match root.open_file("m1n1.sig") {
        Err(_) => return false,
        Ok(file) => file
    };
    let size = match exe_file.read(&mut buf) {
        Err(_) => return false,
        Ok(size) => size
    };
    let buf = &buf[0..size];
    let mut sig_bytes = [0u8; 64];
    let sig_size = match sig_file.read(&mut sig_bytes) {
        Err(_) => return false,
        Ok(size) => size
    };
    if sig_size != ed25519_dalek::SIGNATURE_LENGTH {
        return false
    }
    let sig = Signature::from_bytes(&sig_bytes).unwrap();
    PublicKey::from_bytes(&MINI_PUBLIC_KEY).unwrap().verify_strict(&buf, &sig).is_ok()
}

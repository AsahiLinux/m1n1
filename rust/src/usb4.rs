// SPDX-License-Identifier: MIT

use crate::adt::{ADTNode, AdtError};
// use crate::println;
use sha1_smol::Sha1;

const PLATFORM_UUID_SALT: [u8; 16] = [
    0xa6, 0xdd, 0x4c, 0xcb, 0xb5, 0xe8, 0x4a, 0xf5, 0xac, 0xdd, 0xb6, 0xdc, 0x6a, 0x05, 0x42, 0xb8,
];

const DROM_UUID_SALT: [u8; 16] = [
    0x06, 0xbf, 0x07, 0x64, 0x05, 0x78, 0x4a, 0xaa, 0x85, 0xb4, 0x79, 0x08, 0x34, 0x8e, 0xe3, 0x43,
];

fn usb4_router_uuid() -> Result<u64, AdtError> {
    let node = ADTNode::from_path("/chosen")?;
    let unique_chip_id = node.named_prop("unique-chip-id")?.u64()?;
    let chip_id = node.named_prop("chip-id")?.u32()?;

    let mut hasher = Sha1::new();
    hasher.update(&PLATFORM_UUID_SALT);
    hasher.update(&unique_chip_id.to_le_bytes());
    hasher.update(&chip_id.to_le_bytes());

    let digest = hasher.digest();

    let mut uuid: [u8; 16] = digest.bytes()[0..16].try_into().unwrap();

    uuid[6] = 0x50 | (uuid[6] & 0xf);
    uuid[8] = 0x80 | (uuid[8] & 0x3f);

    // println!(
    //     "IOPlatformUUID: \
    //     {:02x}{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}{:02x} \
    //     {:02x}{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}",
    //     uuid[0],
    //     uuid[1],
    //     uuid[2],
    //     uuid[3],
    //     uuid[4],
    //     uuid[5],
    //     uuid[6],
    //     uuid[7],
    //     uuid[8],
    //     uuid[9],
    //     uuid[10],
    //     uuid[11],
    //     uuid[12],
    //     uuid[13],
    //     uuid[14],
    //     uuid[15]
    // );

    let mut drom_sha1 = Sha1::new();
    drom_sha1.update(&uuid);
    drom_sha1.update(&DROM_UUID_SALT);

    let drom_digest = drom_sha1.digest();
    let drom_bytes: [u8; 8] = drom_digest.bytes()[0..8].try_into().unwrap();

    let mut drom_uuid: u64 = u64::from_le_bytes(drom_bytes);

    drom_uuid = (drom_uuid & 0xffff_ffff_fff0u64) | (0x05ac << 48);
    // println!("USB4 router UUID: {:#08x}", drom_uuid);

    Ok(drom_uuid)
}

#[no_mangle]
pub unsafe extern "C" fn rust_usb4_router_uuid() -> u64 {
    match usb4_router_uuid() {
        Ok(uuid) => uuid,
        Err(_) => 0,
    }
}

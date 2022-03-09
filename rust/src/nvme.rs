// SPDX-License-Identifier: MIT
use crate::println;
use alloc::boxed::Box;
use core::cmp::min;
use core::ffi::c_void;
use fatfs::SeekFrom;

extern "C" {
    fn nvme_read(nsid: u32, lba: u64, buffer: *mut c_void) -> bool;
}

const SECTOR_SIZE: usize = 4096;

pub type Error = ();

#[repr(C, align(4096))]
struct SectorBuffer([u8; SECTOR_SIZE]);

fn alloc_sector_buf() -> Box<SectorBuffer> {
    let p: Box<SectorBuffer> = unsafe { Box::new_zeroed().assume_init() };
    debug_assert_eq!(0, p.0.as_ptr().align_offset(4096));
    p
}

pub struct NVMEStorage {
    nsid: u32,
    offset: u64,
    lba: Option<u64>,
    buf: Box<SectorBuffer>,
    pos: u64,
}

impl NVMEStorage {
    pub fn new(nsid: u32, offset: u64) -> NVMEStorage {
        NVMEStorage {
            nsid: nsid,
            offset: offset,
            lba: None,
            buf: alloc_sector_buf(),
            pos: 0,
        }
    }
}

impl fatfs::IoBase for NVMEStorage {
    type Error = Error;
}

impl fatfs::Read for NVMEStorage {
    fn read(&mut self, mut buf: &mut [u8]) -> Result<usize, Self::Error> {
        let mut read = 0;

        while !buf.is_empty() {
            let lba = self.pos / SECTOR_SIZE as u64;
            let off = self.pos as usize % SECTOR_SIZE;

            if Some(lba) != self.lba {
                self.lba = Some(lba);
                let lba = lba + self.offset;
                if !unsafe { nvme_read(self.nsid, lba, self.buf.0.as_mut_ptr() as *mut c_void) } {
                    println!("nvme_read({}, {}) failed", self.nsid, lba);
                    return Err(());
                }
            }
            let copy_len = min(SECTOR_SIZE - off, buf.len());
            buf[..copy_len].copy_from_slice(&self.buf.0[off..off + copy_len]);
            buf = &mut buf[copy_len..];
            read += copy_len;
            self.pos += copy_len as u64;
        }
        Ok(read)
    }
}

impl fatfs::Write for NVMEStorage {
    fn write(&mut self, _buf: &[u8]) -> Result<usize, Self::Error> {
        Err(())
    }
    fn flush(&mut self) -> Result<(), Self::Error> {
        Err(())
    }
}

impl fatfs::Seek for NVMEStorage {
    fn seek(&mut self, from: SeekFrom) -> Result<u64, Self::Error> {
        self.pos = match from {
            SeekFrom::Start(n) => n,
            SeekFrom::End(_n) => panic!("SeekFrom::End not supported"),
            SeekFrom::Current(n) => self.pos.checked_add_signed(n).ok_or(())?,
        };
        Ok(self.pos)
    }
}

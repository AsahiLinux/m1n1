// SPDX-License-Identifier: MIT

use crate::println;
use core::convert::TryInto;
use core::result::Result;
use fatfs::{Read, Seek};
use uuid::Uuid;

const EFI_SIGNATURE: u64 = 0x5452415020494645;

const SECTOR_SIZE: usize = 4096;

#[derive(Debug)]
pub enum Error<T> {
    Io(T),
    InvalidGPTHeader,
}

impl<T> From<T> for Error<T> {
    fn from(err: T) -> Error<T> {
        Error::Io(err)
    }
}

struct TableHeader {
    bytes: [u8; Self::SIZE],
    my_lba: u64,
}

impl TableHeader {
    const SIZE: usize = 0x5C;

    fn read<R: Read + Seek>(rdr: &mut R, lba: u64) -> Result<Self, Error<R::Error>> {
        let mut hdr = Self {
            bytes: [0; Self::SIZE],
            my_lba: lba,
        };
        let off = SECTOR_SIZE * (lba as usize);
        rdr.seek(fatfs::SeekFrom::Start(off as u64))?;
        rdr.read_exact(&mut hdr.bytes)?;
        match hdr.is_valid() {
            true => Ok(hdr),
            false => Err(Error::InvalidGPTHeader),
        }
    }

    fn get_signature(&self) -> u64 {
        u64::from_le_bytes(self.bytes[0..8].try_into().unwrap())
    }
    fn get_my_lba(&self) -> u64 {
        u64::from_le_bytes(self.bytes[24..32].try_into().unwrap())
    }
    fn get_partition_entry_lba(&self) -> u64 {
        u64::from_le_bytes(self.bytes[72..80].try_into().unwrap())
    }
    fn get_partition_entry_count(&self) -> usize {
        u32::from_le_bytes(self.bytes[80..84].try_into().unwrap()) as usize
    }
    fn get_partition_entry_size(&self) -> usize {
        u32::from_le_bytes(self.bytes[84..88].try_into().unwrap()) as usize
    }
    fn is_valid(&self) -> bool {
        self.get_signature() == EFI_SIGNATURE && self.get_my_lba() == self.my_lba
    }
}

pub struct PartitionEntry {
    bytes: [u8; Self::SIZE],
}

impl PartitionEntry {
    const SIZE: usize = 0x80;

    fn read<R: Read + Seek>(rdr: &mut R, off: usize) -> Result<Self, Error<R::Error>> {
        let mut part = Self {
            bytes: [0; Self::SIZE],
        };
        rdr.seek(fatfs::SeekFrom::Start(off as u64))?;
        rdr.read_exact(&mut part.bytes)?;
        Ok(part)
    }

    #[allow(dead_code)]
    pub fn get_type_guid(&self) -> Uuid {
        Uuid::from_bytes_le(self.bytes[0..16].try_into().unwrap())
    }
    pub fn get_partition_guid(&self) -> Uuid {
        Uuid::from_bytes_le(self.bytes[16..32].try_into().unwrap())
    }
    pub fn get_starting_lba(&self) -> u64 {
        u64::from_le_bytes(self.bytes[32..40].try_into().unwrap())
    }
    pub fn get_ending_lba(&self) -> u64 {
        u64::from_le_bytes(self.bytes[40..48].try_into().unwrap())
    }
    pub fn get_attributes(&self) -> u64 {
        u64::from_le_bytes(self.bytes[48..56].try_into().unwrap())
    }
    pub fn get_name(&self) -> &[u8] {
        &self.bytes[56..72]
    }
}

pub struct GPT<T: fatfs::ReadWriteSeek> {
    disk: T,
    hdr: TableHeader,
}

impl<IO: fatfs::ReadWriteSeek> GPT<IO> {
    pub fn new<T: fatfs::IntoStorage<IO>>(storage: T) -> Result<Self, Error<IO::Error>> {
        let mut disk = storage.into_storage();

        let hdr = TableHeader::read(&mut disk, 1)?;

        let gpt = Self { disk, hdr };
        Ok(gpt)
    }

    pub fn count(&self) -> usize {
        self.hdr.get_partition_entry_count()
    }

    pub fn index(&mut self, index: usize) -> Result<PartitionEntry, Error<IO::Error>> {
        let off = (self.hdr.get_partition_entry_lba() as usize * SECTOR_SIZE)
            + index * self.hdr.get_partition_entry_size();
        PartitionEntry::read(&mut self.disk, off)
    }

    pub fn find_by_partuuid(
        &mut self,
        uuid: Uuid,
    ) -> Result<Option<PartitionEntry>, Error<IO::Error>> {
        for i in 0..self.count() {
            let part = self.index(i)?;
            if part.get_type_guid().is_nil() {
                continue;
            }
            if part.get_partition_guid() == uuid {
                return Ok(Some(part));
            }
        }
        Ok(None)
    }

    pub fn dump(&mut self) {
        for i in 0..self.count() {
            let part = self.index(i).unwrap();
            let guid = part.get_type_guid();
            if guid.is_nil() {
                continue;
            }
            println!(
                "{}: {}..{} {:x} {:x}",
                i,
                part.get_starting_lba(),
                part.get_ending_lba(),
                guid,
                part.get_partition_guid()
            );
        }
    }
}

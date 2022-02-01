use core::convert::TryInto;
use core::result::Result;

use block_device::BlockDevice;

const EFI_SIGNATURE: u64 = 0x5452415020494645;
const ESP_GUID: u128 = 0x3bc93ec9a0004bba11d2f81fc12a7328;
const SECTOR_SIZE: usize = 4096;

struct TableHeader<'a> {
    bytes: &'a [u8]
}

impl TableHeader<'_> {
    fn new<'a>(bytes: &'a [u8]) -> TableHeader<'a> {
        TableHeader {
            bytes
        }
    }
    fn get_signature(&self) -> u64 {
        u64::from_le_bytes(self.bytes[0..8].try_into().unwrap())
    }
    #[allow(dead_code)]
    fn get_revision(&self) -> u32 {
        u32::from_le_bytes(self.bytes[8..12].try_into().unwrap())
    }
    fn get_size(&self) -> u32 {
        u32::from_le_bytes(self.bytes[12..16].try_into().unwrap())
    }
    fn get_crc(&self) -> u32 {
        u32::from_le_bytes(self.bytes[16..20].try_into().unwrap())
    }
    fn get_my_lba(&self) -> u64 {
        u64::from_le_bytes(self.bytes[24..32].try_into().unwrap())
    }
    #[allow(dead_code)]
    fn get_alternate_lba(&self) -> u64 {
        u64::from_le_bytes(self.bytes[32..40].try_into().unwrap())
    }
    #[allow(dead_code)]
    fn get_first_usable_lba(&self) -> u64 {
        u64::from_le_bytes(self.bytes[40..48].try_into().unwrap())
    }
    #[allow(dead_code)]
    fn get_last_usable_lba(&self) -> u64 {
        u64::from_le_bytes(self.bytes[48..56].try_into().unwrap())
    }
    #[allow(dead_code)]
    fn get_disk_guid(&self) -> u128 {
        u128::from_le_bytes(self.bytes[56..72].try_into().unwrap())
    }
    fn get_partition_entry_lba(&self) -> u64 {
        u64::from_le_bytes(self.bytes[72..80].try_into().unwrap())
    }
    fn get_number_partition_entries(&self) -> u32 {
        u32::from_le_bytes(self.bytes[80..84].try_into().unwrap())
    }
    fn get_partition_entry_size(&self) -> u32 {
        u32::from_le_bytes(self.bytes[84..88].try_into().unwrap())
    }
    fn get_partition_array_crc(&self) -> u32 {
        u32::from_le_bytes(self.bytes[88..92].try_into().unwrap())
    }
    fn calculate_crc(&self) -> u32 {
        let mut state = 0xFFFFFFFF;
        state = crc32_update_buf(state, &self.bytes[0..16]);
        state = crc32_update_buf(state, &[0u8; 4]);
        state = crc32_update_buf(state, &self.bytes[20..self.get_size() as usize]);
        return state ^ 0xFFFFFFFF;
    }
    fn is_valid(&self, my_lba: u64) -> bool {
        self.get_signature() == EFI_SIGNATURE &&
            self.calculate_crc() == self.get_crc() &&
            self.get_my_lba() == my_lba
    }
}

struct PartitionEntry<'a> {
    bytes: &'a [u8]
}

impl PartitionEntry<'_> {
    fn new<'a>(bytes: &'a [u8]) -> PartitionEntry<'a> {
        PartitionEntry {
            bytes
        }
    }
    fn get_type_guid(&self) -> u128 {
        u128::from_le_bytes(self.bytes[0..16].try_into().unwrap())
    }
    #[allow(dead_code)]
    fn get_parition_guid(&self) -> u128 {
        u128::from_le_bytes(self.bytes[16..32].try_into().unwrap())
    }
    fn get_starting_lba(&self) -> u64 {
        u64::from_le_bytes(self.bytes[32..40].try_into().unwrap())
    }
    fn get_ending_lba(&self) -> u64 {
        u64::from_le_bytes(self.bytes[40..48].try_into().unwrap())
    }
    #[allow(dead_code)]
    fn get_attributes(&self) -> u64 {
        u64::from_le_bytes(self.bytes[48..56].try_into().unwrap())
    }
    #[allow(dead_code)]
    fn get_name(&self) -> &[u8] {
        &self.bytes[56..72]
    }
}

#[derive(Debug)]
pub enum EspSearchError {
    NvmeReadError,
    PartitionTableCorrupted,
    NoESP
}


fn find_esp_lba<T: BlockDevice>(disk: &T) -> Result<(u64, u64), EspSearchError> {
    let mut hdr_buf = [0u8; SECTOR_SIZE];
    disk.read(&mut hdr_buf, SECTOR_SIZE, 1).or(Err(EspSearchError::NvmeReadError))?;
    let pt = TableHeader::new(&hdr_buf);
    if !pt.is_valid(1) {
        return Err(EspSearchError::PartitionTableCorrupted);
    }
    let mut entry_buf = [0u8; SECTOR_SIZE];
    let start_lba = pt.get_partition_entry_lba() as usize;
    let mut crc = 0xFFFFFFFF;
    let full_lbas = (pt.get_partition_entry_size() * pt.get_number_partition_entries()) as usize / SECTOR_SIZE;
    for lba in start_lba..(start_lba + full_lbas) {
        disk.read(&mut entry_buf, lba * SECTOR_SIZE, 1).or(Err(EspSearchError::NvmeReadError))?;
        crc = crc32_update_buf(crc, &entry_buf)
    }
    let remainder = (pt.get_partition_entry_size() * pt.get_number_partition_entries()) as usize % SECTOR_SIZE;
    if remainder != 0 {
        disk.read(&mut entry_buf, (start_lba + full_lbas) * SECTOR_SIZE, 1).or(Err(EspSearchError::NvmeReadError))?;
        crc = crc32_update_buf(crc, &entry_buf[..remainder]);
    }
    if pt.get_partition_array_crc() != (crc ^ 0xFFFFFFFF) {
        return Err(EspSearchError::PartitionTableCorrupted);
    }
    let mut cur_lba = 0xFFFFFFFFFFFFFFFF;
    for i in 0..pt.get_number_partition_entries() {
        let containing_lba = start_lba + (i * pt.get_partition_entry_size()) as usize / SECTOR_SIZE;
        if containing_lba != cur_lba {
            disk.read(&mut entry_buf, containing_lba * SECTOR_SIZE, 1).or(Err(EspSearchError::NvmeReadError))?;
            cur_lba = containing_lba;
        }
        let offset = ((i * pt.get_partition_entry_size()) % SECTOR_SIZE as u32) as usize;
        // Spec says entry size is a power of two, so they should not cross lbas
        let entry = PartitionEntry::new(&entry_buf[offset..offset + pt.get_partition_entry_size() as usize]);
        if entry.get_type_guid() == ESP_GUID {
            return Ok((entry.get_starting_lba(), entry.get_ending_lba()));
        }
    }
    return Err(EspSearchError::NoESP)
}

fn crc32_update(mut state: u32, byte: u8) -> u32 {
    state = state ^ byte as u32;
    for _ in 0..8 {
        let mask = -((state & 1) as i32) as u32;
        state = (state >> 1) ^ (0xEDB88320 & mask);
    }
    return state;
}

fn crc32_update_buf(mut state: u32, buf: &[u8]) -> u32 {
    for byte in buf {
        state = crc32_update(state, *byte);
    }
    return state;
}

#[derive(Clone, Copy)]
pub struct SliceBlockDevice<T> {
    first: usize,
    last: usize,
    inner: T
}

impl<T> BlockDevice for SliceBlockDevice<T> where T: BlockDevice {
    type Error = T::Error;
    fn write(&self, buf: &[u8], address: usize, number_of_blocks: usize) -> Result<(), Self::Error> {
        if address + (number_of_blocks + self.first) * SECTOR_SIZE > self.last * SECTOR_SIZE {
            panic!("Attempt to write out of bounds");
        }
        self.inner.write(buf, address + self.first * SECTOR_SIZE, number_of_blocks)
    }
    fn read(&self, buf: &mut [u8], address: usize, number_of_blocks: usize) -> Result<(), Self::Error> {
        if address + (number_of_blocks + self.first) * SECTOR_SIZE > self.last * SECTOR_SIZE {
            panic!("Attempt to read out of bounds {} {} {} {}", address, number_of_blocks, self.first, self.last);
        }
        self.inner.read(buf, address + self.first * SECTOR_SIZE, number_of_blocks)
    }
}

pub fn find_and_open_esp<T: BlockDevice>(disk: T) -> Result<SliceBlockDevice<T>, EspSearchError> {
    let (first, last) = find_esp_lba(&disk)?;
    Ok(SliceBlockDevice {
        first: first as usize,
        last: last as usize,
        inner: disk
    })
}

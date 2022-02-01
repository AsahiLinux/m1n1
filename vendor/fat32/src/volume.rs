use core::str;
use block_device::BlockDevice;
use core::fmt::{
    Debug,
    Formatter,
    Result,
};
use crate::tool::{
    is_fat32,
    read_le_u16,
    read_le_u32,
};
use crate::bpb::BIOSParameterBlock;
use crate::BUFFER_SIZE;
use crate::dir::Dir;
use crate::entry::Entry;
use crate::fat::FAT;

#[derive(Copy, Clone)]
pub struct Volume<T>
    where T: BlockDevice + Clone + Copy,
          <T as BlockDevice>::Error: core::fmt::Debug
{
    device: T,
    bpb: BIOSParameterBlock,
}

impl<T> Volume<T>
    where T: BlockDevice + Clone + Copy,
          <T as BlockDevice>::Error: core::fmt::Debug {
    /// Make volume from device which implement BlockDevice
    pub fn new(device: T) -> Volume<T> {
        let mut buf = [0; BUFFER_SIZE];
        device.read(&mut buf, 0, 1).unwrap();

        let mut volume_label = [0; 11];
        volume_label.copy_from_slice(&buf[0x47..0x52]);

        let mut file_system = [0; 8];
        file_system.copy_from_slice(&buf[0x52..0x5A]);

        let bps = read_le_u16(&buf[0x0B..0x0D]);
        if bps as usize != BUFFER_SIZE {
            panic!("BUFFER_SIZE is {} Bytes, byte_per_sector is {} Bytes\
            , please edit features",
                   BUFFER_SIZE, bps);
        }

        // if not fat32 file system, panic
        if !is_fat32(&file_system) { panic!("not fat32 file system"); }

        Volume::<T> {
            device,
            bpb: BIOSParameterBlock {
                byte_per_sector: bps,
                sector_per_cluster: buf[0x0D],
                reserved_sector: read_le_u16(&buf[0x0E..0x10]),
                num_fat: buf[0x10],
                total_sector: read_le_u32(&buf[0x20..0x24]),
                sector_per_fat: read_le_u32(&buf[0x24..0x28]),
                root_cluster: read_le_u32(&buf[0x2C..0x30]),
                id: read_le_u32(&buf[0x43..0x47]),
                volume_label,
                file_system,
            },
        }
    }

    /// Get Volume Label
    pub fn volume_label(&self) -> &str {
        str::from_utf8(&self.bpb.volume_label).unwrap()
    }

    /// Cd root dir, its Dir<T> Type
    pub fn root_dir(&self) -> Dir<T> {
        Dir::<T> {
            device: self.device,
            bpb: &self.bpb,
            detail: Entry::root_dir(self.bpb.root_cluster),
            fat: FAT::new(self.bpb.root_cluster,
                          self.device,
                          self.bpb.fat1()),
        }
    }
}

/// implement Debug Display for Volume
impl<T> Debug for Volume<T>
    where T: BlockDevice + Clone + Copy,
          <T as BlockDevice>::Error: core::fmt::Debug {
    fn fmt(&self, f: &mut Formatter<'_>) -> Result {
        f.debug_struct("Volume")
            .field("byte_per_sector", &self.bpb.byte_per_sector)
            .field("sector_per_cluster", &self.bpb.sector_per_cluster)
            .field("reserved_sector", &self.bpb.reserved_sector)
            .field("num_fat", &self.bpb.num_fat)
            .field("total_sector", &self.bpb.total_sector)
            .field("sector_per_fat", &self.bpb.sector_per_fat)
            .field("root_cluster", &self.bpb.root_cluster)
            .field("id", &self.bpb.id)
            .field("volume_label", &self.volume_label().trim())
            .field("file_system", &"FAT32")
            .finish()
    }
}

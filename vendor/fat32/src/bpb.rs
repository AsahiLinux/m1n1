/// Define BIOS Parameters
#[derive(Debug, Copy, Clone)]
pub struct BIOSParameterBlock {
    pub(crate) byte_per_sector: u16,
    pub(crate) sector_per_cluster: u8,
    pub(crate) reserved_sector: u16,
    pub(crate) num_fat: u8,
    pub(crate) total_sector: u32,
    pub(crate) sector_per_fat: u32,
    pub(crate) root_cluster: u32,
    pub(crate) id: u32,
    pub(crate) volume_label: [u8; 11],
    pub(crate) file_system: [u8; 8],
}

impl BIOSParameterBlock {
    /// Get the first sector offset bytes of the cluster from the cluster number
    pub(crate) fn offset(&self, cluster: u32) -> usize {
        ((self.reserved_sector as usize)
            + (self.num_fat as usize) * (self.sector_per_fat as usize)
            + (cluster as usize - 2) * (self.sector_per_cluster as usize))
            * (self.byte_per_sector as usize)
    }

    /// Get FAT1 Offset
    pub(crate) fn fat1(&self) -> usize {
        (self.reserved_sector as usize) * (self.byte_per_sector as usize)
    }

    /// Get sector_per_cluster_usize as usize value
    pub(crate) fn sector_per_cluster_usize(&self) -> usize {
        self.sector_per_cluster as usize
    }
}

use block_device::BlockDevice;
use crate::BUFFER_SIZE;
use crate::tool::read_le_u32;

#[derive(Debug, Copy, Clone)]
pub struct FAT<T>
    where T: BlockDevice + Clone + Copy,
          <T as BlockDevice>::Error: core::fmt::Debug {
    device: T,
    fat_offset: usize,
    start_cluster: u32,
    previous_cluster: u32,
    pub(crate) current_cluster: u32,
    next_cluster: Option<u32>,
    buffer: [u8; BUFFER_SIZE],
}

impl<T> FAT<T>
    where T: BlockDevice + Clone + Copy,
          <T as BlockDevice>::Error: core::fmt::Debug {
    pub(crate) fn new(cluster: u32, device: T, fat_offset: usize) -> Self {
        Self {
            device,
            fat_offset,
            start_cluster: cluster,
            previous_cluster: 0,
            current_cluster: 0,
            next_cluster: None,
            buffer: [0; BUFFER_SIZE],
        }
    }

    pub(crate) fn blank_cluster(&mut self) -> u32 {
        let mut cluster = 0;
        let mut done = false;

        for block in 0.. {
            self.device.read(&mut self.buffer,
                             self.fat_offset + block * BUFFER_SIZE,
                             1).unwrap();
            for i in (0..BUFFER_SIZE).step_by(4) {
                if read_le_u32(&self.buffer[i..i + 4]) == 0 {
                    done = true;
                    break;
                } else { cluster += 1; }
            }
            if done { break; }
        }
        cluster
    }

    pub(crate) fn write(&mut self, cluster: u32, value: u32) {
        let offset = (cluster as usize) * 4;
        let block_offset = offset / BUFFER_SIZE;
        let offset_left = offset % BUFFER_SIZE;
        let offset = self.fat_offset + block_offset * BUFFER_SIZE;
        let mut value: [u8; 4] = value.to_be_bytes();
        value.reverse();

        self.device.read(&mut self.buffer,
                         offset,
                         1).unwrap();
        self.buffer[offset_left..offset_left + 4].copy_from_slice(&value);
        self.device.write(&self.buffer,
                          offset,
                          1).unwrap();
    }

    pub(crate) fn refresh(&mut self, start_cluster: u32) {
        self.current_cluster = 0;
        self.start_cluster = start_cluster;
    }

    pub(crate) fn previous(&mut self) {
        if self.current_cluster != 0 {
            self.next_cluster = Some(self.current_cluster);
            self.current_cluster = self.previous_cluster;
        }
    }

    pub(crate) fn next_is_none(&self) -> bool {
        self.next_cluster.is_none()
    }

    fn current_cluster_usize(&self) -> usize {
        self.current_cluster as usize
    }
}

impl<T> Iterator for FAT<T>
    where T: BlockDevice + Clone + Copy,
          <T as BlockDevice>::Error: core::fmt::Debug {
    type Item = Self;

    fn next(&mut self) -> Option<Self::Item> {
        if self.current_cluster == 0 {
            self.current_cluster = self.start_cluster;
        } else {
            let next_cluster = self.next_cluster;
            if next_cluster.is_some() {
                self.previous_cluster = self.current_cluster;
                self.current_cluster = next_cluster.unwrap();
            } else {
                return None;
            }
        }

        let offset = self.current_cluster_usize() * 4;
        let block_offset = offset / BUFFER_SIZE;
        let offset_left = offset % BUFFER_SIZE;

        self.device.read(&mut self.buffer,
                         self.fat_offset + block_offset * BUFFER_SIZE,
                         1).unwrap();

        let next_cluster = read_le_u32(&self.buffer[offset_left..offset_left + 4]);
        let next_cluster = if next_cluster == 0x0FFFFFFF {
            None
        } else {
            Some(next_cluster)
        };

        self.next_cluster = next_cluster;

        Some(Self {
            next_cluster,
            ..(*self)
        })
    }
}

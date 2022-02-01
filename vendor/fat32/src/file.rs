use core::cmp;
use block_device::BlockDevice;
use crate::bpb::BIOSParameterBlock;
use crate::directory_item::DirectoryItem;
use crate::fat::FAT;
use crate::BUFFER_SIZE;
use crate::dir::DirIter;
use crate::tool::get_needed_sector;

/// Define FileError
#[derive(Debug)]
pub enum FileError {
    BufTooSmall,
    WriteError,
}

/// Define WriteType
pub enum WriteType {
    OverWritten,
    Append,
}

#[derive(Debug, Copy, Clone)]
pub struct File<'a, T>
    where T: BlockDevice + Clone + Copy,
          <T as BlockDevice>::Error: core::fmt::Debug {
    pub(crate) device: T,
    pub(crate) bpb: &'a BIOSParameterBlock,
    pub(crate) dir_cluster: u32,
    pub(crate) detail: DirectoryItem,
    pub(crate) fat: FAT<T>,
}

/// To Read File Per Sector By Iterator
pub struct ReadIter<'a, T>
    where T: BlockDevice + Clone + Copy,
          <T as BlockDevice>::Error: core::fmt::Debug {
    device: T,
    buffer: [u8; BUFFER_SIZE],
    bpb: &'a BIOSParameterBlock,
    fat: FAT<T>,
    left_length: usize,
    read_count: usize,
    need_count: usize,
}

impl<'a, T> File<'a, T>
    where T: BlockDevice + Clone + Copy,
          <T as BlockDevice>::Error: core::fmt::Debug {
    /// Read File To Buffer, Return File Length
    pub fn read(&self, buf: &mut [u8]) -> Result<usize, FileError> {
        let length = self.detail.length().unwrap();
        let spc = self.bpb.sector_per_cluster_usize();
        let cluster_size = spc * BUFFER_SIZE;
        let mut number_of_blocks = spc;

        if buf.len() < length { return Err(FileError::BufTooSmall); }

        let mut index = 0;
        self.fat.map(|f| {
            let offset = self.bpb.offset(f.current_cluster);
            let end = if (length - index) < cluster_size {
                let bytes_left = length % cluster_size;
                number_of_blocks = get_needed_sector(bytes_left);
                index + bytes_left
            } else {
                index + cluster_size
            };
            self.device.read(&mut buf[index..end],
                             offset,
                             number_of_blocks).unwrap();
            index += cluster_size;
        }).last();

        Ok(length)
    }

    /// Write Data To File, Using Append OR OverWritten
    pub fn write(&mut self, buf: &[u8], write_type: WriteType) -> Result<(), FileError> {
        let num_cluster = match write_type {
            WriteType::OverWritten => self.num_cluster(buf.len()),
            WriteType::Append => self.num_cluster(buf.len() + self.detail.length().unwrap())
        };

        match write_type {
            WriteType::OverWritten => {
                self.fat.map(|mut f| f.write(f.current_cluster, 0)).last();
                self.write_blank_fat(num_cluster);
                self._write(buf, &self.fat);
            }
            WriteType::Append => {
                let mut fat = self.fat;
                let exist_fat = fat.count();
                fat.find(|_| false);

                let (new_cluster, index) = self.fill_left_sector(buf, fat.current_cluster);
                if new_cluster {
                    let buf = &buf[index..];
                    let bl = self.fat.blank_cluster();

                    fat.write(fat.current_cluster, bl);
                    self.write_blank_fat(num_cluster - exist_fat);
                    fat.refresh(bl);

                    self._write(buf, &fat);
                }
            }
        }

        match write_type {
            WriteType::OverWritten => self.update_length(buf.len()),
            WriteType::Append => self.update_length(buf.len() + self.detail.length().unwrap())
        };

        Ok(())
    }

    /// Read Per Sector, Return ReadIter
    pub fn read_per_sector(&self) -> ReadIter<T> {
        let left_length = self.detail.length().unwrap();
        ReadIter::<T> {
            device: self.device,
            buffer: [0; BUFFER_SIZE],
            bpb: self.bpb,
            fat: self.fat,
            left_length,
            read_count: 0,
            need_count: get_needed_sector(left_length),
        }
    }

    /// Get Clusters The File Has
    fn num_cluster(&self, length: usize) -> usize {
        let spc = self.bpb.sector_per_cluster_usize();
        let cluster_size = spc * BUFFER_SIZE;
        if length % cluster_size != 0 {
            length / cluster_size + 1
        } else {
            length / cluster_size
        }
    }

    /// Write Buffer from one to another one
    fn buf_write(&self, from: &[u8], value: usize, to: &mut [u8]) {
        let index = value * BUFFER_SIZE;
        let index_end = index + BUFFER_SIZE;
        if from.len() < index_end {
            to.copy_from_slice(&[0; BUFFER_SIZE]);
            to[0..from.len() - index].copy_from_slice(&from[index..])
        } else {
            to.copy_from_slice(&from[index..index_end])
        }
    }

    /// Fill Left Sector
    fn fill_left_sector(&self, buf: &[u8], cluster: u32) -> (bool, usize) {
        let spc = self.bpb.sector_per_cluster_usize();
        let length = self.detail.length().unwrap();
        let get_used_sector = |len: usize| if len % (spc * BUFFER_SIZE) == 0 && length != 0 {
            spc
        } else {
            len % (spc * BUFFER_SIZE) / BUFFER_SIZE
        };
        let left_start = length % BUFFER_SIZE;
        let blank_size = BUFFER_SIZE - left_start;

        let mut already_fill = 0;
        let mut buf_has_left = true;
        let mut index = 0;
        let mut used_sector = get_used_sector(length);
        let mut data = [0; BUFFER_SIZE];
        let mut offset = self.bpb.offset(cluster) + used_sector * BUFFER_SIZE;

        if left_start != 0 {
            self.device.read(&mut data, offset, 1).unwrap();
            if buf.len() <= blank_size {
                data[left_start..left_start + buf.len()]
                    .copy_from_slice(&buf[0..]);
                buf_has_left = false;
            } else {
                data[left_start..].copy_from_slice(&buf[0..blank_size]);
                already_fill = blank_size;
                index = already_fill;
                used_sector = get_used_sector(length + already_fill);
                buf_has_left = true;
            };
            self.device.write(&data, offset, 1).unwrap();
            offset = self.bpb.offset(cluster) + BUFFER_SIZE;
        }

        if buf_has_left {
            let buf_needed_sector = get_needed_sector(buf.len() - already_fill);
            let the_cluster_left_sector = spc - used_sector;
            let num_sector = cmp::min(the_cluster_left_sector,
                                      buf_needed_sector);
            for s in 0..num_sector {
                self.buf_write(&buf[index..], s, &mut data);
                self.device.write(&data,
                                  offset + s * BUFFER_SIZE,
                                  1).unwrap();
                index += BUFFER_SIZE;
            }

            if buf_needed_sector > the_cluster_left_sector { return (true, index); }
        }

        (false, 0)
    }

    /// Update File Length
    fn update_length(&mut self, length: usize) {
        let fat = FAT::new(self.dir_cluster, self.device, self.bpb.fat1());
        let mut iter = DirIter::new(self.device, fat, self.bpb);
        iter.find(|d| {
            !d.is_deleted() && !d.is_lfn() && d.cluster() == self.detail.cluster()
        }).unwrap();

        self.detail.set_file_length(length);
        iter.previous();
        iter.update_item(&self.detail.bytes());
        iter.update();
    }

    /// Write Blank FAT
    fn write_blank_fat(&mut self, num_cluster: usize) {
        for n in 0..num_cluster {
            let bl1 = self.fat.blank_cluster();
            self.fat.write(bl1, 0x0FFFFFFF);
            let bl2 = self.fat.blank_cluster();
            if n != num_cluster - 1 {
                self.fat.write(bl1, bl2);
            }
        }
    }

    /// Basic Write Function
    fn _write(&self, buf: &[u8], fat: &FAT<T>) {
        let spc = self.bpb.sector_per_cluster_usize();
        let mut buf_write = [0; BUFFER_SIZE];
        let mut write_count = get_needed_sector(buf.len());
        let op = |start: usize, sectors: usize| -> &[u8] {
            &buf[start * BUFFER_SIZE..(start + sectors) * BUFFER_SIZE]
        };

        let mut w = 0;
        fat.map(|f| {
            let count = if write_count / spc > 0 {
                write_count -= spc;
                spc
            } else {
                write_count
            };

            let offset = self.bpb.offset(f.current_cluster);
            if count == spc {
                if (w + spc) * BUFFER_SIZE > buf.len() {
                    self.buf_write(&buf, w, &mut buf_write);
                    self.device.write(&buf_write,
                                      offset,
                                      1).unwrap();
                } else {
                    self.device.write(op(w, count),
                                      offset,
                                      count).unwrap();
                }
                w += count;
            } else {
                self.device.write(op(w, count - 1),
                                  offset,
                                  count - 1).unwrap();
                w += count - 1;
                self.buf_write(&buf, w, &mut buf_write);
                self.device.write(&buf_write,
                                  offset + (count - 1) * BUFFER_SIZE,
                                  1).unwrap();
            }
        }).last();
    }
}

impl<'a, T> Iterator for ReadIter<'a, T>
    where T: BlockDevice + Clone + Copy,
          <T as BlockDevice>::Error: core::fmt::Debug {
    type Item = ([u8; BUFFER_SIZE], usize);

    fn next(&mut self) -> Option<Self::Item> {
        let spc = self.bpb.sector_per_cluster_usize();
        if self.read_count == self.need_count { return None; }
        if self.read_count % spc == 0 { self.fat.next(); }

        let offset = self.bpb.offset(self.fat.current_cluster)
            + (self.read_count % spc) * BUFFER_SIZE;
        self.device.read(&mut self.buffer,
                         offset,
                         1).unwrap();
        self.read_count += 1;

        Some(if self.read_count == self.need_count {
            (self.buffer, self.left_length)
        } else {
            self.left_length -= BUFFER_SIZE;
            (self.buffer, BUFFER_SIZE)
        })
    }
}
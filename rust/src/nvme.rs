use block_device::BlockDevice;

const BLOCK_SIZE: usize = 4096;

#[derive(Clone, Copy)]
pub struct NvmeBlockDevice {
    ns: u32
}

#[derive(Debug)]
pub struct NvmeError;

impl NvmeBlockDevice {
    pub fn new(ns: u32) -> NvmeBlockDevice {
        NvmeBlockDevice {
            ns
        }
    }
}

extern "C" {
    fn nvme_read(nsid: u32, lba: u64, buffer: *mut u8) -> bool;
}


impl BlockDevice for NvmeBlockDevice {
    type Error = NvmeError;
    fn write(&self, _buf: &[u8], _address: usize, _number_of_blocks: usize) -> Result<(), Self::Error> {
        unimplemented!();
    }
    fn read(&self, buf: &mut [u8], address: usize, number_of_blocks: usize) -> Result<(), Self::Error> {
        if address % BLOCK_SIZE != 0 {
            panic!("Unaligned read {}", address);
        }
        let mut bounce_buffer = [0; BLOCK_SIZE * 2];
        let buf_ptr = &mut bounce_buffer;
        let offset = buf_ptr.as_ptr().align_offset(BLOCK_SIZE);
        let aligned_ptr = &mut buf_ptr[offset..offset + BLOCK_SIZE];
        let block_num = address / BLOCK_SIZE;
        for i in 0..number_of_blocks {
            //SAFETY: nvme_read only writes BLOCK_SIZE bytes into the buffer
            unsafe {
                if !nvme_read(self.ns, (block_num + i) as u64, aligned_ptr.as_mut_ptr()) {
                    return Err(NvmeError)
                }
            }
            if i != number_of_blocks - 1 || buf.len() % BLOCK_SIZE == 0 {
                buf[i * BLOCK_SIZE..(i + 1) * BLOCK_SIZE].copy_from_slice(aligned_ptr);
            } else {
                let remainder = buf.len() % BLOCK_SIZE;
                buf[i * BLOCK_SIZE..].copy_from_slice(&aligned_ptr[..remainder]);
            }
        }
        Ok(())
    }
}

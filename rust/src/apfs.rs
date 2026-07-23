// SPDX-License-Identifier: MIT

use crate::{
    c_size_t,
    gpt::GPT,
    nvme::{alloc_sector_buf, nvme_read, NVMEStorage, SectorBuffer},
    println,
};
use alloc::{boxed::Box, slice, string::String, vec::Vec};
use core::{cmp, ffi::c_void, mem, ptr};
use uuid::Uuid;

struct NxSuperblock([u8; 4096]);

macro_rules! obj_field {
    ($name:ident, $typ:ident, $offs:expr) => {
        #[allow(dead_code)]
        fn $name(&self) -> $typ {
            $typ::from_le_bytes(
                self.0[$offs..$offs + mem::size_of::<$typ>()]
                    .try_into()
                    .unwrap(),
            )
        }
    };
}

macro_rules! obj_header {
    () => {
        obj_field!(cksum, u64, 0);
        obj_field!(oid, u64, 8);
        obj_field!(xid, u64, 16);
        obj_field!(type_, u32, 24);
        obj_field!(subtype, u32, 28);
    };
}

impl NxSuperblock {
    const MAGIC: u32 = 1112758350; //'BSXN'
    const MAX_FILE_SYSTEMS: usize = 100;
    fn get_buf(&mut self) -> &mut [u8] {
        &mut self.0
    }
    fn new() -> Self {
        NxSuperblock([0; 4096])
    }
    obj_header!();
    obj_field!(magic, u32, 32);
    obj_field!(block_size, u32, 36);
    obj_field!(omap_oid, u64, 160);
    obj_field!(xp_desc_blocks, u32, 104);
    obj_field!(xp_desc_base, u64, 112);
    fn fs_oid(&self, i: usize) -> u64 {
        let at = 184 + 8 * i;
        u64::from_le_bytes(self.0[at..at + 8].try_into().unwrap())
    }
}

struct OmapPhys<'a>(&'a [u8]);
impl OmapPhys<'_> {
    const SIZE: usize = 88;
    obj_header!();
    obj_field!(tree_oid, u64, 48);
}

struct NLoc<'a>(&'a [u8]);

impl NLoc<'_> {
    obj_field!(off, u16, 0);
    obj_field!(len, u16, 2);
}

struct KVLoc<'a>(&'a [u8]);
impl KVLoc<'_> {
    const SIZE: usize = 8;
    fn k(&self) -> NLoc<'_> {
        NLoc(&self.0[0..0 + 4])
    }
    fn v(&self) -> NLoc<'_> {
        NLoc(&self.0[4..4 + 4])
    }
}

struct KVOff<'a>(&'a [u8]);
impl KVOff<'_> {
    const SIZE: usize = 4;
    obj_field!(k, u16, 0);
    obj_field!(v, u16, 2);
}

struct OmapKey<'a>(&'a [u8]);
impl OmapKey<'_> {
    obj_field!(oid, u64, 0);
    obj_field!(xid, u64, 8);
}

struct OmapVal<'a>(&'a [u8]);
impl OmapVal<'_> {
    obj_field!(size, u32, 4);
    obj_field!(paddr, u64, 8);
}

struct JDrecHashedKey<'a>(&'a [u8]);
impl JDrecHashedKey<'_> {
    obj_field!(obj_id_and_type, u64, 0);
    fn name_len(&self) -> u32 {
        u32::from_le_bytes(self.0[8..8 + 4].try_into().unwrap()) & 0x000003ff
    }
    fn name(&self) -> &[u8] {
        &self.0[12..12 + self.name_len() as usize - 1]
    }
}

struct JDrecVal<'a>(&'a [u8]);
impl JDrecVal<'_> {
    obj_field!(file_id, u64, 0);
}

struct JFileExtentKey<'a>(&'a [u8]);
impl JFileExtentKey<'_> {
    obj_field!(obj_id_and_type, u64, 0);
    obj_field!(logical_addr, u64, 8);
}

struct JFileExtentVal<'a>(&'a [u8]);
impl JFileExtentVal<'_> {
    obj_field!(len_and_flags, u64, 0);
    obj_field!(phys_block_num, u64, 8);
}

struct BTreeInfo;
impl BTreeInfo {
    const SIZE: usize = 40;
}

struct BTreeNodePhys<'a>(&'a [u8]);
impl BTreeNodePhys<'_> {
    const FIXED_KV_SIZE: u16 = 0x4;
    const ROOT: u16 = 0x1;
    const SIZE: usize = 56;
    obj_header!();
    obj_field!(flags, u16, 32);
    obj_field!(level, u16, 34);
    obj_field!(nkeys, u32, 36);
    fn table_space(&self) -> NLoc<'_> {
        NLoc(&self.0[40..])
    }
}

const APFS_FS_FLAGS_OFFSET: usize = 264;
struct ApfsSuperblock<'a>(&'a [u8]);
impl ApfsSuperblock<'_> {
    const MAGIC: u32 = 1112756289; //'BSPA'
    obj_header!();
    obj_field!(magic, u32, 32);
    obj_field!(role, u16, 964);
    obj_field!(fs_flags, u64, APFS_FS_FLAGS_OFFSET);
    obj_field!(omap_oid, u64, 128);
    obj_field!(root_tree_oid, u64, 136);
}

const VOL_ROLE_XART: u16 = 0x100;
const OBJ_TYPE_SHIFT: u32 = 60;
const APFS_TYPE_FILE_EXTENT: u64 = 8;
const APFS_TYPE_DIR_REC: u64 = 9;
const ROOT_DIR_INO_NUM: u64 = 2;

struct Partition {
    offset: u64,
    buf: Box<SectorBuffer>,
}

fn pread(disk: &mut Partition, pos: u64, target: &mut [u8]) -> Result<(), ()> {
    unsafe {
        for i in 0..target.len().next_multiple_of(4096) / 4096 {
            let lba = disk.offset + i as u64 + pos;
            if !nvme_read(1, lba, disk.buf.0.as_mut_ptr() as *mut _) {
                println!("nvme_read({}, {}) failed", 1, lba);
                return Err(());
            }
            let off = i * 4096;
            let copy_len = cmp::min(4096, target.len() - off);
            target[off..off + copy_len].copy_from_slice(&disk.buf.0[..copy_len])
        }
    }
    Ok(())
}

// should probably fix xids here
fn lookup_omap<'a>(
    _disk: &mut Partition,
    cur_node: &'a BTreeNodePhys,
    key: u64,
) -> Option<OmapVal<'a>> {
    if cur_node.level() != 0 {
        unimplemented!();
    }
    if cur_node.flags() & BTreeNodePhys::FIXED_KV_SIZE != 0 {
        let toc_off = cur_node.table_space().off() as usize + BTreeNodePhys::SIZE;
        let key_start = toc_off + cur_node.table_space().len() as usize;
        let val_end = cur_node.0.len()
            - if cur_node.flags() & BTreeNodePhys::ROOT == 0 {
                0
            } else {
                BTreeInfo::SIZE
            };
        for i in 0..cur_node.nkeys() as usize {
            let entry = KVOff(&cur_node.0[(toc_off + i * KVOff::SIZE)..]);
            let key_off = entry.k() as usize + key_start;
            let map_key = OmapKey(&cur_node.0[key_off..]);
            if map_key.oid() == key {
                let val_off = val_end - entry.v() as usize;
                return Some(OmapVal(&cur_node.0[val_off..]));
            }
        }
        None
    } else {
        unimplemented!();
    }
}

fn lookup_gl<'a>(_disk: &mut Partition, cur_node: &'a BTreeNodePhys) -> Option<u64> {
    let root_ino_key = ROOT_DIR_INO_NUM | (APFS_TYPE_DIR_REC << OBJ_TYPE_SHIFT);
    if cur_node.level() != 0 {
        unimplemented!();
    }
    if cur_node.flags() & BTreeNodePhys::FIXED_KV_SIZE == 0 {
        let toc_off = cur_node.table_space().off() as usize + BTreeNodePhys::SIZE;
        let key_start = toc_off + cur_node.table_space().len() as usize;
        let val_end = cur_node.0.len()
            - if cur_node.flags() & BTreeNodePhys::ROOT == 0 {
                0
            } else {
                BTreeInfo::SIZE
            };
        for i in 0..cur_node.nkeys() as usize {
            let entry = KVLoc(&cur_node.0[(toc_off + i * KVLoc::SIZE)..]);
            let key_off = entry.k().off() as usize + key_start;
            let key_end = entry.k().len() as usize + key_off;
            let map_key = JDrecHashedKey(&cur_node.0[key_off..key_end]);
            if map_key.obj_id_and_type() != root_ino_key {
                continue;
            }
            if !String::from_utf8_lossy(map_key.name()).ends_with(".gl") {
                continue;
            }
            let val_off = val_end - entry.v().off() as usize;
            let val_end = entry.v().len() as usize + val_off;
            return Some(JDrecVal(&cur_node.0[val_off..val_end]).file_id());
        }
        None
    } else {
        unimplemented!();
    }
}

fn lookup_extents<'a>(
    _disk: &mut Partition,
    cur_node: &'a BTreeNodePhys,
    key: u64,
) -> Option<JFileExtentVal<'a>> {
    if cur_node.level() != 0 {
        unimplemented!();
    }
    if cur_node.flags() & BTreeNodePhys::FIXED_KV_SIZE == 0 {
        let toc_off = cur_node.table_space().off() as usize + BTreeNodePhys::SIZE;
        let key_start = toc_off + cur_node.table_space().len() as usize;
        let val_end = cur_node.0.len()
            - if cur_node.flags() & BTreeNodePhys::ROOT == 0 {
                0
            } else {
                BTreeInfo::SIZE
            };
        for i in 0..cur_node.nkeys() as usize {
            let entry = KVLoc(&cur_node.0[(toc_off + i * KVLoc::SIZE)..]);
            let key_off = entry.k().off() as usize + key_start;
            let key_end = entry.k().len() as usize + key_off;
            let map_key = JFileExtentKey(&cur_node.0[key_off..key_end]);
            if map_key.obj_id_and_type() != key {
                continue;
            }
            let val_off = val_end - entry.v().off() as usize;
            let val_end = entry.v().len() as usize + val_off;
            let val = JFileExtentVal(&cur_node.0[val_off..val_end]);
            return Some(val);
        }
        None
    } else {
        unimplemented!();
    }
}

fn scan_volume(disk: &mut Partition) -> Result<Vec<u8>, ()> {
    let mut sb = NxSuperblock::new();
    pread(disk, 0, sb.get_buf())?;
    if sb.magic() != NxSuperblock::MAGIC {
        return Err(());
    }
    let block_size = sb.block_size() as u64;
    assert!(block_size == 4096);
    for i in 0..sb.xp_desc_blocks() {
        let mut sbc = NxSuperblock::new();
        pread(disk, sb.xp_desc_base() + i as u64, sbc.get_buf())?;
        if sbc.magic() == NxSuperblock::MAGIC && sbc.xid() > sb.xid() {
            sb = sbc;
        }
    }
    let mut cont_omap_bytes = vec![0; OmapPhys::SIZE];
    pread(disk, sb.omap_oid(), &mut cont_omap_bytes)?;
    let cont_omap = OmapPhys(&cont_omap_bytes);
    let mut cont_node_bytes = vec![0; sb.block_size() as usize];
    pread(disk, cont_omap.tree_oid(), &mut cont_node_bytes)?;
    let cont_node = BTreeNodePhys(&cont_node_bytes);
    assert!(cont_omap.oid() == sb.omap_oid());
    for i in 0..NxSuperblock::MAX_FILE_SYSTEMS {
        let fs_id = sb.fs_oid(i);
        if fs_id == 0 {
            continue;
        }
        let vsb = lookup_omap(disk, &cont_node, fs_id);
        let mut asb_bytes = vec![0; sb.block_size() as usize];
        if vsb.is_none() {
            continue;
        }
        let asb_offset = vsb.unwrap().paddr();
        pread(disk, asb_offset, &mut asb_bytes)?;
        let asb = ApfsSuperblock(&asb_bytes);
        assert!(asb.oid() == fs_id);
        assert!(asb.magic() == ApfsSuperblock::MAGIC);
        if asb.role() != VOL_ROLE_XART {
            continue;
        }
        let mut vol_omap_bytes = vec![0; OmapPhys::SIZE];
        pread(disk, asb.omap_oid(), &mut vol_omap_bytes)?;
        let vol_omap = OmapPhys(&vol_omap_bytes);
        assert!(vol_omap.oid() == asb.omap_oid());
        let mut vol_node_bytes = vec![0; sb.block_size() as usize];
        pread(disk, vol_omap.tree_oid(), &mut vol_node_bytes)?;
        let vol_node = BTreeNodePhys(&vol_node_bytes);
        assert!(vol_node.oid() == vol_omap.tree_oid());
        let fs_root = lookup_omap(disk, &vol_node, asb.root_tree_oid()).unwrap();
        let mut fs_root_bytes = vec![0; fs_root.size() as usize];
        pread(disk, fs_root.paddr(), &mut fs_root_bytes)?;
        let fs_root_node = BTreeNodePhys(&fs_root_bytes);
        assert!(fs_root_node.oid() == asb.root_tree_oid());
        let gl_file_id = lookup_gl(disk, &fs_root_node).unwrap();
        let extent = lookup_extents(
            disk,
            &fs_root_node,
            gl_file_id | (APFS_TYPE_FILE_EXTENT << OBJ_TYPE_SHIFT),
        )
        .unwrap();
        let mut data = vec![0; extent.len_and_flags() as usize];
        pread(disk, extent.phys_block_num(), &mut data)?;
        return Ok(data);
    }
    Err(())
}

fn scan_disks() -> Result<Vec<u8>, ()> {
    let storage = NVMEStorage::new(1, 0);
    let mut pt = GPT::new(storage).map_err(|_| ())?;
    for i in 0..pt.count() {
        let v = pt.index(i).map_err(|_| ())?;
        if v.get_type_guid() != Uuid::parse_str("69646961-6700-11aa-aa11-00306543ecac").unwrap() {
            continue;
        }
        let mut part = Partition {
            offset: v.get_starting_lba(),
            buf: alloc_sector_buf(),
        };
        return scan_volume(&mut part);
    }
    Err(())
}

#[no_mangle]
pub unsafe extern "C" fn rust_read_gigalocker(size: *mut c_size_t) -> *mut c_void {
    unsafe {
        let gl = match scan_disks() {
            Ok(g) => g,
            Err(_) => {
                *size = 0;
                return ptr::null_mut();
            }
        };
        let gl = gl.into_boxed_slice();
        *size = gl.len();
        Box::into_raw(gl) as *mut _
    }
}

#[no_mangle]
pub unsafe extern "C" fn rust_free_gigalocker(data: *mut c_void, size: c_size_t) {
    unsafe {
        mem::drop(Box::from_raw(slice::from_raw_parts_mut(
            data as *mut u8,
            size,
        )));
    }
}

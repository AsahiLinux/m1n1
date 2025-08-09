// SPDX-License-Identifier: MIT
use core::ffi::*;
use core::mem::size_of;

use crate::c_size_t;

#[derive(Debug)]
pub enum AdtError {
    NotFound = -1,
    BadOffset = -4,
    BadPath = -5,
    BadNCells = -14,
    BadValue = -15,
    BadLength = -20,
}

const ADT_ALIGN: i32 = 4;

#[repr(C)]
#[derive(Debug)]
pub struct ADTProperty {
    name: [c_char; 32],
    size: u32,
    value: [u8],
}

#[repr(C)]
#[derive(Debug, Copy, Clone)]
pub struct ADTNodeHeader {
    property_count: u32,
    child_count: u32,
}

#[repr(C, packed(1))]
pub struct ADTSegmentRanges {
    phys: u64,
    iova: u64,
    remap: u64,
    size: u32,
    unk: u32,
}

#[repr(C)]
pub struct ADT<'a> {
    size: usize,
    data: &'a [u8],
}

impl<'a> ADT<'a> {
    /// Check that our byte offset into ADT memory is properly aligned
    fn check_offset(offset: i32) -> Result<(), AdtError> {
        if offset < 0 || (offset % ADT_ALIGN != 0) {
            Err(AdtError::BadOffset)
        } else {
            Ok(())
        }
    }

    /// Check that the node pointed to is within the bounds of the ADT and
    /// has a valid property and child count
    fn check_node(node: *const ADTNodeHeader) -> Result<(), AdtError> {
        unsafe {
            if node as usize + size_of::<ADTNodeHeader>()
                > adt.add(adt_get_size() as usize) as usize
                || (*node).property_count > 2048
                || (*node).property_count == 0
                || (*node).child_count > 2048
            {
                Err(AdtError::BadOffset)
            } else {
                Ok(())
            }
        }
    }

    /// Check that our property is not bigger than 1 MB
    fn check_property(prop: *const ADTProperty) -> Result<(), AdtError> {
        if prop.is_null() {
            return Err(AdtError::BadOffset);
        }

        unsafe {
            if (*prop).size & 0x7ff00000 != 0 {
                Err(AdtError::BadOffset)
            } else {
                Ok(())
            }
        }
    }

    /// Manually create a fat pointer to the ADTProperty at ptr. This is required
    /// as ADTProperty.value is an unsized slice of bytes
    fn adt_prop_ptr(ptr: *const u8) -> *mut ADTProperty {
        // SAFETY: ptr is only ever a byte offset into ADT memory, which
        // is given to us by iBoot and can be assumed valid.
        unsafe {
            let val_size: usize = *(ptr.add(32)) as usize;

            let sp: *const [u8] = core::slice::from_raw_parts(
                ptr,
                size_of::<[char; 32]>() + size_of::<u32>() + val_size,
            );

            sp as *mut ADTProperty
        }
    }

    /// Get a static reference to the ADTNodeHeader at the given offset into ADT memory
    pub fn node_at(offset: i32) -> Result<&'static ADTNodeHeader, AdtError> {
        ADT::check_offset(offset)?;

        unsafe {
            let node = adt.add(offset as usize) as *const ADTNodeHeader;
            match ADT::check_node(node) {
                Ok(()) => Ok(&*node),
                Err(e) => Err(e),
            }
        }
    }

    /// Get a static reference to the ADTProperty at the given offset into ADT memory
    pub fn property_at(offset: i32) -> Result<&'static ADTProperty, AdtError> {
        ADT::check_offset(offset)?;

        unsafe {
            let prop = ADT::adt_prop_ptr(adt.add(offset as usize) as *const u8);
            match ADT::check_property(prop) {
                Ok(()) => Ok(&*prop),
                Err(e) => Err(e),
            }
        }
    }

    /// Mutable version of ADT::property_at()
    pub fn property_at_mut(offset: i32) -> Result<&'static mut ADTProperty, AdtError> {
        ADT::check_offset(offset)?;

        // SAFETY: adt is always valid, and our offset is proven aligned above
        unsafe {
            let prop = ADT::adt_prop_ptr(adt.add(offset as usize) as *const u8);
            let ret = ADT::check_property(prop);
            match ret {
                Ok(_i) => Ok(&mut *prop),
                Err(e) => Err(e),
            }
        }
    }

    pub fn first_property_offset(offset: i32) -> i32 {
        offset + size_of::<ADTNodeHeader>() as i32
    }

    pub fn next_property_offset(offset: i32) -> Result<i32, AdtError> {
        let prop = ADT::property_at(offset)?;

        // current offset PLUS the total number of bytes in the property
        Ok(offset + 32 + 4 + ((prop.size as i32 + (ADT_ALIGN - 1)) & !(ADT_ALIGN - 1)))
    }

    pub fn first_child_offset(offset: i32) -> Result<i32, AdtError> {
        let node = ADT::node_at(offset)?;
        let mut cnt = node.property_count;
        let mut off = ADT::first_property_offset(offset);

        while cnt > 0 {
            off = ADT::next_property_offset(off)?;
            cnt -= 1;
        }
        Ok(off)
    }

    pub fn next_sibling_offset(offset: i32) -> Result<i32, AdtError> {
        let node = ADT::node_at(offset)?;
        let mut cnt = node.child_count;
        let mut off = ADT::first_child_offset(offset)?;

        while cnt > 0 {
            off = ADT::next_sibling_offset(off)?;
            cnt -= 1;
        }
        Ok(off)
    }

    /// Search the node at the given byte offset for a property with the given name.
    pub fn get_property_by_name(
        nodeoffset: i32,
        name: &str,
    ) -> Result<&'static ADTProperty, AdtError> {
        let node_prop_cnt = ADT::node_at(nodeoffset)?.property_count;
        let first_prop_offset = ADT::first_property_offset(nodeoffset);
        let mut cur_prop_offset = first_prop_offset;

        for _i in 0..node_prop_cnt {
            let prop = ADT::property_at(cur_prop_offset)?;
            if CStr::from_bytes_until_nul(&prop.name)
                .unwrap()
                .to_str()
                .unwrap()
                == name
            {
                return Ok(prop);
            }
            cur_prop_offset = ADT::next_property_offset(cur_prop_offset)?;
        }
        Err(AdtError::NotFound)
    }

    pub fn get_property_by_name_mut(
        nodeoffset: i32,
        name: &str,
    ) -> Result<&'static mut ADTProperty, AdtError> {
        let node_prop_cnt = ADT::node_at(nodeoffset)?.property_count;
        let first_prop_offset = ADT::first_property_offset(nodeoffset);
        let mut cur_prop_offset = first_prop_offset;

        for _i in 0..node_prop_cnt {
            let prop = ADT::property_at_mut(cur_prop_offset)?;
            if CStr::from_bytes_until_nul(&prop.name)
                .unwrap()
                .to_str()
                .unwrap()
                == name
            {
                return Ok(prop);
            }
            cur_prop_offset = ADT::next_property_offset(cur_prop_offset)?;
        }
        Err(AdtError::NotFound)
    }

    pub fn set_property(nodeoffset: i32, name: &str, val: &[u8]) -> Result<usize, AdtError> {
        let p = ADT::get_property_by_name_mut(nodeoffset, name)?;

        if val.len() != p.size as usize {
            return Err(AdtError::BadLength);
        }

        unsafe {
            core::ptr::copy_nonoverlapping(val.as_ptr(), p.value.as_mut_ptr(), p.size as usize);
        }

        Ok(p.size as usize)
    }

    /// Determine if an ADT node's name is equal to some string bounded by a length.
    /// This is required to match the semantics expected when doing a full ADT path
    /// trace.
    fn node_names_equal(a: &str, b: &str, len: usize) -> bool {
        if a == &b[..len] {
            return true;
        }

        if b[..len].contains('@') && a.as_bytes().get(len) == Some(&b'@') {
            return true;
        }

        false
    }

    pub fn get_subnode_offset_by_name(
        parentoffset: i32,
        name: &str,
        len: usize,
    ) -> Result<i32, AdtError> {
        let cnt = ADT::node_at(parentoffset)?.child_count;
        let mut current_offset = ADT::first_child_offset(parentoffset)?;

        for _i in 0..cnt {
            let prop = ADT::get_property_by_name(current_offset, "name")?;
            let strname = CStr::from_bytes_until_nul(&prop.value)
                .unwrap()
                .to_str()
                .unwrap();
            if ADT::node_names_equal(strname, name, len) {
                return Ok(current_offset);
            }
            current_offset = ADT::next_sibling_offset(current_offset)?;
        }
        Err(AdtError::NotFound)
    }

    pub fn is_compatible(offset: i32, compatible: &str) -> Result<bool, AdtError> {
        let prop = ADT::get_property_by_name(offset, "compatible")?;
        Ok(CStr::from_bytes_until_nul(&prop.value)
            .unwrap()
            .to_str()
            .unwrap()
            .contains(compatible))
    }

    pub fn node_name(offset: i32) -> Result<&'static str, AdtError> {
        let p = ADT::get_property_by_name(offset, "name")?;
        Ok(CStr::from_bytes_until_nul(&p.value)
            .unwrap()
            .to_str()
            .unwrap())
    }

    pub fn copy_prop_val(nodeoffset: i32, name: &str, ptr: usize) -> Result<usize, AdtError> {
        let p = ADT::get_property_by_name(nodeoffset, name)?;

        // SAFETY: Everything here is a known quantity. Callers are reponsible for allocating
        // p.size bytes at ptr, and we know p points to a valid ADTProperty.
        unsafe {
            core::ptr::copy_nonoverlapping(p.value.as_ptr(), ptr as *mut u8, p.size as usize);
        }

        Ok(p.size as usize)
    }

    /// Trace a given ADT path and return the offset of the final node.
    pub fn path_offset_trace(path: &str, mut offsets: Option<&mut [i32]>) -> Result<i32, AdtError> {
        let mut offset = 0;
        let mut p = path;
        let mut oi = 0;

        match ADT::node_at(0) {
            Ok(_) => {}
            Err(e) => return Err(e),
        }

        while !p.is_empty() {
            p = p.trim_start_matches('/');

            if p.is_empty() {
                break;
            }

            let (seg, rest) = match p.find('/') {
                Some(pos) => p.split_at(pos),
                None => (p, ""), // We're at the final node in the path
            };

            match ADT::get_subnode_offset_by_name(offset, seg, seg.len()) {
                Ok(o) => offset = o,
                Err(e) => {
                    if let Some(offsets) = offsets.as_mut() {
                        if oi < offsets.len() {
                            offsets[oi] = 0;
                        } else {
                            return Err(AdtError::BadPath);
                        }
                    }
                    return Err(e);
                }
            };

            if let Some(offsets) = offsets.as_mut() {
                if oi < offsets.len() {
                    offsets[oi] = offset;
                    oi += 1;
                } else {
                    return Err(AdtError::BadPath);
                }
            }

            p = rest;
        }

        if let Some(offsets) = offsets.as_mut() {
            offsets[oi] = 0;
        }

        Ok(offset)
    }

    pub fn path_offset(path: &str) -> Result<i32, AdtError> {
        ADT::path_offset_trace(path, None)
    }

    fn get_cells(src: &[u32]) -> u64 {
        let mut val: u64 = 0;

        src.iter()
            .enumerate()
            .for_each(|(i, &x)| val |= (x as u64) << (32 * i));

        val
    }

    /// Retrieve the register container (addr, size) of a given node. Each addr
    /// and size is a contiguous array of u32s with `#address-cells` or `#size-cells`
    /// elements. The entire `reg` property is similarly a contiguous array of these
    /// containers [(addr, size), (addr, size), ...]. The `i` argument is an index
    /// into this array.
    pub fn get_reg_container(offsets: &[i32], pname: &str, i: i32) -> Result<(u64, u64), AdtError> {
        let mut cursor: usize = offsets.len() - 1;

        if offsets[0] == 0 {
            return Err(AdtError::BadOffset);
        }

        let mut node = offsets[cursor];
        let mut parent = {
            if cursor > 0 {
                offsets[cursor - 1]
            } else {
                0
            }
        };

        let mut addr_cells = u32::from_ne_bytes(
            ADT::get_property_by_name(parent, "#address-cells")
                .unwrap()
                .value[..4]
                .try_into()
                .unwrap(),
        );

        let mut size_cells = u32::from_ne_bytes(
            ADT::get_property_by_name(parent, "#size-cells")
                .unwrap()
                .value[..4]
                .try_into()
                .unwrap(),
        );

        if addr_cells < 1 || addr_cells > 2 || size_cells > 2 {
            return Err(AdtError::BadNCells);
        }

        let reg = ADT::get_property_by_name(node, pname)?;

        if reg.size == 0 {
            return Err(AdtError::NotFound);
        }

        // Check that the reg property is big enough to contain a reg
        // container at index i.
        if reg.size < (i as u32 + 1) * (addr_cells + size_cells) * 4 {
            return Err(AdtError::BadValue);
        }

        let addr_elems: &[u32];
        let size_elems: &[u32];

        // SAFETY: For a reg property, this pointer arithmetic is always true,
        // as we check above that i is within bounds.
        unsafe {
            let aref_ptr: *const u32 = (reg.value.as_ptr() as *const u32)
                .add((i as u32 * (addr_cells + size_cells)) as usize);

            let sref_ptr = aref_ptr.add((addr_cells) as usize);

            addr_elems = core::slice::from_raw_parts(aref_ptr, addr_cells as usize);

            size_elems = core::slice::from_raw_parts(sref_ptr, size_cells as usize);
        }

        let mut addr = ADT::get_cells(addr_elems);
        let size = ADT::get_cells(size_elems);

        while parent != 0 {
            cursor -= 1;
            node = parent;
            parent = {
                if cursor > 0 {
                    offsets[cursor - 1]
                } else {
                    0
                }
            };

            let ranges = ADT::get_property_by_name(node, "ranges")?;

            let paddr_cells = u32::from_ne_bytes(
                ADT::get_property_by_name(parent, "#address-cells")
                    .unwrap()
                    .value[..4]
                    .try_into()
                    .unwrap(),
            );

            if paddr_cells < 1 || paddr_cells > 2 || size_cells > 2 {
                return Err(AdtError::BadNCells);
            }

            let mut n_ranges = ranges.size / (4 * (paddr_cells + addr_cells + size_cells));

            while n_ranges != 0 {
                let ca_ref: &[u32];
                let pa_ref: &[u32];
                let cs_ref: &[u32];

                unsafe {
                    let ca_ptr = ranges.value.as_ptr() as *const u32;
                    let pa_ptr = ca_ptr.add(addr_cells as usize);
                    let cs_ptr = pa_ptr.add(addr_cells as usize);

                    ca_ref = core::slice::from_raw_parts(ca_ptr, addr_cells as usize);

                    pa_ref = core::slice::from_raw_parts(pa_ptr, paddr_cells as usize);

                    cs_ref = core::slice::from_raw_parts(cs_ptr, size_cells as usize);
                }

                let child_addr = ADT::get_cells(ca_ref);
                let parent_addr = ADT::get_cells(pa_ref);
                let child_size = ADT::get_cells(cs_ref);

                if addr >= child_addr && (addr + size) <= (child_addr + child_size) {
                    addr = addr - child_addr + parent_addr;
                    break;
                }
                n_ranges -= 1;
            }

            size_cells = u32::from_ne_bytes(
                ADT::get_property_by_name(parent, "#size-cells")
                    .unwrap()
                    .value[..4]
                    .try_into()
                    .unwrap(),
            );

            addr_cells = paddr_cells;
        }

        Ok((addr, size))
    }
}

extern "C" {
    static adt: *const c_void; // Global, immutable
}

unsafe extern "C" {
    unsafe fn adt_get_size() -> c_uint;
}

#[no_mangle]
pub unsafe extern "C" fn adt_check_header(_dt: *const c_void) -> c_int {
    match ADT::node_at(0) {
        Ok(_n) => 0,
        Err(e) => e as c_int,
    }
}

#[no_mangle]
pub unsafe extern "C" fn adt_first_property_offset(_dt: *const c_void, offset: c_int) -> c_int {
    ADT::first_property_offset(offset) as c_int
}

#[no_mangle]
pub unsafe extern "C" fn adt_next_property_offset(_dt: *const c_void, offset: c_int) -> c_int {
    ADT::next_property_offset(offset).unwrap() as c_int
}

#[no_mangle]
pub unsafe extern "C" fn adt_first_child_offset(_dt: *const c_void, offset: c_int) -> c_int {
    ADT::first_child_offset(offset).unwrap() as c_int
}

#[no_mangle]
pub unsafe extern "C" fn adt_next_sibling_offset(_dt: *const c_void, offset: c_int) -> c_int {
    ADT::next_sibling_offset(offset).unwrap() as c_int
}

#[no_mangle]
pub unsafe extern "C" fn adt_get_child_count(_dt: *const c_void, offset: c_int) -> c_int {
    ADT::node_at(offset).unwrap().child_count as c_int
}

#[no_mangle]
pub unsafe extern "C" fn adt_get_property_count(_dt: *const c_void, offset: c_int) -> c_int {
    ADT::node_at(offset).unwrap().property_count as c_int
}

#[no_mangle]
pub unsafe extern "C" fn adt_get_property_by_offset(
    _dt: *const c_void,
    offset: c_int,
) -> *const c_void {
    match ADT::property_at(offset) {
        Ok(p) => p as *const ADTProperty as *const c_void,
        Err(_) => core::ptr::null(),
    }
}

#[no_mangle]
pub unsafe extern "C" fn adt_get_property(
    _dt: *const c_void,
    nodeoffset: c_int,
    name: *const c_char,
) -> *const c_void {
    let strname: &str = unsafe { CStr::from_ptr(name).to_str().unwrap() };

    match ADT::get_property_by_name(nodeoffset, strname) {
        Ok(p) => p as *const ADTProperty as *const c_void,
        Err(_) => core::ptr::null(),
    }
}

#[no_mangle]
pub unsafe extern "C" fn adt_getprop(
    _dt: *const c_void,
    nodeoffset: c_int,
    name: *const c_char,
    lenp: *mut c_uint,
) -> *const c_void {
    let strname: &str = unsafe { CStr::from_ptr(name).to_str().unwrap() };

    let p = match ADT::get_property_by_name(nodeoffset, strname) {
        Ok(prop) => prop,
        Err(_) => return core::ptr::null(),
    };

    if !lenp.is_null() {
        unsafe { *lenp = p.size as u32 }
    }

    p.value.as_ptr() as *const c_void
}

#[no_mangle]
pub unsafe extern "C" fn adt_getprop_by_offset(
    _dt: *const c_void,
    offset: c_int,
    namep: *mut *const c_char,
    lenp: *mut c_uint,
) -> *const c_void {
    let p = match ADT::property_at(offset) {
        Ok(prop) => prop,
        Err(_) => return core::ptr::null(),
    };

    if !namep.is_null() {
        unsafe { *namep = p.name.as_ptr() }
    }

    if !lenp.is_null() {
        unsafe { *lenp = p.size as u32 }
    }

    p.value.as_ptr() as *const c_void
}

#[no_mangle]
pub unsafe extern "C" fn adt_setprop(
    _dt: *const c_void,
    nodeoffset: c_int,
    name: *const c_char,
    val: *const c_void,
    len: *const c_size_t,
) -> c_int {
    let buf: &[u8];
    let strname: &str;
    unsafe {
        buf = core::slice::from_raw_parts(val as *const u8, len as usize);
        strname = CStr::from_ptr(name).to_str().unwrap();
    };

    match ADT::set_property(nodeoffset, strname, buf) {
        Ok(sz) => sz.try_into().unwrap(),
        Err(e) => e as c_int,
    }
}

#[no_mangle]
pub unsafe extern "C" fn adt_subnode_offset(
    _dt: *const c_void,
    offset: c_int,
    name: *const c_char,
) -> c_int {
    let strname: &str;
    unsafe { strname = CStr::from_ptr(name).to_str().unwrap() }
    match ADT::get_subnode_offset_by_name(offset, strname, strname.len()) {
        Ok(p) => p as c_int,
        Err(e) => e as c_int,
    }
}

#[no_mangle]
pub unsafe extern "C" fn adt_subnode_offset_namelen(
    _dt: *const c_void,
    offset: c_int,
    name: *const c_char,
    len: c_size_t,
) -> c_int {
    let strname: &str = unsafe { CStr::from_ptr(name).to_str().unwrap() };

    match ADT::get_subnode_offset_by_name(offset, strname, len) {
        Ok(p) => p as c_int,
        Err(e) => e as c_int,
    }
}

#[no_mangle]
pub unsafe extern "C" fn adt_is_compatible(
    _dt: *const c_void,
    offset: c_int,
    compat: *const c_char,
) -> bool {
    let strcompat: &str = unsafe { CStr::from_ptr(compat).to_str().unwrap() };
    ADT::is_compatible(offset, strcompat).unwrap()
}

#[no_mangle]
pub unsafe extern "C" fn adt_get_name(_dt: *const c_void, nodeoffset: c_int) -> *const c_char {
    ADT::get_property_by_name(nodeoffset, "name")
        .unwrap()
        .value
        .as_ptr() as *const c_char
}

#[no_mangle]
pub unsafe extern "C" fn adt_getprop_copy(
    _dt: *const c_void,
    nodeoffset: c_int,
    name: *const c_char,
    out: *mut c_void,
    len: c_size_t,
) -> c_int {
    let strname: &str = unsafe { CStr::from_ptr(name).to_str().unwrap() };

    match ADT::copy_prop_val(nodeoffset, strname, out as usize) {
        Ok(p) => {
            if p != len {
                return AdtError::BadLength as c_int;
            } else {
                return len as c_int;
            }
        }
        Err(e) => e as c_int,
    }
}

#[no_mangle]
pub unsafe extern "C" fn adt_path_offset_trace(
    _dt: *const c_void,
    path: *const c_char,
    offsets: *mut i32,
) -> c_int {
    let strpath: &str = unsafe { CStr::from_ptr(path).to_str().unwrap() };
    let o: Option<&mut [i32]> = unsafe {
        // Derive a fat pointer from offsets. We (currently)
        // never have any paths that are more than 8 nodes deep,
        // so this is safe. If we're called by adt_path_offset(),
        // then offsets is null.
        if !offsets.is_null() {
            Some(core::slice::from_raw_parts_mut(offsets, 8))
        } else {
            None
        }
    };

    match ADT::path_offset_trace(strpath, o) {
        Ok(offset) => offset as c_int,
        Err(e) => e as c_int,
    }
}

#[no_mangle]
pub unsafe extern "C" fn adt_path_offset(_dt: *const c_void, path: *const c_char) -> c_int {
    let strpath: &str = unsafe { CStr::from_ptr(path).to_str().unwrap() };

    match ADT::path_offset(strpath) {
        Ok(offset) => offset as c_int,
        Err(e) => e as c_int,
    }
}

#[no_mangle]
pub unsafe extern "C" fn adt_get_reg(
    _dt: *const c_void,
    offsets: *mut i32,
    prop: *const c_char,
    i: c_int,
    paddr: *mut u64,
    psize: *mut u64,
) -> c_int {
    let strname: &str = unsafe { CStr::from_ptr(prop).to_str().unwrap() };
    let o: &[i32];

    unsafe {
        // Unlike adt_path_offset_trace(), we need to know
        // the exact number of nodes in the path.
        let mut n_offs: usize = 0;
        if *offsets == 0 {
            return AdtError::BadOffset as c_int;
        }

        while *offsets.add(n_offs) != 0 {
            n_offs += 1;
        }

        o = core::slice::from_raw_parts(offsets, n_offs);
    }

    match ADT::get_reg_container(o, strname, i) {
        Ok((a, s)) => {
            if !paddr.is_null() {
                unsafe {
                    *paddr = a;
                }
            }

            if !psize.is_null() {
                unsafe {
                    *psize = s;
                }
            }

            return 0;
        }
        Err(e) => {
            return e as c_int;
        }
    }
}

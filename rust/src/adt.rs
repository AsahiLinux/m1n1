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

const ADT_ALIGN: usize = 4;
const ADT_MAX_DEPTH: usize = 8;

/// An ADT node consists of a header (the part described by the struct), packed
/// key:value properties, and subnodes. Properties are always before subnodes
/// in memory.
#[repr(C)]
#[derive(Debug, Copy, Clone)]
pub struct ADTNode {
    property_count: u32,
    child_count: u32,
}

/// An ADT property is simply a collection of bytes preceded by a header which
/// denotes its name and size in bytes (exclusive of the header).
#[repr(C)]
#[derive(Debug)]
pub struct ADTProperty {
    name: [c_char; 32],
    size: u32,
    value: [u8],
}

/// ADTPropertyStringIterator
#[derive(Debug)]
pub struct ADTPropertyStringIterator<'a> {
    value: &'a [u8],
}

impl<'a> Iterator for ADTPropertyStringIterator<'a> {
    type Item = &'a str;

    fn next(&mut self) -> Option<&'a str> {
        match CStr::from_bytes_until_nul(self.value) {
            Ok(cs) => match cs.to_str() {
                Ok(s) => {
                    match self.value.iter().position(|&x| x == 0) {
                        Some(nul) => self.value = &self.value[(nul + 1)..],
                        None => self.value = &[],
                    }
                    Some(s)
                }
                Err(_) => {
                    self.value = &[];
                    None
                }
            },
            Err(_) => {
                self.value = &[];
                None
            }
        }
    }
}

#[repr(C, packed(1))]
pub struct ADTSegmentRanges {
    phys: u64,
    iova: u64,
    remap: u64,
    size: u32,
    unk: u32,
}

/// Check that our address is properly aligned
fn check_ptr(ptr: usize) -> Result<(), AdtError> {
    if ptr % ADT_ALIGN != 0 {
        Err(AdtError::BadOffset)
    } else {
        Ok(())
    }
}

/// Determine if an ADT node's name is equal to some string bounded by a length.
/// This is required to match the semantics expected when doing a full ADT path
/// trace.
fn node_names_equal(a: &str, b: &str) -> bool {
    if a == b {
        return true;
    }

    if b.contains('@') && a.as_bytes().get(b.len()) == Some(&b'@') {
        return true;
    }

    false
}

fn get_cells(src: &[u32]) -> u64 {
    let mut val: u64 = 0;

    src.iter()
        .enumerate()
        .for_each(|(i, &x)| val |= (x as u64) << (32 * i));

    val
}

fn get_cells_u8(src: &[u8]) -> u64 {
    let mut val: u64 = 0;

    for chunk in src.rchunks_exact(4) {
        val = (val << 32) | (u32::from_le_bytes(chunk.try_into().unwrap()) as u64)
    }

    val
}

/// Retrieve the register container (addr, size) of a given node at the end of
/// a node path trace.
///
/// Each addr and size is a contiguous array of u32s with `#address-cells` or
/// `#size-cells` elements. The entire `reg` property is similarly a contiguous
/// array of these containers [(addr, size), (addr, size), ...]. The `i` argument
/// is an index into this array.
pub fn get_reg_container(
    nodes: &[Option<&'static ADTNode>],
    pname: &str,
    i: i32,
) -> Result<(u64, u64), AdtError> {
    let head = unsafe { ADTNode::from_ptr(adt as *const ADTNode)? };

    // Sanity check to make sure we have at least one node in the path
    if nodes[0].is_none() {
        return Err(AdtError::BadPath);
    }

    if nodes[0].unwrap().as_ptr() == unsafe { adt as *const u8 } {
        return Err(AdtError::BadOffset);
    }

    let mut cursor: usize = nodes.len() - 1;

    while nodes[cursor].is_none() {
        cursor -= 1;
    }

    let mut node = nodes[cursor].unwrap();

    let mut parent = {
        if cursor > 0 {
            nodes[cursor - 1].unwrap()
        } else {
            head
        }
    };

    let mut addr_cells = parent.named_prop("#address-cells")?.u32()?;

    let mut size_cells = parent.named_prop("#size-cells")?.u32()?;

    if addr_cells < 1 || addr_cells > 2 || size_cells > 2 {
        return Err(AdtError::BadNCells);
    }

    let reg = node.named_prop(pname)?;

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
        let aref_ptr: *const u32 =
            (reg.value.as_ptr() as *const u32).add((i as u32 * (addr_cells + size_cells)) as usize);

        let sref_ptr = aref_ptr.add((addr_cells) as usize);

        addr_elems = core::slice::from_raw_parts(aref_ptr, addr_cells as usize);

        size_elems = core::slice::from_raw_parts(sref_ptr, size_cells as usize);
    }

    let mut addr = get_cells(addr_elems);
    let size = get_cells(size_elems);

    while parent.as_ptr() != head.as_ptr() {
        cursor -= 1;
        node = parent;
        parent = {
            if cursor > 0 {
                nodes[cursor - 1].unwrap()
            } else {
                head
            }
        };

        let ranges = node.named_prop("ranges")?;

        let paddr_cells = parent.named_prop("#address-cells")?.u32()?;

        if paddr_cells < 1 || paddr_cells > 2 || size_cells > 2 {
            return Err(AdtError::BadNCells);
        }

        let entry_size = (4 * (paddr_cells + addr_cells + size_cells)) as usize;
        let slice = unsafe { core::slice::from_raw_parts(ranges.value.as_ptr(), ranges.size as _) };

        for range in slice.chunks_exact(entry_size) {
            let (ca_ref, remainder) = range.split_at(4 * addr_cells as usize);
            let (pa_ref, cs_ref) = remainder.split_at(4 * paddr_cells as usize);

            let child_addr = get_cells_u8(ca_ref);
            let parent_addr = get_cells_u8(pa_ref);
            let child_size = get_cells_u8(cs_ref);

            if addr >= child_addr && (addr + size) <= (child_addr + child_size) {
                addr = addr - child_addr + parent_addr;
                break;
            }
        }

        size_cells = parent.named_prop("#size-cells")?.u32()?;

        addr_cells = paddr_cells;
    }

    Ok((addr, size))
}

impl ADTNode {
    /// Check that the node pointed to is within the bounds of the ADT and
    /// has a valid property and child count
    fn check(ptr: *const ADTNode) -> Result<(), AdtError> {
        unsafe {
            if ptr as usize + size_of::<ADTNode>() > adt.add(adt_get_size() as usize) as usize
                || (*ptr).property_count > 2048
                || (*ptr).property_count == 0
                || (*ptr).child_count > 2048
            {
                Err(AdtError::BadOffset)
            } else {
                Ok(())
            }
        }
    }

    /// Returns a static reference to the ADTNode at the given address
    fn from_ptr(ptr: *const ADTNode) -> Result<&'static ADTNode, AdtError> {
        check_ptr(ptr as usize)?;

        // SAFETY: The Rust API will only ever use this function to get the
        // head of the ADT, which is given to us by iBoot and assumed valid.
        // We use check_ptr() above to sanity-check any relocated offsets
        // given to us by C code as best we can.
        unsafe {
            match ADTNode::check(ptr) {
                Ok(()) => Ok(&*ptr),
                Err(e) => Err(e),
            }
        }
    }

    /// Get a reference to a node at a specified path, tracing the path to the
    /// desired node
    pub fn from_path_trace(
        path: &str,
        mut breadcrumbs: Option<&mut [Option<&'static ADTNode>]>,
    ) -> Result<&'static ADTNode, AdtError> {
        let ptr: *const ADTNode = unsafe { adt as *const ADTNode };
        let mut p = path;
        let mut bc_idx: usize = 0;

        let head = ADTNode::from_ptr(ptr)?;
        let mut n = head;

        while !p.is_empty() {
            p = p.trim_start_matches('/');

            if p.is_empty() {
                break;
            }

            let (cursor, rest) = match p.find('/') {
                Some(pos) => p.split_at(pos),
                None => (p, ""),
            };

            match n.subnode_by_name(cursor) {
                Ok(sn) => {
                    n = sn;
                }
                Err(e) => {
                    if let Some(b) = breadcrumbs.as_mut() {
                        if bc_idx < b.len() {
                            b[bc_idx] = Some(head);
                        } else {
                            return Err(AdtError::BadPath);
                        }
                    }
                    return Err(e);
                }
            };

            if let Some(b) = breadcrumbs.as_mut() {
                if bc_idx < b.len() {
                    b[bc_idx] = Some(n);
                    bc_idx += 1;
                } else {
                    return Err(AdtError::BadPath);
                }
            }

            p = rest;
        }

        if let Some(b) = breadcrumbs.as_mut() {
            b[bc_idx] = Some(head)
        }

        Ok(n)
    }

    pub fn from_path(path: &str) -> Result<&'static ADTNode, AdtError> {
        ADTNode::from_path_trace(path, None)
    }

    pub fn as_ptr(&self) -> *const u8 {
        self as *const ADTNode as *const u8
    }

    pub fn first_property(&self) -> Result<&'static ADTProperty, AdtError> {
        // SAFETY: We can never have a node that does not have at least one
        // property, and that property is always at the byte immediately following
        // the node header.
        unsafe { ADTProperty::from_ptr(self.as_ptr().add(size_of::<ADTNode>()) as usize) }
    }

    pub fn first_property_mut(&self) -> Result<&'static mut ADTProperty, AdtError> {
        // SAFETY: We know we are a valid node, and our header never changes size
        unsafe { ADTProperty::from_ptr_mut(self.as_ptr().add(size_of::<ADTNode>()) as usize) }
    }

    /// Walk the properties at the top of the curret node's memory to arrive at
    /// the node immediately following it. This could be a child node or a sibling.
    /// Use the relevant wrappers for additional safety.
    fn next_node(&self) -> Result<&'static ADTNode, AdtError> {
        let mut p = self.first_property()?;

        // We already have the first property
        for _ in 0..self.property_count - 1 {
            p = p.next_property()?;
        }

        // SAFETY: We will only ever reach this code when we can guarantee that
        // p is a reference to the very last property of the node, meaning that
        // the next byte after it must be a node.
        unsafe {
            ADTNode::from_ptr(
                p.as_ptr()
                    .add(size_of::<[c_char; 32]>())
                    .add(size_of::<u32>())
                    .add((p.size as usize + (ADT_ALIGN - 1)) & !(ADT_ALIGN - 1))
                    as *const ADTNode,
            )
        }
    }

    /// Walk the properties at the top of the curret node's memory to arrive at
    /// the first child node of the current node
    pub fn first_child(&self) -> Result<&'static ADTNode, AdtError> {
        if self.child_count < 1 {
            return Err(AdtError::NotFound);
        }

        self.next_node()
    }

    /// Searches the node for a property with the given name, and returns it if
    /// found.
    pub fn named_prop(&self, name: &str) -> Result<&'static ADTProperty, AdtError> {
        let mut p = self.first_property()?;

        for _ in 0..self.property_count {
            if p.name() == name {
                return Ok(p);
            }
            p = p.next_property()?;
        }
        Err(AdtError::NotFound)
    }

    pub fn name(&self) -> Result<&str, AdtError> {
        self.named_prop("name")?.str()
    }

    /// Searches the node for a property with the given name, and returns a mutable
    /// reference to it if found.
    pub fn named_prop_mut(&self, name: &str) -> Result<&'static mut ADTProperty, AdtError> {
        let mut p = self.first_property_mut()?;

        for _ in 0..self.property_count {
            if p.name() == name {
                return Ok(p);
            }
            p = p.next_property_mut()?;
        }
        Err(AdtError::NotFound)
    }

    /// Returns a reference to the current node's closest sibling
    pub fn next_sibling(&self) -> Result<&'static ADTNode, AdtError> {
        if self.child_count < 1 {
            return self.next_node();
        }

        let mut c = self.first_child()?;

        for _ in 0..self.child_count {
            c = c.next_sibling()?;
        }
        Ok(c)
    }

    /// Walks the node's subnodes and searches for one with the specified name
    pub fn subnode_by_name(&self, name: &str) -> Result<&'static ADTNode, AdtError> {
        let mut c = self.first_child()?;

        for _ in 0..self.child_count {
            let prop = c.named_prop("name")?;
            if node_names_equal(prop.str()?, name) {
                return Ok(c);
            }
            c = c.next_sibling()?;
        }
        Err(AdtError::NotFound)
    }

    pub fn is_compatible(&self, compatible: &str) -> Result<bool, AdtError> {
        Ok(self.named_prop("compatible")?.str()?.contains(compatible))
    }

    pub fn compatible(&self, index: usize) -> Option<&str> {
        let prop = self.named_prop("compatible").ok()?;
        prop.str_iter().nth(index)
    }
}

impl ADTProperty {
    /// Create a Rust fat pointer to the ADTProperty at ptr.
    ///
    /// We need to do this manually since we do not know the size of
    /// ADTProperty.value beforehand.
    fn fat_ptr(ptr: *const u8) -> *mut ADTProperty {
        // SAFETY: This function is only ever called when we can guarantee that
        // ptr points to a valid ADTProperty.
        unsafe {
            let sp: *const [u8] = core::slice::from_raw_parts(
                ptr,
                // Size of name, size of size, size of value
                size_of::<[char; 32]>() + size_of::<u32>() + *(ptr.add(32)) as usize,
            );

            sp as *mut ADTProperty
        }
    }

    /// Check that our property is no bigger than 1 MB
    fn check(ptr: *const ADTProperty) -> Result<(), AdtError> {
        if ptr.is_null() {
            return Err(AdtError::BadOffset);
        }

        unsafe {
            if (*ptr).size & 0x7ff00000 != 0 {
                Err(AdtError::BadOffset)
            } else {
                Ok(())
            }
        }
    }

    /// Returns a static reference to the ADTProperty at the given address
    fn from_ptr(ptr: usize) -> Result<&'static ADTProperty, AdtError> {
        check_ptr(ptr)?;

        // SAFETY: By the time we reach this code, we can be certain that ptr
        // points to an ADTProperty. This function is only used for FFI, and
        // the pointer passed to it is a priori valid as we are simply recreating
        // a pointer we would have calculated and passed to the foreign side
        // as an offset relative to the ADT head.
        unsafe {
            let prop = ADTProperty::fat_ptr(ptr as *const u8);
            match ADTProperty::check(prop) {
                Ok(()) => Ok(&*prop),
                Err(e) => Err(e),
            }
        }
    }

    fn from_ptr_mut(ptr: usize) -> Result<&'static mut ADTProperty, AdtError> {
        check_ptr(ptr)?;

        // SAFETY: Refer to the immutable function
        unsafe {
            let prop = ADTProperty::fat_ptr(ptr as *const u8);
            match ADTProperty::check(prop) {
                Ok(()) => Ok(&mut *prop),
                Err(e) => Err(e),
            }
        }
    }

    pub fn as_ptr(&self) -> *const u8 {
        self as *const ADTProperty as *const u8
    }

    pub fn next_property(&self) -> Result<&'static ADTProperty, AdtError> {
        // SAFETY: We know we are a valid property, and if the calculated pointer
        // does not also point to one, ADTProperty::from_ptr() will catch it.
        let ptr: usize = unsafe {
            self.as_ptr()
                .add(size_of::<[c_char; 32]>())
                .add(size_of::<u32>())
                .add((self.size as usize + (ADT_ALIGN - 1)) & !(ADT_ALIGN - 1)) as usize
        };
        ADTProperty::from_ptr(ptr)
    }

    pub fn next_property_mut(&self) -> Result<&'static mut ADTProperty, AdtError> {
        // SAFETY: We know we are a valid property
        let ptr: usize = unsafe {
            self.as_ptr()
                .add(32)
                .add(4)
                .add((self.size as usize + (ADT_ALIGN - 1)) & !(ADT_ALIGN - 1)) as usize
        };
        ADTProperty::from_ptr_mut(ptr)
    }

    pub fn name(&self) -> &str {
        CStr::from_bytes_until_nul(&self.name)
            .unwrap()
            .to_str()
            .unwrap()
    }

    pub fn str(&self) -> Result<&str, AdtError> {
        match CStr::from_bytes_until_nul(&self.value) {
            Ok(cs) => match cs.to_str() {
                Ok(s) => Ok(s),
                Err(_e) => Err(AdtError::BadValue),
            },
            Err(_e) => Err(AdtError::BadValue),
        }
    }

    pub fn str_iter<'a>(&'a self) -> ADTPropertyStringIterator<'a> {
        ADTPropertyStringIterator {
            value: unsafe { core::slice::from_raw_parts(self.value.as_ptr(), self.size as usize) },
        }
    }

    pub fn set(&mut self, val: &[u8]) -> Result<usize, AdtError> {
        if val.len() != self.size as usize {
            return Err(AdtError::BadLength);
        }

        unsafe {
            core::ptr::copy_nonoverlapping(
                val.as_ptr(),
                self.value.as_mut_ptr(),
                self.size as usize,
            );
        }

        Ok(self.size as usize)
    }

    /// Copy an ADTProperty's value to a preallocated buffer
    pub fn copy_raw(&self, ptr: usize) -> Result<usize, AdtError> {
        // SAFETY: Callers are reponsible for allocating self.size bytes at ptr,
        // and we never reach this code if we aren't already certain that we are
        // a valid property
        unsafe {
            core::ptr::copy_nonoverlapping(self.value.as_ptr(), ptr as *mut u8, self.size as usize);
        }

        Ok(self.size as usize)
    }

    pub fn u32(&self) -> Result<u32, AdtError> {
        if self.size != 4 {
            return Err(AdtError::BadLength);
        }

        Ok(u32::from_ne_bytes(self.value[..4].try_into().unwrap()))
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
    unsafe {
        match ADTNode::from_ptr(adt as *const ADTNode) {
            Ok(_) => 0,
            Err(e) => e as c_int,
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn adt_first_property_offset(_dt: *const c_void, offset: c_int) -> c_int {
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };

    let p: *const u8 = ADTNode::from_ptr(ptr)
        .unwrap()
        .first_property()
        .unwrap()
        .as_ptr();

    unsafe { p.sub(adt as usize) as c_int }
}

#[no_mangle]
pub unsafe extern "C" fn adt_first_child_offset(_dt: *const c_void, offset: c_int) -> c_int {
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };
    let n = ADTNode::from_ptr(ptr).unwrap();
    unsafe { n.first_child().unwrap().as_ptr().sub(adt as usize) as c_int }
}

#[no_mangle]
pub unsafe extern "C" fn adt_next_sibling_offset(_dt: *const c_void, offset: c_int) -> c_int {
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };
    let n = ADTNode::from_ptr(ptr).unwrap();
    unsafe { n.next_sibling().unwrap().as_ptr().sub(adt as usize) as c_int }
}

#[no_mangle]
pub unsafe extern "C" fn adt_get_child_count(_dt: *const c_void, offset: c_int) -> c_int {
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };
    ADTNode::from_ptr(ptr).unwrap().child_count as c_int
}

#[no_mangle]
pub unsafe extern "C" fn adt_get_property_count(_dt: *const c_void, offset: c_int) -> c_int {
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };
    ADTNode::from_ptr(ptr).unwrap().property_count as c_int
}

#[no_mangle]
pub unsafe extern "C" fn adt_get_property_by_offset(
    _dt: *const c_void,
    offset: c_int,
) -> *const c_void {
    let ptr: usize = unsafe { adt.add(offset as usize) as usize };
    match ADTProperty::from_ptr(ptr) {
        Ok(p) => p as *const ADTProperty as *const c_void,
        Err(_) => core::ptr::null(),
    }
}

#[no_mangle]
pub unsafe extern "C" fn adt_get_property(
    _dt: *const c_void,
    offset: c_int,
    name: *const c_char,
) -> *const c_void {
    let strname: &str = unsafe { CStr::from_ptr(name).to_str().unwrap() };
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };
    let n = ADTNode::from_ptr(ptr).unwrap();

    match n.named_prop(strname) {
        Ok(p) => p.as_ptr() as *const c_void,
        Err(_) => core::ptr::null(),
    }
}

#[no_mangle]
pub unsafe extern "C" fn adt_getprop(
    _dt: *const c_void,
    offset: c_int,
    name: *const c_char,
    lenp: *mut c_uint,
) -> *const c_void {
    let strname: &str = unsafe { CStr::from_ptr(name).to_str().unwrap() };
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };

    let p = match ADTNode::from_ptr(ptr).unwrap().named_prop(strname) {
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
    let ptr: usize = unsafe { adt.add(offset as usize) as usize };
    let p = match ADTProperty::from_ptr(ptr) {
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
    offset: c_int,
    name: *const c_char,
    val: *const c_void,
    len: *const c_size_t,
) -> c_int {
    let buf: &[u8];
    let strname: &str;
    let ptr: *const ADTNode;
    unsafe {
        buf = core::slice::from_raw_parts(val as *const u8, len as usize);
        strname = CStr::from_ptr(name).to_str().unwrap();
        ptr = adt.add(offset as usize) as *const ADTNode;
    };

    let n = match ADTNode::from_ptr(ptr) {
        Ok(node) => node,
        Err(e) => return e as c_int,
    };

    let p = match n.named_prop_mut(strname) {
        Ok(prop) => prop,
        Err(e) => return e as c_int,
    };

    match p.set(buf) {
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
    let strname: &str = unsafe { CStr::from_ptr(name).to_str().unwrap() };
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };

    let n = match ADTNode::from_ptr(ptr) {
        Ok(node) => node,
        Err(e) => return e as c_int,
    };

    match n.subnode_by_name(strname) {
        Ok(s) => unsafe { s.as_ptr().sub(adt as usize) as c_int },
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
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };
    ADTNode::from_ptr(ptr)
        .unwrap()
        .is_compatible(strcompat)
        .unwrap()
}

#[no_mangle]
pub unsafe extern "C" fn adt_is_compatible_at(
    _dt: *const c_void,
    offset: c_int,
    compat: *const c_char,
    index: usize,
) -> bool {
    let strcompat: &str = unsafe { CStr::from_ptr(compat).to_str().unwrap() };
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };
    ADTNode::from_ptr(ptr).unwrap().compatible(index).unwrap() == strcompat
}

#[no_mangle]
pub unsafe extern "C" fn adt_get_name(_dt: *const c_void, offset: c_int) -> *const c_char {
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };
    ADTNode::from_ptr(ptr).unwrap().name().unwrap().as_ptr() as *const c_char
}

#[no_mangle]
pub unsafe extern "C" fn adt_getprop_copy(
    _dt: *const c_void,
    offset: c_int,
    name: *const c_char,
    out: *mut c_void,
    len: c_size_t,
) -> c_int {
    let strname: &str = unsafe { CStr::from_ptr(name).to_str().unwrap() };
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };

    let n = match ADTNode::from_ptr(ptr) {
        Ok(node) => node,
        Err(e) => return e as c_int,
    };

    let p = match n.named_prop(strname) {
        Ok(prop) => prop,
        Err(e) => return e as c_int,
    };

    match p.copy_raw(out as usize) {
        Ok(l) => {
            if l != len {
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

    // We don't know how deep the path will be, but we do know that it can't be
    // deeper than 8 nodes
    let mut refs: [Option<&'static ADTNode>; ADT_MAX_DEPTH] = [None; ADT_MAX_DEPTH];

    match ADTNode::from_path_trace(strpath, Some(&mut refs)) {
        Ok(n) => {
            if !offsets.is_null() {
                for (i, &r) in refs.iter().enumerate() {
                    if r.is_some() {
                        unsafe {
                            *offsets.add(i) =
                                (r.unwrap().as_ptr() as *const u8).sub(adt as usize) as i32;
                        }
                    }
                }
            }
            unsafe { n.as_ptr().sub(adt as usize) as c_int }
        }
        Err(e) => e as c_int,
    }
}

#[no_mangle]
pub unsafe extern "C" fn adt_path_offset(_dt: *const c_void, path: *const c_char) -> c_int {
    let strpath: &str = unsafe { CStr::from_ptr(path).to_str().unwrap() };

    match ADTNode::from_path(strpath) {
        Ok(n) => unsafe { n.as_ptr().sub(adt as usize) as c_int },
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
    let mut n_offs: usize = 0;
    let mut refs: [Option<&'static ADTNode>; ADT_MAX_DEPTH] = [None; ADT_MAX_DEPTH];

    unsafe {
        // Unlike adt_path_offset_trace(), we need to know
        // the exact number of nodes in the path.
        if *offsets == 0 {
            return AdtError::BadOffset as c_int;
        }

        while *offsets.add(n_offs) != 0 {
            n_offs += 1;
        }

        o = core::slice::from_raw_parts_mut(offsets, n_offs);
        for (i, &offset) in o.iter().enumerate() {
            refs[i] = Some(ADTNode::from_ptr(adt.add(offset as usize) as *const ADTNode).unwrap());
        }
    }

    match get_reg_container(&refs, strname, i) {
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

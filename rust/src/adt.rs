// SPDX-License-Identifier: MIT
use core::ffi::*;
use core::mem::size_of;

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

    pub fn as_ptr(&self) -> *const u8 {
        self as *const ADTNode as *const u8
    }

    pub fn first_property(&self) -> Result<&'static ADTProperty, AdtError> {
        // SAFETY: We can never have a node that does not have at least one
        // property, and that property is always at the byte immediately following
        // the node header.
        unsafe { ADTProperty::from_ptr(self.as_ptr().add(size_of::<ADTNode>()) as usize) }
    }

    /// Walk the properties at the top of the curret node's memory to arrive at
    /// the first child node of the current node
    pub fn first_child(&self) -> Result<&'static ADTNode, AdtError> {
        if self.child_count < 1 {
            return Err(AdtError::NotFound);
        }

        let mut p = self.first_property()?;

        // We already have the first property
        for _ in 0..self.property_count - 1 {
            p = p.next_property()?;
        }

        // SAFETY: We will only ever reach this code when we can guarantee that
        // p is a reference to the very last property of the node, meaning that
        // the next byte after it must be a child node.
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
}

impl ADTProperty {
    /// Create a Rust fat pointer to the ADTProperty at ptr.
    ///
    /// We need to do this manually since we do not know the size of
    /// ADTProperty.value beforehand.
    fn fat_ptr(ptr: *const u8) -> *const ADTProperty {
        // SAFETY: This function is only ever called when we can guarantee that
        // ptr points to a valid ADTProperty.
        unsafe {
            let sp: *const [u8] = core::slice::from_raw_parts(
                ptr,
                // Size of name, size of size, size of value
                size_of::<[char; 32]>() + size_of::<u32>() + *(ptr.add(32)) as usize,
            );

            sp as *const ADTProperty
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

    pub fn name(&self) -> &str {
        CStr::from_bytes_until_nul(&self.name)
            .unwrap()
            .to_str()
            .unwrap()
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

// This function has load-bearing UB on the C side... The sound Rust equivalent
// breaks this. Recreate the UB here rather than call the new Rust function.
#[no_mangle]
pub unsafe extern "C" fn adt_next_property_offset(_dt: *const c_void, offset: c_int) -> c_int {
    let ptr: usize = unsafe { adt.add(offset as usize) as usize };
    let p = ADTProperty::from_ptr(ptr).unwrap();
    unsafe {
        p.as_ptr()
            .add(size_of::<[c_char; 32]>())
            .add(size_of::<u32>())
            .add((p.size as usize + (ADT_ALIGN - 1)) & !(ADT_ALIGN - 1))
            .sub(adt as usize) as c_int
    }
}

// This function has load-bearing UB on the C side... The sound Rust equivalent
// breaks this. Recreate the UB here rather than call the new Rust function.
#[no_mangle]
pub unsafe extern "C" fn adt_first_child_offset(_dt: *const c_void, offset: c_int) -> c_int {
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };
    let n = ADTNode::from_ptr(ptr).unwrap();

    let mut p: &ADTProperty = n.first_property().unwrap();

    for _ in 0..n.property_count - 1 {
        p = p.next_property().unwrap();
    }

    unsafe {
        ADTNode::from_ptr(
            p.as_ptr()
                .add(size_of::<[c_char; 32]>())
                .add(size_of::<u32>())
                .add((p.size as usize + (ADT_ALIGN - 1)) & !(ADT_ALIGN - 1))
                as *const ADTNode,
        )
        .unwrap()
        .as_ptr()
        .sub(adt as usize) as c_int
    }
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

/// TODO: Remove once no more callers reference this
#[no_mangle]
pub unsafe extern "C" fn adt_get_property_namelen(
    _dt: *const c_void,
    offset: c_int,
    name: *const c_char,
    _len: c_int,
) -> *const c_void {
    let strname: &str = unsafe { CStr::from_ptr(name).to_str().unwrap() };
    let ptr: *const ADTNode = unsafe { adt.add(offset as usize) as *const ADTNode };
    let n = ADTNode::from_ptr(ptr).unwrap();

    match n.named_prop(strname) {
        Ok(p) => p.as_ptr() as *const c_void,
        Err(_) => core::ptr::null(),
    }
}

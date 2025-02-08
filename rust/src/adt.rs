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
}

extern "C" {
    static adt: *const c_void; // Global, immutable
}

unsafe extern "C" {
    unsafe fn adt_get_size() -> c_uint;
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

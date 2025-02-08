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
    fn adt_prop_ptr(ptr: *const u8) -> *const ADTProperty {
        // SAFETY: ptr is only ever a byte offset into ADT memory, which
        // is given to us by iBoot and can be assumed valid.
        unsafe {
            let val_size: usize = *(ptr.add(32)) as usize;

            let sp: *const [u8] = core::slice::from_raw_parts(
                ptr,
                size_of::<[char; 32]>() + size_of::<u32>() + val_size,
            );

            sp as *const ADTProperty
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
}

extern "C" {
    static adt: *const c_void; // Global, immutable
}

unsafe extern "C" {
    unsafe fn adt_get_size() -> c_uint;
}

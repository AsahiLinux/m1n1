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
    /// Not required... yet
    pub fn from_raw(ptr: *const ADT) -> Self {
        // SAFETY: ptr comes from iBoot, we know it points to the ADT
        unsafe {
            let sz: usize = adt_get_size() as usize;
            Self {
                size: sz,
                data: core::slice::from_raw_parts(ptr as *const u8, sz),
            }
        }
    }

    /// These are only needed internally. The public API guarantees
    /// that every property or node returned is valid via these routines.
    fn check_node(node: *const ADTNodeHeader) -> Result<i32, AdtError> {
        // SAFETY: by the time we've called this, we already know we have
        // an aligned node
        unsafe {
            if node as usize + size_of::<ADTNodeHeader>()
                > adt.add(adt_get_size() as usize) as usize
                || (*node).property_count > 2048
                || (*node).property_count == 0
                || (*node).child_count > 2048
            {
                return Err(AdtError::BadOffset);
            }
        }
        Ok(0)
    }

    /// Make sure our offset is sane
    fn check_offset(offset: i32) -> Result<i32, AdtError> {
        if offset < 0 || (offset % ADT_ALIGN != 0) {
            Err(AdtError::BadOffset)
        } else {
            Ok(0)
        }
    }

    /// Properties can have a maximum of 1 MB of data in value
    fn check_property(prop: *const ADTProperty) -> Result<i32, AdtError> {
        if prop.is_null() {
            return Err(AdtError::BadOffset);
        }

        // SAFETY: We know the pointer is not null
        unsafe {
            if (*prop).size & 0x7ff00000 != 0 {
                return Err(AdtError::BadOffset);
            } else {
                Ok(0)
            }
        }
    }

    /// Do some cursed shit to get a fat pointer to ADTProperty
    fn adt_prop_ptr(ptr: *const u8) -> *const ADTProperty {
        // SAFETY: If we're calling this, we know we have a property
        // at the address
        unsafe {
            let val_size: usize = *(ptr.add(32)) as usize;
            // sizeof name + sizeof size + sizeof value
            let sp: *const [u8] = core::slice::from_raw_parts(
                ptr,
                size_of::<[char; 32]>() + size_of::<u32>() + val_size,
            );
            sp as *const ADTProperty
        }
    }

    /// Check a given offset for an ADT node. Returns a static reference
    /// to ADTNodeHeader if successful, or a known ADT error code if
    /// unseuccessful
    pub fn node_at(offset: i32) -> Result<&'static ADTNodeHeader, AdtError> {
        ADT::check_offset(offset)?;

        // SAFETY: adt is always a valid pointer
        unsafe {
            let node = adt.add(offset as usize) as *const ADTNodeHeader;
            let ret = ADT::check_node(node);
            match ret {
                Ok(_i) => Ok(&*node),
                Err(e) => Err(e),
            }
        }
    }

    pub fn get_child_count(offset: i32) -> Result<u32, AdtError> {
        Ok(ADT::node_at(offset)?.child_count)
    }

    /// Check a given offset for an ADT property. Returns a static reference to
    /// an ADTProperty if successful, or a known ADT error code if unseuccessful
    pub fn property_at(offset: i32) -> Result<&'static ADTProperty, AdtError> {
        ADT::check_offset(offset)?;

        // SAFETY: ad is always valid, and our offset is proven aligned above
        unsafe {
            let prop = ADT::adt_prop_ptr(adt.add(offset as usize) as *const u8);
            let ret = ADT::check_property(prop);
            match ret {
                Ok(_i) => Ok(&*prop),
                Err(e) => Err(e),
            }
        }
    }

    pub fn first_property_offset(offset: i32) -> i32 {
        offset + size_of::<ADTNodeHeader>() as i32
    }

    pub fn next_property_offset(offset: i32) -> Result<i32, AdtError> {
        let prop = ADT::property_at(offset)?;
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
        Ok(_i) => 0,
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
pub unsafe extern "C" fn adt_get_child_count(_dt: *const c_void, offset: c_int) -> c_int {
    ADT::get_child_count(offset).unwrap() as c_int
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

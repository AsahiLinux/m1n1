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

/// TODO: Remove once no more callers reference this
#[no_mangle]
pub unsafe extern "C" fn adt_get_property_namelen(
    _dt: *const c_void,
    nodeoffset: c_int,
    name: *const c_char,
    _len: c_int,
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

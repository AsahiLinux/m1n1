// SPDX-License-Identifier: MIT

use alloc::vec::Vec;
use core::cell::UnsafeCell;
use core::ffi::{c_char, c_int, c_uint, c_void, CStr};
use core::mem::size_of;
use core::ptr;

use crate::adt::ADTNode;
use crate::println;

const EFI_PAGE_SIZE: u64 = 4096;
const EFI_RT_REGION_ALIGN: u64 = 0x10000;

const EFI_SYSTEM_TABLE_SIGNATURE: u64 = 0x5453595320494249;
const EFI_RUNTIME_SERVICES_SIGNATURE: u64 = 0x56524553544e5552;
const EFI_SYSTEM_TABLE_REVISION: u32 = 2 << 16;

const EFI_RUNTIME_SERVICES_CODE: u32 = 4;
const EFI_RUNTIME_SERVICES_DATA: u32 = 5;
const EFI_CONVENTIONAL_MEMORY: u32 = 7;
const EFI_MEMORY_MAPPED_IO: u32 = 11;

const EFI_MAX_MEM_DESC: usize = 128;

const EFI_MEMORY_UC: u64 = 0x0000000000000001;
const EFI_MEMORY_WB: u64 = 0x0000000000000008;
const EFI_MEMORY_XP: u64 = 0x0000000000004000;
const EFI_MEMORY_RO: u64 = 0x0000000000020000;
const EFI_MEMORY_RUNTIME: u64 = 0x8000000000000000;
const EFI_MEMORY_ISA_VALID: u64 = 0x4000000000000000;
const EFI_MEMORY_ISA_SHIFT: u64 = 44;

const fn efi_memory_isa(mair: u16) -> u64 {
    EFI_MEMORY_ISA_VALID | ((mair as u64) << EFI_MEMORY_ISA_SHIFT)
}

#[allow(non_upper_case_globals)]
const EFI_RT_MMIO_nGnRnE: u64 = EFI_MEMORY_UC | efi_memory_isa(0x00) | EFI_MEMORY_RUNTIME;

const EFI_INVALID_TABLE_ADDR: u64 = !0;

const EFI_RT_PROPERTIES_TABLE_VERSION: u16 = 0x1;

extern "C" {
    static _base: u8;
    static _data_start: u8;
    static _end: u8;

    static psci_efi_table: u8;

    fn fdt_path_offset(fdt: *const c_void, path: *const c_char) -> c_int;
    fn fdt_getprop(
        fdt: *const c_void,
        nodeoffset: c_int,
        name: *const c_char,
        lenp: *mut c_int,
    ) -> *const c_void;
    fn fdt_setprop(
        fdt: *mut c_void,
        nodeoffset: c_int,
        name: *const c_char,
        val: *const c_void,
        len: c_int,
    ) -> c_int;

    fn tinf_crc32(data: *const c_void, length: c_uint) -> c_uint;
}

const ARM_PSCI_TABLE_GUID: [u8; 16] = [
    0x51, 0x76, 0xb4, 0xf9, 0x74, 0x46, 0xd9, 0x4e, 0x94, 0x3b, 0x5c, 0xea, 0xd2, 0x10, 0x9a, 0x8b,
];
const RT_PROPERTIES_TABLE_GUID: [u8; 16] = [
    0x8a, 0x91, 0x66, 0xeb, 0xef, 0x7e, 0x2a, 0x40, 0x84, 0x2e, 0x93, 0x1d, 0x21, 0xc3, 0x8a, 0xe9,
];

#[allow(dead_code)]
#[repr(C)]
struct TableHeader {
    signature: u64,
    revision: u32,
    headersize: u32,
    crc32: u32,
    reserved: u32,
}

impl TableHeader {
    const fn new(signature: u64) -> Self {
        Self {
            signature,
            revision: EFI_SYSTEM_TABLE_REVISION,
            headersize: 0,
            crc32: 0,
            reserved: 0,
        }
    }
}

#[repr(C)]
struct MemoryDescriptor {
    ty: u32,
    pad: u32,
    phys_addr: u64,
    virt_addr: u64,
    num_pages: u64,
    attribute: u64,
}

impl MemoryDescriptor {
    const ZERO: Self = Self {
        ty: 0,
        pad: 0,
        phys_addr: 0,
        virt_addr: 0,
        num_pages: 0,
        attribute: 0,
    };
}

#[allow(dead_code)]
#[repr(C)]
struct RuntimeServices {
    hdr: TableHeader,
    services: [u64; 14],
}

#[allow(dead_code)]
#[repr(C)]
struct SystemTable {
    hdr: TableHeader,
    fw_vendor: u64,
    fw_revision: u32,
    pad: u32,
    con_in_handle: u64,
    con_in: u64,
    con_out_handle: u64,
    con_out: u64,
    stderr_handle: u64,
    stderr: u64,
    runtime: u64,
    boottime: u64,
    nr_tables: u64,
    tables: u64,
}

#[allow(dead_code)]
#[repr(C)]
struct ConfigTable {
    guid: [u8; 16],
    table: u64,
}

#[allow(dead_code)]
#[repr(C)]
struct RtPropertiesTable {
    version: u16,
    length: u16,
    runtime_services_supported: u32,
}

#[repr(transparent)]
struct SyncUnsafeCell<T>(UnsafeCell<T>);

// SAFETY: must be specified everywhere this is used
unsafe impl<T> Sync for SyncUnsafeCell<T> {}

impl<T> SyncUnsafeCell<T> {
    const fn new(value: T) -> Self {
        Self(UnsafeCell::new(value))
    }

    const fn get(&self) -> *mut T {
        self.0.get()
    }

    fn addr(&self) -> u64 {
        self.get() as u64
    }
}

static EFI_VENDOR: [u16; 5] = [b'm' as u16, b'1' as u16, b'n' as u16, b'1' as u16, 0];

// SAFETY: m1n1 runs single-threaded and this table is only used in dt_setup_efi()
static EFI_MEMMAP: SyncUnsafeCell<[MemoryDescriptor; EFI_MAX_MEM_DESC]> =
    SyncUnsafeCell::new([MemoryDescriptor::ZERO; EFI_MAX_MEM_DESC]);

// SAFETY: m1n1 runs single-threaded and this table is only used in dt_setup_efi()
static EFI_RUNTIME: SyncUnsafeCell<RuntimeServices> = SyncUnsafeCell::new(RuntimeServices {
    hdr: TableHeader::new(EFI_RUNTIME_SERVICES_SIGNATURE),
    services: [EFI_INVALID_TABLE_ADDR; 14],
});

static EFI_RT_PROPERTIES: RtPropertiesTable = RtPropertiesTable {
    version: EFI_RT_PROPERTIES_TABLE_VERSION,
    length: size_of::<RtPropertiesTable>() as u16,
    runtime_services_supported: 0,
};

// SAFETY: m1n1 runs single-threaded and this table is only used in dt_setup_efi()
static EFI_CONFIG_TABLES: SyncUnsafeCell<[ConfigTable; 2]> = SyncUnsafeCell::new([
    ConfigTable {
        guid: ARM_PSCI_TABLE_GUID,
        table: 0,
    },
    ConfigTable {
        guid: RT_PROPERTIES_TABLE_GUID,
        table: 0,
    },
]);

// SAFETY: m1n1 runs single-threaded and this table is only used in dt_setup_efi()
static EFI_SYSTAB: SyncUnsafeCell<SystemTable> = SyncUnsafeCell::new(SystemTable {
    hdr: TableHeader::new(EFI_SYSTEM_TABLE_SIGNATURE),
    fw_vendor: 0,
    fw_revision: 0,
    pad: 0,
    con_in_handle: 0,
    con_in: 0,
    con_out_handle: 0,
    con_out: 0,
    stderr_handle: 0,
    stderr: 0,
    runtime: 0,
    boottime: 0,
    nr_tables: 0,
    tables: 0,
});

/// # Safety
///
/// Implementors must be `#[repr(C)]` with no padding bytes: the whole table
/// is fed to tinf_crc32, so every byte must be initialized. `table_update_crc()`
/// verifies this against `UEFI_EXPECTED_SIZE` at compile time.
unsafe trait Table: Sized {
    // expected size from the UEFI specification
    const UEFI_EXPECTED_SIZE: usize;
    fn header_mut(&mut self) -> &mut TableHeader;
}

unsafe impl Table for RuntimeServices {
    const UEFI_EXPECTED_SIZE: usize = 136;
    fn header_mut(&mut self) -> &mut TableHeader {
        &mut self.hdr
    }
}

unsafe impl Table for SystemTable {
    const UEFI_EXPECTED_SIZE: usize = 120;
    fn header_mut(&mut self) -> &mut TableHeader {
        &mut self.hdr
    }
}

fn table_update_crc<T: Table>(table: &mut T) {
    const {
        assert!(size_of::<T>() == T::UEFI_EXPECTED_SIZE);
    }
    table.header_mut().headersize = size_of::<T>() as u32;
    table.header_mut().crc32 = 0;
    // SAFETY: `table` is a fully initialized repr(C) struct without padding
    // (checked above); tinf_crc32 only reads size_of::<T>() bytes from it.
    let crc = unsafe { tinf_crc32(ptr::from_ref(table).cast(), size_of::<T>() as c_uint) };
    table.header_mut().crc32 = crc;
}

trait PreviousMultipleOf {
    fn previous_multiple_of(self, align: Self) -> Self;
}

impl PreviousMultipleOf for u64 {
    fn previous_multiple_of(self, align: u64) -> u64 {
        self & !(align - 1)
    }
}

#[derive(Clone, Copy)]
struct MemRange {
    base: u64,
    end: u64,
}

impl MemRange {
    fn size(&self) -> u64 {
        self.end - self.base
    }

    fn overlaps(&self, other: MemRange) -> bool {
        self.base < other.end && self.end > other.base
    }
}

struct MemoryMapBuilder {
    entries: &'static mut [MemoryDescriptor; EFI_MAX_MEM_DESC],
    used: usize,
}

impl MemoryMapBuilder {
    fn add(&mut self, ty: u32, base: u64, size: u64, attribute: u64) -> Result<(), c_int> {
        if size == 0 {
            return Ok(());
        }

        // TODO: ensure size is aligned

        if self.used >= self.entries.len() {
            println!(
                "FDT: EFI memory map overflow, can't add region 0x{:x}..0x{:x}",
                base,
                base + size
            );
            return Err(-1);
        }

        self.entries[self.used] = MemoryDescriptor {
            ty,
            pad: 0,
            phys_addr: base,
            virt_addr: if attribute & EFI_MEMORY_RUNTIME != 0 {
                base
            } else {
                0
            },
            num_pages: size / EFI_PAGE_SIZE,
            attribute,
        };
        self.used += 1;
        Ok(())
    }
}

fn fdt_node(dt: *mut c_void, path: &CStr) -> Result<c_int, c_int> {
    // SAFETY: dt points to a valid FDT via dt_setup_efi()
    let node = unsafe { fdt_path_offset(dt, path.as_ptr()) };
    if node < 0 {
        Err(node)
    } else {
        Ok(node)
    }
}

fn fdt_set_prop(dt: *mut c_void, node: c_int, name: &CStr, val: &[u8]) -> Result<(), c_int> {
    // SAFETY: dt points to a valid FDT via dt_setup_efi()
    let ret = unsafe {
        fdt_setprop(
            dt,
            node,
            name.as_ptr(),
            val.as_ptr().cast(),
            val.len() as c_int,
        )
    };
    if ret == 0 {
        Ok(())
    } else {
        Err(ret)
    }
}

fn fdt_set_u64(dt: *mut c_void, node: c_int, name: &CStr, val: u64) -> Result<(), c_int> {
    fdt_set_prop(dt, node, name, &val.to_be_bytes())
}

fn fdt_set_u32(dt: *mut c_void, node: c_int, name: &CStr, val: u32) -> Result<(), c_int> {
    fdt_set_prop(dt, node, name, &val.to_be_bytes())
}

fn efi_init_tables() {
    // SAFETY: Single-threaded and only called once before the tables are handed to the kernel
    unsafe {
        let tables = &mut *EFI_CONFIG_TABLES.get();
        tables[0].table = &raw const psci_efi_table as u64;
        tables[1].table = &raw const EFI_RT_PROPERTIES as u64;

        table_update_crc(&mut *EFI_RUNTIME.get());

        let systab = &mut *EFI_SYSTAB.get();
        systab.fw_vendor = EFI_VENDOR.as_ptr() as u64;
        systab.runtime = EFI_RUNTIME.addr();
        systab.nr_tables = tables.len() as u64;
        systab.tables = EFI_CONFIG_TABLES.addr();
        table_update_crc(systab);
    }
}

fn memmap_add_mmio(map: &mut MemoryMapBuilder) -> Result<(), c_int> {
    let Ok(ranges) = ADTNode::from_path("/arm-io").and_then(|node| node.named_prop("ranges"))
    else {
        println!("FDT: EFI: no /arm-io ranges");
        return Err(-1);
    };

    // Grab all MMIO ranges from the ADT and align to the highest page size
    // the kernel might use (64 KiB for pre-M1 SoCs)
    // TODO: this assumes #{address,size}-cells = 2 and is probably going to
    //       fail in funny ways otherwise
    let (entries, _) = ranges.bytes().as_chunks::<8>().0.as_chunks::<3>();
    let mut mmio: Vec<MemRange> = entries
        .iter()
        .filter_map(|&[_bus, phys, size]| {
            let (phys, size) = (u64::from_ne_bytes(phys), u64::from_ne_bytes(size));
            (size != 0).then_some(MemRange {
                base: phys.previous_multiple_of(EFI_RT_REGION_ALIGN),
                end: (phys + size).next_multiple_of(EFI_RT_REGION_ALIGN),
            })
        })
        .collect();

    // Merge overlapping or adjacent windows because the kernel will BUG_ON if
    // we have any of those
    mmio.sort_unstable_by_key(|range| range.base);
    mmio.dedup_by(|range, last| {
        if range.base <= last.end {
            last.end = last.end.max(range.end);
            true
        } else {
            false
        }
    });

    for range in &mmio {
        // Technically we would need to map PCIe BAR space as Device-nGnRE here
        // but since that's not used in the PSCI code we just ignore that for now...
        map.add(
            EFI_MEMORY_MAPPED_IO,
            range.base,
            range.size(),
            EFI_RT_MMIO_nGnRnE,
        )?;
    }

    Ok(())
}

fn fdt_get_memory_ranges(dt: *mut c_void) -> Result<Vec<MemRange>, c_int> {
    let memory = fdt_node(dt, c"/memory")?;
    let mut reg_len: c_int = 0;
    // SAFETY: On failure fdt_getprop returns NULL and stores the FDT
    // error in reg_len, otherwise the pointer is valid for reg_len bytes
    // until the FDT is next modified and it is consumed within this
    // function where we don't modify the FDT.
    let reg = unsafe {
        let reg = fdt_getprop(dt, memory, c"reg".as_ptr(), &mut reg_len);
        if reg.is_null() {
            return Err(reg_len);
        }
        core::slice::from_raw_parts(reg.cast::<u8>(), reg_len as usize)
    };
    let (pairs, _) = reg.as_chunks::<8>().0.as_chunks::<2>();
    Ok(pairs
        .iter()
        .map(|&[base, size]| {
            let base = u64::from_be_bytes(base);
            MemRange {
                base,
                end: base + u64::from_be_bytes(size),
            }
        })
        .collect())
}

fn efi_publish_to_fdt(dt: *mut c_void, map: &MemoryMapBuilder) -> Result<(), c_int> {
    let chosen = fdt_node(dt, c"/chosen")?;
    fdt_set_u64(dt, chosen, c"linux,uefi-system-table", EFI_SYSTAB.addr())?;
    fdt_set_u64(dt, chosen, c"linux,uefi-mmap-start", EFI_MEMMAP.addr())?;
    fdt_set_u32(
        dt,
        chosen,
        c"linux,uefi-mmap-size",
        (map.used * size_of::<MemoryDescriptor>()) as u32,
    )?;
    fdt_set_u32(
        dt,
        chosen,
        c"linux,uefi-mmap-desc-size",
        size_of::<MemoryDescriptor>() as u32,
    )?;
    fdt_set_u32(dt, chosen, c"linux,uefi-mmap-desc-ver", 1)?;

    Ok(())
}

fn efi_setup(dt: *mut c_void) -> Result<(), c_int> {
    efi_init_tables();

    let m1n1_base = &raw const _base as u64;
    let m1n1_data_start = &raw const _data_start as u64;
    let m1n1_end = &raw const _end as u64;

    if (m1n1_base | m1n1_data_start | m1n1_end) & (EFI_RT_REGION_ALIGN - 1) != 0 {
        println!(
            "FDT: EFI: m1n1 image not 0x{:x}-aligned (base 0x{:x}, data 0x{:x}, end 0x{:x})",
            EFI_RT_REGION_ALIGN, m1n1_base, m1n1_data_start, m1n1_end
        );
        // TODO: can't fail here because base of image might only be 16KiB aligned
        //return Err(-1);
    }

    // SAFETY: Single-threaded and this is the only mutable reference to EFI_MEMMAP
    let mut map = MemoryMapBuilder {
        entries: unsafe { &mut *EFI_MEMMAP.get() },
        used: 0,
    };

    // Add /memory from FDT but carve out m1n1 because we later add it as runtime memory
    // and the UEFI spec does not allow overlapping memory ranges
    let m1n1 = MemRange {
        base: m1n1_base,
        end: m1n1_end,
    };
    for range in &fdt_get_memory_ranges(dt)? {
        let mut pos = range.base;
        let end = range.end;

        if m1n1.overlaps(*range) {
            if m1n1.base > pos {
                map.add(EFI_CONVENTIONAL_MEMORY, pos, m1n1.base - pos, EFI_MEMORY_WB)?;
            }
            pos = m1n1.end;
        }
        if pos < end {
            map.add(EFI_CONVENTIONAL_MEMORY, pos, end - pos, EFI_MEMORY_WB)?;
        }
    }

    // add m1n1 code and rodata mapped as RX during EFI runtime calls
    map.add(
        EFI_RUNTIME_SERVICES_CODE,
        m1n1_base,
        m1n1_data_start - m1n1_base,
        EFI_MEMORY_WB | EFI_MEMORY_RO | EFI_MEMORY_RUNTIME,
    )?;

    // add m1n1 data and bss mapped as RW during EFI runtime calls
    map.add(
        EFI_RUNTIME_SERVICES_DATA,
        m1n1_data_start,
        m1n1_end - m1n1_data_start,
        EFI_MEMORY_WB | EFI_MEMORY_XP | EFI_MEMORY_RUNTIME,
    )?;

    // add all MMIO mapped as RW with Device-nGnRnE semantics during runtime calls
    memmap_add_mmio(&mut map)?;

    // and finally publish our EFI stub in the FDT
    efi_publish_to_fdt(dt, &map)?;

    println!(
        "FDT: EFI system table prepared at 0x{:x}",
        EFI_SYSTAB.addr()
    );

    Ok(())
}

/// # Safety
///
/// * `dt` must point to a valid FDT.
/// * /memory must've already been filled by dt_set_memory()
#[no_mangle]
pub unsafe extern "C" fn dt_setup_efi(dt: *mut c_void) -> c_int {
    match efi_setup(dt) {
        Ok(()) => 0,
        Err(err) => err,
    }
}

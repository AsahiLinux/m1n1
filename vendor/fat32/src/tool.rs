use core::convert::TryInto;
use core::str;
use crate::BUFFER_SIZE;
use crate::entry::NameType;

pub(crate) fn is_fat32(value: &[u8]) -> bool {
    let file_system_str = str::from_utf8(&value[0..5]).unwrap();
    file_system_str.eq("FAT32")
}

pub(crate) fn read_le_u16(input: &[u8]) -> u16 {
    let (int_bytes, _) = input.split_at(core::mem::size_of::<u16>());
    u16::from_le_bytes(int_bytes.try_into().unwrap())
}

pub(crate) fn read_le_u32(input: &[u8]) -> u32 {
    let (int_bytes, _) = input.split_at(core::mem::size_of::<u32>());
    u32::from_le_bytes(int_bytes.try_into().unwrap())
}

pub(crate) fn is_illegal(chs: &str) -> bool {
    let illegal_char = "\\/:*?\"<>|";
    for ch in illegal_char.chars() {
        if chs.contains(ch) {
            return true;
        }
    }
    false
}

pub(crate) fn sfn_or_lfn(value: &str) -> NameType {
    let (name, extension) = match value.find('.') {
        Some(i) => (&value[0..i], &value[i + 1..]),
        None => (&value[0..], "")
    };

    if value.is_ascii()
        && !value.contains(|ch: char| ch.is_ascii_uppercase())
        && !value.contains(' ')
        && !name.contains('.')
        && !extension.contains('.')
        && name.len() <= 8
        && extension.len() <= 3 {
        NameType::SFN
    } else {
        NameType::LFN
    }
}

pub(crate) fn get_count_of_lfn(value: &str) -> usize {
    let num_char = value.chars().count();
    if num_char % 13 == 0 { num_char / 13 } else { num_char / 13 + 1 }
}

pub(crate) fn get_lfn_index(value_str: &str, count: usize) -> usize {
    let end = 13 * (count - 1);
    let mut len = 0;
    for (index, ch) in value_str.chars().enumerate() {
        if (0..end).contains(&index) {
            len += ch.len_utf8();
        }
    }
    len
}

pub(crate) fn generate_checksum(value: &[u8]) -> u8 {
    let mut checksum = 0;
    for &i in value {
        checksum = (if checksum & 1 == 1 {
            0x80
        } else {
            0
        } + (checksum >> 1) + i as u32) & 0xFF;
    }
    checksum as u8
}

pub(crate) fn get_needed_sector(value: usize) -> usize {
    if value % BUFFER_SIZE != 0 {
        value / BUFFER_SIZE + 1
    } else {
        value / BUFFER_SIZE
    }
}

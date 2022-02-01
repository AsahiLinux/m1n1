use core::str;
use crate::tool::read_le_u32;
use crate::dir::OpType;

pub(crate) enum NameType {
    SFN,
    LFN,
}

#[derive(Copy, Clone, Debug, PartialOrd, PartialEq)]
pub enum EntryType {
    Dir,
    File,
    LFN,
    Deleted,
}

impl EntryType {
    fn from_value(value: u8) -> EntryType {
        if (value & 0x10) == 0x10 {
            EntryType::Dir
        } else if value == 0x0F {
            EntryType::LFN
        } else {
            EntryType::File
        }
    }

    fn from_create(value: OpType) -> EntryType {
        match value {
            OpType::Dir => EntryType::Dir,
            OpType::File => EntryType::File
        }
    }
}

impl Default for EntryType {
    fn default() -> Self {
        EntryType::Dir
    }
}

#[derive(Default, Copy, Clone, Debug)]
pub struct ShortDirectoryEntry {
    name: [u8; 8],
    extension: [u8; 3],
    length: u32,
    cluster: u32,
}

impl ShortDirectoryEntry {
    fn new(cluster: u32, value: &str, create_type: OpType) -> Self {
        let (name, extension) = match value.find('.') {
            Some(i) => (&value[0..i], &value[i + 1..]),
            None => (&value[0..], "")
        };

        let mut item = [0; 32];
        let _item = [0x20; 11];
        item[0x00..0x0B].copy_from_slice(&_item);
        item[0x00..0x00 + name.len()].copy_from_slice(name.as_bytes());
        item[0x08..0x08 + extension.len()].copy_from_slice(extension.as_bytes());
        item[0x00..0x00 + name.len()].make_ascii_uppercase();
        item[0x08..0x08 + extension.len()].make_ascii_uppercase();

        let mut cluster: [u8; 4] = cluster.to_be_bytes();
        cluster.reverse();

        item[0x14..0x16].copy_from_slice(&cluster[2..4]);
        item[0x1A..0x1C].copy_from_slice(&cluster[0..2]);

        match create_type {
            OpType::Dir => item[0x0B] = 0x10,
            OpType::File => item[0x10] = 0x20,
        }

        ShortDirectoryEntry::from_buf(&item)
    }

    fn new_bytes(cluster: u32, value: &[u8], create_type: OpType) -> Self {
        let mut item = [0; 32];
        item[0x00..0x0B].copy_from_slice(value);

        let mut cluster: [u8; 4] = cluster.to_be_bytes();
        cluster.reverse();

        item[0x14..0x16].copy_from_slice(&cluster[2..4]);
        item[0x1A..0x1C].copy_from_slice(&cluster[0..2]);

        match create_type {
            OpType::Dir => item[0x0B] = 0x10,
            OpType::File => item[0x10] = 0x20,
        }

        ShortDirectoryEntry::from_buf(&item)
    }

    fn root_dir(cluster: u32) -> Self {
        Self {
            cluster,
            ..Self::default()
        }
    }

    fn from_buf(buf: &[u8]) -> Self {
        let mut name = [0; 8];
        let mut extension = [0; 3];

        name.copy_from_slice(&buf[0x00..0x08]);
        extension.copy_from_slice(&buf[0x08..0x0B]);

        Self {
            name,
            extension,
            cluster: ((buf[0x15] as u32) << 24)
                | ((buf[0x14] as u32) << 16)
                | ((buf[0x1B] as u32) << 8)
                | (buf[0x1A] as u32),
            length: read_le_u32(&buf[0x1C..0x20]),
        }
    }

    fn get_full_name_bytes(&self) -> ([u8; 12], usize) {
        let mut len = 0;
        let mut full_name = [0; 12];

        for &i in self.name.iter() {
            if i != 0x20 {
                full_name[len] = i;
                len += 1;
            }
        }

        if self.extension[0] != 0x20 {
            full_name[len] = b'.';
            len += 1;
        }

        for &i in self.extension.iter() {
            if i != 0x20 {
                full_name[len] = i;
                len += 1;
            }
        }

        (full_name, len)
    }

    fn bytes(&self, item_type: EntryType) -> [u8; 32] {
        let mut item = [0; 32];

        item[0x00..0x08].copy_from_slice(&self.name);
        item[0x08..0x0B].copy_from_slice(&self.extension);

        let mut cluster: [u8; 4] = self.cluster.to_be_bytes();
        cluster.reverse();

        item[0x14..0x16].copy_from_slice(&cluster[2..4]);
        item[0x1A..0x1C].copy_from_slice(&cluster[0..2]);
        item[0x0C] = 0x18;

        let mut length: [u8; 4] = self.length.to_be_bytes();
        length.reverse();
        item[0x1C..0x20].copy_from_slice(&length);

        match item_type {
            EntryType::Dir => item[0x0B] = 0x10,
            EntryType::File => item[0x0B] = 0x20,
            EntryType::LFN => item[0x0B] = 0x0F,
            EntryType::Deleted => item[0x00] = 0xE5
        }

        item
    }
}

#[derive(Default, Copy, Clone, Debug)]
pub struct LongDirectoryEntry {
    attribute: u8,
    check_sum: u8,
    unicode_part1: [u8; 10],
    unicode_part2: [u8; 12],
    unicode_part3: [u8; 4],
}

impl LongDirectoryEntry {
    fn new(attribute: u8, check_sum: u8, value: &str) -> Self {
        let mut buf = [0; 32];
        buf[0x00] = attribute;
        buf[0x0D] = check_sum;
        LongDirectoryEntry::write_unicode(value, &mut buf);
        LongDirectoryEntry::from_buf(&buf)
    }

    fn write_unicode(value: &str, buf: &mut [u8]) {
        let mut temp = [0xFF; 26];
        let mut index = 0;

        for i in value.encode_utf16() {
            let part1 = (i & 0xFF) as u8;
            let part2 = ((i & 0xFF00) >> 8) as u8;
            temp[index] = part1;
            temp[index + 1] = part2;
            index += 2;
        }

        if index != 26 {
            temp[index] = 0;
            temp[index + 1] = 0;
        }
        index = 0;

        let mut op = |start: usize, end: usize| {
            for i in (start..end).step_by(2) {
                buf[i] = temp[index];
                buf[i + 1] = temp[index + 1];
                index += 2;
            }
        };

        op(0x01, 0x0A);
        op(0x0E, 0x19);
        op(0x1C, 0x1F);
    }

    fn from_buf(buf: &[u8]) -> Self {
        let attribute = buf[0x00];
        let check_sum = buf[0x0D];
        let mut unicode_part1 = [0; 10];
        let mut unicode_part2 = [0; 12];
        let mut unicode_part3 = [0; 4];

        unicode_part1.copy_from_slice(&buf[0x01..0x0B]);
        unicode_part2.copy_from_slice(&buf[0x0E..0x1A]);
        unicode_part3.copy_from_slice(&buf[0x1C..0x20]);

        Self {
            attribute,
            check_sum,
            unicode_part1,
            unicode_part2,
            unicode_part3,
        }
    }

    fn to_utf8(&self) -> ([u8; 13 * 3], usize) {
        let (mut utf8, mut len) = ([0; 13 * 3], 0);

        let mut op = |part: &[u8]| {
            for i in (0..part.len()).step_by(2) {
                if (part[i] == 0x00 && part[i + 1] == 0x00) || part[i] == 0xFF { break; }
                let unicode = ((part[i + 1] as u16) << 8) | part[i] as u16;

                if unicode <= 0x007F {
                    utf8[len] = unicode as u8;
                    len += 1;
                } else if unicode >= 0x0080 && unicode <= 0x07FF {
                    let part1 = (0b11000000 | (0b00011111 & (unicode >> 6))) as u8;
                    let part2 = (0b10000000 | (0b00111111) & unicode) as u8;

                    utf8[len] = part1;
                    utf8[len + 1] = part2;
                    len += 2;
                } else if unicode >= 0x0800 {
                    let part1 = (0b11100000 | (0b00011111 & (unicode >> 12))) as u8;
                    let part2 = (0b10000000 | (0b00111111) & (unicode >> 6)) as u8;
                    let part3 = (0b10000000 | (0b00111111) & unicode) as u8;

                    utf8[len] = part1;
                    utf8[len + 1] = part2;
                    utf8[len + 2] = part3;
                    len += 3;
                }
            }
        };

        op(&self.unicode_part1);
        op(&self.unicode_part2);
        op(&self.unicode_part3);

        (utf8, len)
    }

    fn count_of_name(&self) -> usize {
        self.attribute as usize & 0x1F
    }

    fn is_name_end(&self) -> bool {
        (self.attribute & 0x40) == 0x40
    }

    fn bytes(&self) -> [u8; 32] {
        let mut buf = [0; 32];
        buf[0x00] = self.attribute;
        buf[0x0B] = 0x0F;
        buf[0x0D] = self.check_sum;

        buf[0x01..0x0B].copy_from_slice(&self.unicode_part1);
        buf[0x0E..0x1A].copy_from_slice(&self.unicode_part2);
        buf[0x1C..0x20].copy_from_slice(&self.unicode_part3);
        buf
    }
}

#[derive(Default, Copy, Clone, Debug)]
pub struct Entry {
    pub(crate) item_type: EntryType,
    sfn: Option<ShortDirectoryEntry>,
    lfn: Option<LongDirectoryEntry>,
}

impl Entry {
    pub(crate) fn cluster(&self) -> u32 {
        self.sfn.unwrap().cluster
    }

    fn get_sfn(&self) -> Option<([u8; 12], usize)> {
        if self.sfn.is_some() {
            Some(self.sfn.as_ref().unwrap().get_full_name_bytes())
        } else {
            None
        }
    }

    fn get_lfn(&self) -> Option<([u8; 13 * 3], usize)> {
        if self.lfn.is_some() {
            Some(self.lfn.as_ref().unwrap().to_utf8())
        } else {
            None
        }
    }

    pub(crate) fn count_of_name(&self) -> Option<usize> {
        if self.lfn.is_some() {
            Some(self.lfn.as_ref().unwrap().count_of_name())
        } else {
            None
        }
    }

    pub(crate) fn is_name_end(&self) -> Option<bool> {
        if self.lfn.is_some() {
            Some(self.lfn.as_ref().unwrap().is_name_end())
        } else {
            None
        }
    }

    pub(crate) fn length(&self) -> Option<usize> {
        if self.sfn.is_some() {
            Some(self.sfn.as_ref().unwrap().length as usize)
        } else {
            None
        }
    }

    pub(crate) fn bytes(&self) -> [u8; 32] {
        if self.sfn.is_some() {
            self.sfn.as_ref().unwrap().bytes(self.item_type)
        } else {
            self.lfn.as_ref().unwrap().bytes()
        }
    }

    pub(crate) fn new_lfn(attribute: u8, check_sum: u8, value: &str) -> Self {
        Self {
            item_type: EntryType::LFN,
            sfn: None,
            lfn: Some(LongDirectoryEntry::new(attribute, check_sum, value)),
        }
    }

    pub(crate) fn new_sfn(cluster: u32, value: &str, create_type: OpType) -> Self {
        Self {
            item_type: EntryType::from_create(create_type),
            sfn: Some(ShortDirectoryEntry::new(cluster, value, create_type)),
            lfn: None,
        }
    }

    pub(crate) fn new_sfn_bytes(cluster: u32, value: &[u8], create_type: OpType) -> Self {
        Self {
            item_type: EntryType::from_create(create_type),
            sfn: Some(ShortDirectoryEntry::new_bytes(cluster, value, create_type)),
            lfn: None,
        }
    }

    pub(crate) fn root_dir(cluster: u32) -> Self {
        Self {
            sfn: Some(ShortDirectoryEntry::root_dir(cluster)),
            ..Self::default()
        }
    }

    pub(crate) fn from_buf(buf: &[u8]) -> Self {
        let item_type = if buf[0x00] == 0xE5 {
            EntryType::Deleted
        } else {
            EntryType::from_value(buf[0x0B])
        };

        match item_type {
            EntryType::LFN => {
                Self {
                    item_type,
                    sfn: None,
                    lfn: Some(LongDirectoryEntry::from_buf(buf)),
                }
            }
            _ => {
                Self {
                    item_type,
                    sfn: Some(ShortDirectoryEntry::from_buf(buf)),
                    lfn: None,
                }
            }
        }
    }

    pub(crate) fn sfn_equal(&self, value: &str) -> bool {
        if self.is_deleted() { return false; }
        let option = self.get_sfn();
        if option.is_none() { return false; }
        let (bytes, len) = option.unwrap();
        if let Ok(res) = str::from_utf8(&bytes[0..len]) {
            value.eq_ignore_ascii_case(res)
        } else {
            false
        }
    }

    pub(crate) fn lfn_equal(&self, value: &str) -> bool {
        if self.is_deleted() { return false; }
        let option = self.get_lfn();
        if option.is_none() { return false; }
        let (bytes, len) = option.unwrap();
        if let Ok(res) = str::from_utf8(&bytes[0..len]) {
            value.eq_ignore_ascii_case(res)
        } else {
            false
        }
    }

    pub(crate) fn set_file_length(&mut self, length: usize) {
        self.sfn.as_mut().unwrap().length = length as u32;
    }

    pub(crate) fn is_lfn(&self) -> bool {
        EntryType::LFN == self.item_type
    }

    pub(crate) fn is_deleted(&self) -> bool {
        EntryType::Deleted == self.item_type
    }

    pub(crate) fn is_dir(&self) -> bool {
        EntryType::Dir == self.item_type
    }

    pub(crate) fn is_file(&self) -> bool {
        EntryType::File == self.item_type
    }
}

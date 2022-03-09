// SPDX-License-Identifier: MIT
use core::ffi::c_void;

extern "C" {
    fn iodev_console_write(buf: *const c_void, len: u64);
}

pub struct IODevConsoleWriter;

impl core::fmt::Write for IODevConsoleWriter {
    #[inline]
    fn write_str(&mut self, msg: &str) -> core::fmt::Result {
        write(msg)
    }
}

impl IODevConsoleWriter {
    #[inline]
    pub fn write_fmt(args: core::fmt::Arguments) -> core::fmt::Result {
        core::fmt::Write::write_fmt(&mut Self, args)
    }

    #[inline]
    pub fn write_str(msg: &str) -> core::fmt::Result {
        write(msg)
    }

    #[inline]
    pub fn write_nl() -> core::fmt::Result {
        write("\n")
    }
}

#[inline]
fn write(msg: &str) -> core::fmt::Result {
    unsafe { iodev_console_write(msg.as_ptr() as _, msg.len() as u64) };
    Ok(())
}

#[macro_export]
macro_rules! println {
    () => { $crate::println!("") };
    ($($arg:tt)*) => {
        #[allow(unused_must_use)]
        {
            $crate::print::IODevConsoleWriter::write_fmt(format_args!($($arg)*));
            $crate::print::IODevConsoleWriter::write_nl();
        }
    };
}

#[macro_export]
macro_rules! print {
    ($($arg:tt)*) => {
        #[allow(unused_must_use)]
        {
            $crate::print::IODevConsoleWriter::write_fmt(format_args!($($arg)*));
        }
    };
}

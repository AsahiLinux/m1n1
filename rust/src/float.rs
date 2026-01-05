// SPDX-License-Identifier: GPL-2.0-only OR MIT

//! Basic soft floating-point support
//!
//! The GPU firmware requires a large number of power-related configuration values, many of which
//! are IEEE 754 32-bit floating point values. These values change not only between GPU/SoC
//! variants, but also between specific hardware platforms using these SoCs, so they must be
//! derived from device tree properties. There are many redundant values computed from the same
//! inputs with simple add/sub/mul/div calculations, plus a few values that are actually specific
//! to each individual device depending on its binning and fused voltage configuration, so it
//! doesn't make sense to store the final values to be passed to the firmware in the device tree.
//!
//! Therefore, we need a way to perform floating-point calculations in the kernel.
//!
//! Using the actual FPU from kernel mode is asking for trouble, since there is no way to bound
//! the execution of FPU instructions to a controlled section of code without outright putting it
//! in its own compilation unit, which is quite painful for Rust. Since these calculations only
//! have to happen at initialization time and there is no need for performance, let's use a simple
//! software float implementation instead.
//!
//! This implementation makes no attempt to be fully IEEE754 compliant, but it's good enough and
//! gives bit-identical results to macOS in the vast majority of cases, with one or two exceptions
//! related to slightly non-compliant rounding.

use core::ops;

/// An IEEE754-compatible floating point number implemented in software.
#[derive(Default, Debug, Copy, Clone)]
#[repr(transparent)]
pub struct F32(u32);

#[derive(Default, Debug, Copy, Clone)]
struct F32U {
    sign: bool,
    exp: i32,
    frac: i64,
}

impl F32 {
    #[allow(dead_code)]
    /// Convert a raw 32-bit representation into an F32
    pub(crate) const fn from_bits(u: u32) -> F32 {
        F32(u)
    }

    // Convert a `f32` value into an F32
    //
    // This must ONLY be used in const context. Use the `f32!{}` macro to do it safely.
    #[doc(hidden)]
    pub(crate) const fn from_f32(v: f32) -> F32 {
        // Replace with to_bits() after kernel Rust minreq is >= 1.83.0
        #[allow(clippy::transmute_float_to_int)]
        #[allow(unnecessary_transmutes)]
        // SAFETY: Transmuting f32 to u32 is always safe
        F32(unsafe { core::mem::transmute::<f32, u32>(v) })
    }

    // Convert an F32 into a `f32` value
    //
    // For testing only.
    #[doc(hidden)]
    #[cfg(test)]
    pub(crate) fn to_f32(self) -> f32 {
        f32::from_bits(self.0)
    }

    const fn unpack(&self) -> F32U {
        F32U {
            sign: self.0 & (1 << 31) != 0,
            exp: ((self.0 >> 23) & 0xff) as i32 - 127,
            frac: (((self.0 & 0x7fffff) | 0x800000) as i64) << 9,
        }
        .norm()
    }
}

/// Safely construct an `F32` out of a constant floating-point value.
///
/// This ensures that the conversion happens in const context, so no floating point operations are
/// emitted.
#[macro_export]
macro_rules! f32 {
    ([$($val:expr),*]) => {{
        [$(f32!($val)),*]
    }};
    ($val:expr) => {{
        const _K: $crate::float::F32 = $crate::float::F32::from_f32($val);
        _K
    }};
}

impl ops::Neg for F32 {
    type Output = F32;

    fn neg(self) -> F32 {
        F32(self.0 ^ (1 << 31))
    }
}

impl ops::Add<F32> for F32 {
    type Output = F32;

    fn add(self, rhs: F32) -> F32 {
        self.unpack().add(rhs.unpack()).pack()
    }
}

impl ops::Sub<F32> for F32 {
    type Output = F32;

    fn sub(self, rhs: F32) -> F32 {
        self.unpack().add((-rhs).unpack()).pack()
    }
}

impl ops::Mul<F32> for F32 {
    type Output = F32;

    fn mul(self, rhs: F32) -> F32 {
        self.unpack().mul(rhs.unpack()).pack()
    }
}

impl ops::Div<F32> for F32 {
    type Output = F32;

    fn div(self, rhs: F32) -> F32 {
        self.unpack().div(rhs.unpack()).pack()
    }
}

macro_rules! from_ints {
    ($u:ty, $i:ty) => {
        impl From<$i> for F32 {
            fn from(v: $i) -> F32 {
                F32U::from_i64(v as i64).pack()
            }
        }
        impl From<$u> for F32 {
            fn from(v: $u) -> F32 {
                F32U::from_u64(v as u64).pack()
            }
        }
    };
}

from_ints!(u8, i8);
from_ints!(u16, i16);
from_ints!(u32, i32);
from_ints!(u64, i64);

impl F32U {
    const INFINITY: F32U = f32!(f32::INFINITY).unpack();
    const NEG_INFINITY: F32U = f32!(f32::NEG_INFINITY).unpack();

    fn from_i64(v: i64) -> F32U {
        F32U {
            sign: v < 0,
            exp: 32,
            frac: v.abs(),
        }
        .norm()
    }

    fn from_u64(mut v: u64) -> F32U {
        let mut exp = 32;
        if v >= (1 << 63) {
            exp = 31;
            v >>= 1;
        }
        F32U {
            sign: false,
            exp,
            frac: v as i64,
        }
        .norm()
    }

    fn shr(&mut self, shift: i32) {
        if shift > 63 {
            self.exp = 0;
            self.frac = 0;
        } else {
            self.frac >>= shift;
        }
    }

    fn align(a: &mut F32U, b: &mut F32U) {
        if a.exp > b.exp {
            b.shr(a.exp - b.exp);
            b.exp = a.exp;
        } else {
            a.shr(b.exp - a.exp);
            a.exp = b.exp;
        }
    }

    fn mul(self, other: F32U) -> F32U {
        F32U {
            sign: self.sign != other.sign,
            exp: self.exp + other.exp,
            frac: ((self.frac >> 8) * (other.frac >> 8)) >> 16,
        }
    }

    fn div(self, other: F32U) -> F32U {
        if other.frac == 0 || self.is_inf() {
            if self.sign {
                F32U::NEG_INFINITY
            } else {
                F32U::INFINITY
            }
        } else {
            F32U {
                sign: self.sign != other.sign,
                exp: self.exp - other.exp,
                frac: ((self.frac << 24) / (other.frac >> 8)),
            }
        }
    }

    fn add(mut self, mut other: F32U) -> F32U {
        F32U::align(&mut self, &mut other);
        if self.sign == other.sign {
            self.frac += other.frac;
        } else {
            self.frac -= other.frac;
        }
        if self.frac < 0 {
            self.sign = !self.sign;
            self.frac = -self.frac;
        }
        self
    }

    const fn norm(mut self) -> F32U {
        let lz = self.frac.leading_zeros() as i32;
        if lz > 31 {
            self.frac <<= lz - 31;
            self.exp -= lz - 31;
        } else if lz < 31 {
            self.frac >>= 31 - lz;
            self.exp += 31 - lz;
        }

        if self.is_zero() {
            return F32U {
                sign: self.sign,
                frac: 0,
                exp: 0,
            };
        }
        self
    }

    const fn is_zero(&self) -> bool {
        self.frac == 0 || self.exp < -126
    }

    const fn is_inf(&self) -> bool {
        self.exp > 127
    }

    const fn pack(mut self) -> F32 {
        self = self.norm();
        if !self.is_zero() {
            self.frac += 0x100;
            self = self.norm();
        }

        if self.is_inf() {
            if self.sign {
                return f32!(f32::NEG_INFINITY);
            } else {
                return f32!(f32::INFINITY);
            }
        } else if self.is_zero() {
            if self.sign {
                return f32!(-0.0);
            } else {
                return f32!(0.0);
            }
        }

        F32(if self.sign { 1u32 << 31 } else { 0u32 }
            | ((self.exp + 127) as u32) << 23
            | ((self.frac >> 9) & 0x7fffff) as u32)
    }
}

// TODO: Fix failing cases
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_all() {
        fn add(a: f32, b: f32) {
            assert_eq!((F32::from_f32(a) + F32::from_f32(b)).to_f32(), a + b);
        }
        fn sub(a: f32, b: f32) {
            assert_eq!((F32::from_f32(a) - F32::from_f32(b)).to_f32(), a - b);
        }
        fn mul(a: f32, b: f32) {
            assert_eq!((F32::from_f32(a) * F32::from_f32(b)).to_f32(), a * b);
        }
        fn div(a: f32, b: f32) {
            assert_eq!((F32::from_f32(a) / F32::from_f32(b)).to_f32(), a / b);
        }

        fn test(a: f32, b: f32) {
            add(a, b);
            sub(a, b);
            mul(a, b);
            div(a, b);
        }

        test(1.123, 7.567);
        test(1.123, 1.456);
        test(7.567, 1.123);
        test(1.123, -7.567);
        test(1.123, -1.456);
        test(7.567, -1.123);
        test(-1.123, -7.567);
        test(-1.123, -1.456);
        test(-7.567, -1.123);
        test(1000.123, 0.001);
        test(1000.123, 0.0000001);
        test(0.0012, 1000.123);
        test(0.0000001, 1000.123);
        //test(0., 0.);
        test(0., 1.);
        test(1., 0.);
        test(1., 1.);
        test(2., f32::INFINITY);
        test(2., f32::NEG_INFINITY);
        test(f32::INFINITY, 2.);
        test(f32::NEG_INFINITY, 2.);
        test(f32::NEG_INFINITY, 2.);
        test(f32::MAX, 2.);
        test(f32::MIN, 2.);
        //test(f32::MIN_POSITIVE, 2.);
        //test(2., f32::MAX);
        //test(2., f32::MIN);
        test(2., f32::MIN_POSITIVE);
    }
}

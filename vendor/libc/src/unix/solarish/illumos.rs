s! {
    pub struct shmid_ds {
        pub shm_perm: ::ipc_perm,
        pub shm_segsz: ::size_t,
        pub shm_amp: *mut ::c_void,
        pub shm_lkcnt: ::c_ushort,
        pub shm_lpid: ::pid_t,
        pub shm_cpid: ::pid_t,
        pub shm_nattch: ::shmatt_t,
        pub shm_cnattch: ::c_ulong,
        pub shm_atime: ::time_t,
        pub shm_dtime: ::time_t,
        pub shm_ctime: ::time_t,
        pub shm_pad4: [i64; 4],
    }

    pub struct fil_info {
        pub fi_flags: ::c_int,
        pub fi_pos: ::c_int,
        pub fi_name: [::c_char; ::FILNAME_MAX as usize],
    }
}

pub const AF_LOCAL: ::c_int = 1; // AF_UNIX
pub const AF_FILE: ::c_int = 1; // AF_UNIX

pub const EFD_SEMAPHORE: ::c_int = 0x1;
pub const EFD_NONBLOCK: ::c_int = 0x800;
pub const EFD_CLOEXEC: ::c_int = 0x80000;

pub const TCP_KEEPIDLE: ::c_int = 34;
pub const TCP_KEEPCNT: ::c_int = 35;
pub const TCP_KEEPINTVL: ::c_int = 36;
pub const TCP_CONGESTION: ::c_int = 37;

pub const F_OFD_GETLK: ::c_int = 50;
pub const F_OFD_SETLKL: ::c_int = 51;
pub const F_OFD_SETLKW: ::c_int = 52;
pub const F_FLOCK: ::c_int = 55;
pub const F_FLOCKW: ::c_int = 56;

pub const FIL_ATTACH: ::c_int = 0x1;
pub const FIL_DETACH: ::c_int = 0x2;
pub const FIL_LIST: ::c_int = 0x3;
pub const FILNAME_MAX: ::c_int = 32;
pub const FILF_PROG: ::c_int = 0x1;
pub const FILF_AUTO: ::c_int = 0x2;
pub const FILF_BYPASS: ::c_int = 0x4;
pub const SOL_FILTER: ::c_int = 0xfffc;

pub const MR_HDR_AOUT: ::c_uint = 0x3;

extern "C" {
    pub fn eventfd(init: ::c_uint, flags: ::c_int) -> ::c_int;

    pub fn mincore(addr: ::caddr_t, len: ::size_t, vec: *mut ::c_char) -> ::c_int;

    pub fn pset_bind_lwp(
        pset: ::psetid_t,
        id: ::id_t,
        pid: ::pid_t,
        opset: *mut ::psetid_t,
    ) -> ::c_int;
    pub fn pset_getloadavg(pset: ::psetid_t, load: *mut ::c_double, num: ::c_int) -> ::c_int;

    pub fn preadv(fd: ::c_int, iov: *const ::iovec, iovcnt: ::c_int, offset: ::off_t) -> ::ssize_t;
    pub fn pwritev(fd: ::c_int, iov: *const ::iovec, iovcnt: ::c_int, offset: ::off_t)
        -> ::ssize_t;
    pub fn getpagesizes2(pagesize: *mut ::size_t, nelem: ::c_int) -> ::c_int;
}

ENTRY(_start)

/* Fake virtual load address for the mach-o */
_va_base = 0xFFFFFE0007004000;

_stack_size = 0x20000;

_max_payload_size = 64*1024*1024;

/* We are actually relocatable */
. = 0;

PHDRS
{
  hdr PT_LOAD;
  text PT_LOAD;
  rodata PT_LOAD;
  data PT_LOAD;
}

SECTIONS {
    _base = .;

    .header : {
        _mach_header = .;
        /* mach-o header */
        LONG(0xfeedfacf); /* magic */
        LONG(0x100000c); /* cputype */
        LONG(0x02); /* cputype */
        LONG(0x0c); /* filetype */
        LONG(6); /* ncmds */
        LONG(_cmd_end - _cmd_start); /* sizeofcmds */
        LONG(4); /* flags */
        LONG(0); /* reserved */

        _cmd_start = .;

        /* unix_thread (entrypoint) */
        LONG(0x5); /* type = UNIX_THREAD */
        LONG(0x120); /* cmdsize */
        LONG(6); /* ARM_THREAD64 */
        LONG(0x44); /* length */
        . += 32 * 8; /* useless registers */
        QUAD(_start + _va_off) /* pc */
        . += 8; /* useless registers */

        ASSERT(. - _cmd_start == 0x120, "Bad unix_thread structure");

        /* segment: mach-o structures */
        LONG(0x19); /* type = SEGMENT_64 */
        LONG(0x48); /* cmdsize */
        LONG(0x5244485f); /* segname = "_HDR" */
        . += 12;
        QUAD(ADDR(.header) + _va_off); /* vmaddr */
        QUAD(SIZEOF(.header)); /* vmsize */
        QUAD(ADDR(.header) - _base); /* fileoff */
        QUAD(SIZEOF(.header)); /* filesize */
        LONG(PROT_READ); /* maxprot */
        LONG(PROT_READ); /* initprot */
        LONG(0); /* nsects */
        LONG(0); /* flags */

        /* segment: text */
        LONG(0x19); /* type = SEGMENT_64 */
        LONG(0x48); /* cmdsize */
        LONG(0x54584554); /* segname = "TEXT" */
        . += 12;
        QUAD(ADDR(.init) + _va_off); /* vmaddr */
        QUAD(_text_size); /* vmsize */
        QUAD(ADDR(.init) - _base); /* fileoff */
        QUAD(_text_size); /* filesize */
        LONG(PROT_READ | PROT_EXECUTE); /* maxprot */
        LONG(PROT_READ | PROT_EXECUTE); /* initprot */
        LONG(0); /* nsects */
        LONG(0); /* flags */

        /* segment: rodata */
        LONG(0x19); /* type = SEGMENT_64 */
        LONG(0x48); /* cmdsize */
        LONG(0x41444F52); /* segname = "RODA" */
        . += 12;
        QUAD(ADDR(.rodata) + _va_off); /* vmaddr */
        QUAD(_rodata_end - ADDR(.rodata)); /* vmsize */
        QUAD(ADDR(.rodata) - _base); /* fileoff */
        QUAD(_rodata_end - ADDR(.rodata)); /* filesize */
        LONG(PROT_READ); /* maxprot */
        LONG(PROT_READ); /* initprot */
        LONG(0); /* nsects */
        LONG(0); /* flags */

        /* segment: data */
        LONG(0x19); /* type = SEGMENT_64 */
        LONG(0x48); /* cmdsize */
        LONG(0x41544144); /* segmname = "DATA" */
        . += 12;
        QUAD(ADDR(.data) + _va_off); /* vmaddr */
        QUAD(_data_size); /* vmsize */
        QUAD(ADDR(.data) - _base); /* fileoff */
        QUAD(SIZEOF(.data)); /* filesize */
        LONG(PROT_READ | PROT_WRITE); /* maxprot */
        LONG(PROT_READ | PROT_WRITE); /* initprot */
        LONG(0); /* nsects */
        LONG(0); /* flags */

        /* segment: payload */
        LONG(0x19); /* type = SEGMENT_64 */
        LONG(0x48); /* cmdsize */
        LONG(0x444C5950); /* segmname = "PYLD" */
        . += 12;
        QUAD(_end + _va_off); /* vmaddr */
        QUAD(_max_payload_size); /* vmsize */
        QUAD(_file_end - _base); /* fileoff */
        QUAD(_max_payload_size); /* filesize */
        LONG(PROT_READ | PROT_WRITE); /* maxprot */
        LONG(PROT_READ | PROT_WRITE); /* initprot */
        LONG(0); /* nsects */
        LONG(0); /* flags */

        _cmd_end = .;

        . = ALIGN(0x4000);
        _hdr_end = .;
    } :hdr
    _text_start = .;
    .init : ALIGN(0x4000) {
        *(.init)
        *(.init.*)
    } :text
    .text : ALIGN(0x4000) {
        *(.text)
        *(.text.*)
        . = ALIGN(8);
        *(.got.plt)
        . = ALIGN(0x4000);
    } :text
    _text_size = . - _text_start;
    .rodata : ALIGN(0x4000) {
        *(.rodata)
        *(.rodata.*)
        . = ALIGN(8);
    } :rodata
    .rela.dyn : {
        _rela_start = .;
        *(.rela)
        *(.rela.text)
        *(.rela.got)
        *(.rela.plt)
        *(.rela.bss)
        *(.rela.ifunc)
        *(.rela.text.*)
        *(.rela.data)
        *(.rela.data.*)
        *(.rela.rodata)
        *(.rela.rodata*)
        *(.rela.dyn)
        _rela_end = .;
        . = ALIGN(0x4000);
    } :rodata
    _rodata_end = .;
    _data_start = .;
    .data : ALIGN(0x4000) {
        *(.data)
        *(.data.*)
        . = ALIGN(8);
        _got_start = .;
        *(.got)
        _got_end = .;
        . = ALIGN(0x4000);
        _file_end = .;
    } :data
    .bss : ALIGN(0x4000) {
        _bss_start = .;
        *(.bss)
        *(.bss.*)
        *(.dynbss)
        *(COMMON)
        . = ALIGN(0x4000);
        _bss_end = .;
        PROVIDE(_stack_top = .);
        . += _stack_size;
        PROVIDE(_stack_bot = .);
        . = ALIGN(0x4000);
    } :data
    _data_size = . - _data_start;
    _end = .;
    _payload_start = .;
    _payload_end = . + _max_payload_size;

    .symtab 0 : { *(.symtab) }
    .strtab 0 : { *(.strtab) }
    .shstrtab 0 : { *(.shstrtab) }

    /DISCARD/ : {
        *(.discard)
        *(.discard.*)
        *(.interp .dynamic)
        *(.dynsym .dynstr .hash .gnu.hash)
        *(.eh_frame)
        *(.gnu.version*)
        *(.note*)
        *(.comment*)
    }

    .empty (NOLOAD) : {
        *(.plt) *(.plt.*) *(.iplt) *(.igot)
        *(.data.rel.ro)
    }
    ASSERT(SIZEOF(.empty) == 0, "Unexpected sections detected!")

    .got.plt (NOLOAD) : {
        *(.got.plt)
    }
    ASSERT(SIZEOF(.got.plt) == 0 || SIZEOF(.got.plt) == 0x18, "Unexpected GOT PLT detected!")

    .stab          0 : { *(.stab) }
    .stabstr       0 : { *(.stabstr) }
    .stab.excl     0 : { *(.stab.excl) }
    .stab.exclstr  0 : { *(.stab.exclstr) }
    .stab.index    0 : { *(.stab.index) }
    .stab.indexstr 0 : { *(.stab.indexstr) }
    .comment       0 : { *(.comment) }
    .debug          0 : { *(.debug) }
    .line           0 : { *(.line) }
    .debug_srcinfo  0 : { *(.debug_srcinfo) }
    .debug_sfnames  0 : { *(.debug_sfnames) }
    .debug_aranges  0 : { *(.debug_aranges) }
    .debug_pubnames 0 : { *(.debug_pubnames) }
    .debug_info     0 : { *(.debug_info .gnu.linkonce.wi.*) }
    .debug_abbrev   0 : { *(.debug_abbrev) }
    .debug_line     0 : { *(.debug_line) }
    .debug_frame    0 : { *(.debug_frame) }
    .debug_str      0 : { *(.debug_str) }
    .debug_loc      0 : { *(.debug_loc) }
    .debug_macinfo  0 : { *(.debug_macinfo) }
    .debug_weaknames 0 : { *(.debug_weaknames) }
    .debug_funcnames 0 : { *(.debug_funcnames) }
    .debug_typenames 0 : { *(.debug_typenames) }
    .debug_varnames  0 : { *(.debug_varnames) }
    .debug_pubtypes 0 : { *(.debug_pubtypes) }
    .debug_ranges   0 : { *(.debug_ranges) }
    .debug_types    0 : { *(.debug_types) }
    .debug_addr     0 : { *(.debug_addr) }
    .debug_line_str 0 : { *(.debug_line_str) }
    .debug_loclists 0 : { *(.debug_loclists) }
    .debug_macro    0 : { *(.debug_macro) }
    .debug_names    0 : { *(.debug_names) }
    .debug_rnglists 0 : { *(.debug_rnglists) }
    .debug_str_offsets 0 : { *(.debug_str_offsets) }
    .debug_sup      0 : { *(.debug_sup) }
}

PROT_READ = 0x01;
PROT_WRITE = 0x02;
PROT_EXECUTE = 0x04;

_va_off = _va_base - _base;

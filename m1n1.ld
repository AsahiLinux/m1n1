ENTRY(_start)

/* Fake virtual load address for the mach-o */
_va_base = 0xFFFFFE0007004000;

/* We are actually relocatable */
_base = 0;

_stack_size = 0x20000;

. = _base;

PHDRS
{
  hdr PT_LOAD;
  text PT_LOAD;
  rodata PT_LOAD;
  data PT_LOAD;
}

SECTIONS {
    .header : {
        _mach_header = .;
        /* mach-o header */
        LONG(0xfeedfacf); /* magic */
        LONG(0x100000c); /* cputype */
        LONG(0x02); /* cputype */
        LONG(0x0c); /* filetype */
        LONG(5); /* ncmds */
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

        _cmd_end = .;
        
        . = ALIGN(0x8000);
        _hdr_end = .;
    } :hdr
    _text_start = .;
    .init : ALIGN(0x8000) {
        *(.init)
        *(.init.*)
    } :text
    .text : ALIGN(0x8000) {
        *(.text)
        *(.text.*)
        . = ALIGN(8);
        *(.got.plt)
        . = ALIGN(0x8000);
    } :text
    _text_size = . - _text_start;
    .rodata : ALIGN(0x8000) {
        *(.rodata)
        *(.rodata.*)
        . = ALIGN(8);
    } :rodata
    .rela.dyn : {
        _rela_start = .;
        *(.rela)
        *(.rela.*)
        _rela_end = .;
        . = ALIGN(0x8000);
    } :rodata
    _rodata_end = .;
    _data_start = .;
    .data : ALIGN(0x8000) {
        *(.data)
        *(.data.*)
        . = ALIGN(8);
        _got_start = .;
        *(.got)
        _got_end = .;
        . = ALIGN(0x8000);
    } :data
    .bss : ALIGN(0x8000) {
        *(.bss)
        *(.bss.*)
        *(.dynbss)
        *(COMMON)
        . = ALIGN(0x8000);
        PROVIDE(_stack_top = .);
        . += _stack_size;
        PROVIDE(_stack_bot = .);
        . = ALIGN(0x8000);
    } :data
    _data_size = . - _data_start;
    _end = .;

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
}

PROT_READ = 0x01;
PROT_WRITE = 0x02;
PROT_EXECUTE = 0x04;

_va_off = _va_base - _base;

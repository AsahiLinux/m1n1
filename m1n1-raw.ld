ENTRY(_start)

_stack_size = 0x20000;

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
        _bss_end = .;
    } : data
    .stack : ALIGN(0x4000) {
        PROVIDE(_stack_top = .);
        . += _stack_size - 8;
        QUAD(0x544f424b43415453);
        PROVIDE(_stack_bot = .);
    } :data
    ASSERT(ALIGN(0x4000) == ., "Stack size is not aligned!")
    _data_size = . - _data_start;
    _end = .;
    _payload_start = .;

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

ARCH := aarch64-linux-gnu-

CFLAGS := -O2 -Wall -Wundef -Werror=strict-prototypes -fno-common -fno-PIE \
	-Werror=implicit-function-declaration -Werror=implicit-int \
	-Wsign-compare -Wunused-parameter -Wno-multichar \
	-ffreestanding -fpic -ffunction-sections -fdata-sections \
	-fno-stack-protector -mgeneral-regs-only -mstrict-align -march=armv8.2-a

LDFLAGS := -T m1n1.ld -EL -maarch64elf --no-undefined -X -Bsymbolic \
	-z notext --no-apply-dynamic-relocs --orphan-handling=warn --strip-debug \
	-z nocopyreloc --gc-sections -pie

MINILZLIB_OBJECTS := $(patsubst %,minilzlib/%, \
	dictbuf.o inputbuf.o lzma2dec.o lzmadec.o rangedec.o xzstream.o)

TINF_OBJECTS := $(patsubst %,tinf/%, \
	adler32.o crc32.o tinfgzip.o tinflate.o tinfzlib.o)

DLMALLOC_OBJECTS := dlmalloc/malloc.o

LIBFDT_OBJECTS := $(patsubst %,libfdt/%, \
	fdt_addresses.o fdt_empty_tree.o fdt_overlay.o fdt_ro.o fdt_rw.o fdt_strerror.o fdt_sw.o \
	fdt_wip.o fdt.o)

OBJECTS := adt.o bootlogo_128.o bootlogo_256.o chickens.o exception.o exception_asm.o fb.o \
	heapblock.o kboot.o main.o memory.o memory_asm.o payload.o proxy.o smp.o start.o startup.o \
	string.o uart.o uartproxy.o utils.o utils_asm.o vsprintf.o wdt.o $(MINILZLIB_OBJECTS) \
	$(TINF_OBJECTS) $(DLMALLOC_OBJECTS) $(LIBFDT_OBJECTS)

DTS := apple-j274.dts

BUILD_OBJS := $(patsubst %,build/%,$(OBJECTS))
DTBS := $(patsubst %.dts,build/dtb/%.dtb,$(DTS))

NAME := m1n1
TARGET := m1n1.macho

DEPDIR := build/.deps

ifeq ($(USE_CLANG),1)
CC := clang --target=$(ARCH)
AS := clang --target=$(ARCH)
LD := ld.lld
OBJCOPY := llvm-objcopy
else
CC := $(ARCH)gcc
AS := $(ARCH)gcc
LD := $(ARCH)ld
OBJCOPY := $(ARCH)objcopy
endif

.PHONY: all clean format
all: build/$(TARGET) $(DTBS)
clean:
	rm -rf build/*
format:
	clang-format -i src/*.c src/*.h

build/dtb/%.dtb: dts/%.dts
	@echo "  DTC   $@"
	@mkdir -p "$(dir $@)"
	@dtc -I dts $< >$@

build/%.o: src/%.S
	@echo "  AS    $@"
	@mkdir -p $(DEPDIR)
	@mkdir -p "$(dir $@)"
	@$(AS) -c $(CFLAGS) -Wp,-MMD,$(DEPDIR)/$(*F).d,-MQ,"$@",-MP -o $@ $<

build/%.o: src/%.c
	@echo "  CC    $@"
	@mkdir -p $(DEPDIR)
	@mkdir -p "$(dir $@)"
	@$(CC) -c $(CFLAGS) -Wp,-MMD,$(DEPDIR)/$(*F).d,-MQ,"$@",-MP -o $@ $<

build/$(NAME).elf: $(BUILD_OBJS) m1n1.ld
	@echo "  LD    $@"
	@$(LD) $(LDFLAGS) -o $@ $(BUILD_OBJS)

build/$(NAME).macho: build/$(NAME).elf
	@echo "  MACHO $@"
	@$(OBJCOPY) -O binary $< $@

build/build_tag.h:
	@echo "  TAG   $@"
	@echo "#define BUILD_TAG \"$$(git describe --always --dirty)\"" > $@

build/%.bin: data/%.png
	@echo "  IMG   $@"
	@convert $< -background black -flatten -depth 8 rgba:$@

build/%.o: build/%.bin
	@echo "  BIN   $@"
	@$(OBJCOPY) -I binary -B aarch64 -O elf64-littleaarch64 $< $@

build/main.o: build/build_tag.h src/main.c

-include $(DEPDIR)/*




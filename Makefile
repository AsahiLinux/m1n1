ARCH ?= aarch64-linux-gnu-
RUSTARCH ?= aarch64-unknown-none-softfloat

ifeq ($(shell uname),Darwin)
USE_CLANG ?= 1
$(info INFO: Building on Darwin)
ifeq ($(shell uname -p),arm)
TOOLCHAIN ?= /opt/homebrew/opt/llvm/bin/
else
TOOLCHAIN ?= /usr/local/opt/llvm/bin/
endif
$(info INFO: Toolchain path: $(TOOLCHAIN))
endif

ifeq ($(USE_CLANG),1)
CC := $(TOOLCHAIN)clang --target=$(ARCH)
AS := $(TOOLCHAIN)clang --target=$(ARCH)
LD := $(TOOLCHAIN)ld.lld
OBJCOPY := $(TOOLCHAIN)llvm-objcopy
CLANG_FORMAT := $(TOOLCHAIN)clang-format
EXTRA_CFLAGS ?=
else
CC := $(TOOLCHAIN)$(ARCH)gcc
AS := $(TOOLCHAIN)$(ARCH)gcc
LD := $(TOOLCHAIN)$(ARCH)ld
OBJCOPY := $(TOOLCHAIN)$(ARCH)objcopy
CLANG_FORMAT := clang-format
EXTRA_CFLAGS ?= -Wstack-usage=1024
endif

CFLAGS := -O2 -Wall -g -Wundef -Werror=strict-prototypes -fno-common -fno-PIE \
	-Werror=implicit-function-declaration -Werror=implicit-int \
	-Wsign-compare -Wunused-parameter -Wno-multichar \
	-ffreestanding -fpic -ffunction-sections -fdata-sections \
	-nostdinc -isystem $(shell $(CC) -print-file-name=include) -isystem sysinc \
	-fno-stack-protector -mgeneral-regs-only -mstrict-align -march=armv8.2-a \
	$(EXTRA_CFLAGS)

CFG :=
ifeq ($(RELEASE),1)
CFG += \#define RELEASE\\n
endif

# Required for no_std + alloc for now
export RUSTUP_TOOLCHAIN=nightly
RUST_LIB := librust.a
RUST_LIBS :=
ifeq ($(CHAINLOADING),1)
CFG += \#define CHAINLOADING\\n
RUST_LIBS += $(RUST_LIB)
endif

LDFLAGS := -EL -maarch64elf --no-undefined -X -Bsymbolic \
	-z notext --no-apply-dynamic-relocs --orphan-handling=warn \
	-z nocopyreloc --gc-sections -pie

MINILZLIB_OBJECTS := $(patsubst %,minilzlib/%, \
	dictbuf.o inputbuf.o lzma2dec.o lzmadec.o rangedec.o xzstream.o)

TINF_OBJECTS := $(patsubst %,tinf/%, \
	adler32.o crc32.o tinfgzip.o tinflate.o tinfzlib.o)

DLMALLOC_OBJECTS := dlmalloc/malloc.o

LIBFDT_OBJECTS := $(patsubst %,libfdt/%, \
	fdt_addresses.o fdt_empty_tree.o fdt_ro.o fdt_rw.o fdt_strerror.o fdt_sw.o \
	fdt_wip.o fdt.o)

OBJECTS := \
	adt.o \
	afk.o \
	aic.o \
	asc.o \
	bootlogo_128.o bootlogo_256.o \
	chainload.o \
	chainload_asm.o \
	chickens.o \
	clk.o \
	cpufreq.o \
	dart.o \
	dcp.o \
	dcp_iboot.o \
	display.o \
	exception.o exception_asm.o \
	fb.o font.o font_retina.o \
	gxf.o gxf_asm.o \
	heapblock.o \
	hv.o hv_vm.o hv_exc.o hv_vuart.o hv_wdt.o hv_asm.o hv_aic.o \
	i2c.o \
	iodev.o \
	iova.o \
	kboot.o \
	main.o \
	mcc.o \
	memory.o memory_asm.o \
	nvme.o \
	payload.o \
	pcie.o \
	pmgr.o \
	proxy.o \
	ringbuffer.o \
	rtkit.o \
	sart.o \
	smp.o \
	start.o \
	startup.o \
	string.o \
	tunables.o \
	tps6598x.o \
	uart.o \
	uartproxy.o \
	usb.o usb_dwc3.o \
	utils.o utils_asm.o \
	vsprintf.o \
	wdt.o \
	$(MINILZLIB_OBJECTS) $(TINF_OBJECTS) $(DLMALLOC_OBJECTS) $(LIBFDT_OBJECTS) $(RUST_LIBS)

BUILD_OBJS := $(patsubst %,build/%,$(OBJECTS))
NAME := m1n1
TARGET := m1n1.macho
TARGET_RAW := m1n1.bin

DEPDIR := build/.deps

.PHONY: all clean format update_tag update_cfg
all: update_tag update_cfg build/$(TARGET) build/$(TARGET_RAW)
clean:
	rm -rf build/*
format:
	$(CLANG_FORMAT) -i src/*.c src/*.h sysinc/*.h
format-check:
	$(CLANG_FORMAT) --dry-run --Werror src/*.c src/*.h sysinc/*.h
rustfmt:
	cd rust && cargo fmt
rustfmt-check:
	cd rust && cargo fmt --check

build/$(RUST_LIB): rust/src/* rust/*
	@echo "  RS    $@"
	@mkdir -p $(DEPDIR)
	@mkdir -p "$(dir $@)"
	@cargo build --target $(RUSTARCH) --lib --release --manifest-path rust/Cargo.toml --target-dir build
	@cp "build/$(RUSTARCH)/release/${RUST_LIB}" "$@"

build/%.o: src/%.S
	@echo "  AS    $@"
	@mkdir -p $(DEPDIR)
	@mkdir -p "$(dir $@)"
	@$(AS) -c $(CFLAGS) -MMD -MF $(DEPDIR)/$(*F).d -MQ "$@" -MP -o $@ $<

build/%.o: src/%.c
	@echo "  CC    $@"
	@mkdir -p $(DEPDIR)
	@mkdir -p "$(dir $@)"
	@$(CC) -c $(CFLAGS) -MMD -MF $(DEPDIR)/$(*F).d -MQ "$@" -MP -o $@ $<

build/$(NAME).elf: $(BUILD_OBJS) m1n1.ld
	@echo "  LD    $@"
	@$(LD) -T m1n1.ld $(LDFLAGS) -o $@ $(BUILD_OBJS)

build/$(NAME)-raw.elf: $(BUILD_OBJS) m1n1-raw.ld
	@echo "  LDRAW $@"
	@$(LD) -T m1n1-raw.ld $(LDFLAGS) -o $@ $(BUILD_OBJS)

build/$(NAME).macho: build/$(NAME).elf
	@echo "  MACHO $@"
	@$(OBJCOPY) -O binary --strip-debug $< $@

build/$(NAME).bin: build/$(NAME)-raw.elf
	@echo "  RAW   $@"
	@$(OBJCOPY) -O binary --strip-debug $< $@

update_tag:
	@echo "#define BUILD_TAG \"$$(git describe --always --dirty)\"" > build/build_tag.tmp
	@cmp -s build/build_tag.h build/build_tag.tmp 2>/dev/null || \
	( mv -f build/build_tag.tmp build/build_tag.h && echo "  TAG   build/build_tag.h" )

update_cfg:
	@echo -ne "$(CFG)" > build/build_cfg.tmp
	@cmp -s build/build_cfg.h build/build_cfg.tmp 2>/dev/null || \
	( mv -f build/build_cfg.tmp build/build_cfg.h && echo "  CFG   build/build_cfg.h" )

build/build_tag.h: update_tag
build/build_cfg.h: update_cfg

build/%.bin: data/%.png
	@echo "  IMG   $@"
	@convert $< -background black -flatten -depth 8 rgba:$@

build/%.o: build/%.bin
	@echo "  BIN   $@"
	@$(OBJCOPY) -I binary -B aarch64 -O elf64-littleaarch64 $< $@

build/%.bin: font/%.bin
	@echo "  CP    $@"
	@cp $< $@

build/main.o: build/build_tag.h build/build_cfg.h src/main.c
build/usb_dwc3.o: build/build_tag.h src/usb_dwc3.c
build/chainload.o: build/build_cfg.h src/usb_dwc3.c

-include $(DEPDIR)/*

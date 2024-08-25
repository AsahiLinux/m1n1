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

ifeq ($(shell uname -m),aarch64)
ARCH ?=
else
ARCH ?= aarch64-linux-gnu-
endif

ifeq ($(USE_CLANG),1)
CC := $(TOOLCHAIN)clang --target=$(ARCH)
AS := $(TOOLCHAIN)clang --target=$(ARCH)
LD := $(TOOLCHAIN)ld.lld
OBJCOPY := $(TOOLCHAIN)llvm-objcopy
CLANG_FORMAT ?= $(TOOLCHAIN)clang-format
EXTRA_CFLAGS ?=
else
CC := $(TOOLCHAIN)$(ARCH)gcc
AS := $(TOOLCHAIN)$(ARCH)gcc
LD := $(TOOLCHAIN)$(ARCH)ld
OBJCOPY := $(TOOLCHAIN)$(ARCH)objcopy
CLANG_FORMAT ?= clang-format
EXTRA_CFLAGS ?= -Wstack-usage=2048
endif

ifeq ($(V),)
QUIET := @
else
ifeq ($(V),0)
QUIET := @
else
QUIET :=
endif
endif

BASE_CFLAGS := -O2 -Wall -g -Wundef -Werror=strict-prototypes -fno-common -fno-PIE \
	-Werror=implicit-function-declaration -Werror=implicit-int \
	-Wsign-compare -Wunused-parameter -Wno-multichar \
	-ffreestanding -fpic -ffunction-sections -fdata-sections \
	-nostdinc -isystem $(shell $(CC) -print-file-name=include) -isystem sysinc \
	-fno-stack-protector -mstrict-align -march=armv8.2-a \
	$(EXTRA_CFLAGS)

CFLAGS := $(BASE_CFLAGS) -mgeneral-regs-only

CFG :=
ifeq ($(RELEASE),1)
CFG += RELEASE
endif

# Required for no_std + alloc for now
export RUSTC_BOOTSTRAP=1
RUST_LIB := librust.a
RUST_LIBS :=
ifeq ($(CHAINLOADING),1)
CFG += CHAINLOADING
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

DCP_OBJECTS := $(patsubst %,dcp/%, \
	dpav_ep.o \
	dptx_phy.o \
	dptx_port_ep.o \
	parser.o \
	system_ep.o)

OBJECTS := \
	adt.o \
	afk.o \
	aic.o \
	asc.o \
	bootlogo_128.o bootlogo_256.o \
	chainload.o \
	chainload_asm.o \
	chickens.o \
	chickens_avalanche.o \
	chickens_blizzard.o \
	chickens_cyclone_typhoon.o \
	chickens_everest.o \
	chickens_firestorm.o \
	chickens_hurricane_zephyr.o \
	chickens_monsoon_mistral.o \
	chickens_icestorm.o \
	chickens_sawtooth.o \
	chickens_twister.o \
	clk.o \
	cpufreq.o \
	dapf.o \
	dart.o \
	dcp.o \
	dcp_iboot.o \
	devicetree.o \
	display.o \
	exception.o exception_asm.o \
	fb.o font.o font_retina.o \
	firmware.o \
	gxf.o gxf_asm.o \
	heapblock.o \
	hv.o hv_vm.o hv_exc.o hv_vuart.o hv_wdt.o hv_asm.o hv_aic.o hv_virtio.o \
	i2c.o \
	iodev.o \
	iova.o \
	isp.o \
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
	sep.o \
	sio.o \
	smc.o \
	smp.o \
	start.o \
	startup.o \
	string.o \
	tunables.o tunables_static.o \
	tps6598x.o \
	uart.o \
	uartproxy.o \
	usb.o usb_dwc3.o \
	utils.o utils_asm.o \
	vsprintf.o \
	wdt.o \
	$(DCP_OBJECTS) \
	$(MINILZLIB_OBJECTS) $(TINF_OBJECTS) $(DLMALLOC_OBJECTS) $(LIBFDT_OBJECTS) $(RUST_LIBS)

FP_OBJECTS := \
	kboot_gpu.o \
	math/expf.o \
	math/exp2f_data.o \
	math/powf.o \
	math/powf_data.o

BUILD_OBJS := $(patsubst %,build/%,$(OBJECTS))
BUILD_FP_OBJS := $(patsubst %,build/%,$(FP_OBJECTS))
BUILD_ALL_OBJS := $(BUILD_OBJS) $(BUILD_FP_OBJS)
NAME := m1n1
TARGET := m1n1.macho
TARGET_RAW := m1n1.bin

DEPDIR := build/.deps

.PHONY: all clean format update_tag update_cfg invoke_cc
all: update_tag update_cfg build/$(TARGET) build/$(TARGET_RAW)
clean:
	rm -rf build/*
format:
	$(CLANG_FORMAT) -i src/*.c src/dcp/*.c src/math/*.c src/*.h src/dcp/*.h src/math/*.h sysinc/*.h
format-check:
	$(CLANG_FORMAT) --dry-run --Werror src/*.c src/dcp/*.c src/math/*.c src/*.h src/dcp/*.h src/math/*.h sysinc/*.h
rustfmt:
	cd rust && cargo fmt
rustfmt-check:
	cd rust && cargo fmt --check

build/$(RUST_LIB): rust/src/* rust/*
	$(QUIET)echo "  RS    $@"
	$(QUIET)mkdir -p $(DEPDIR)
	$(QUIET)mkdir -p "$(dir $@)"
	$(QUIET)cargo build --target $(RUSTARCH) --lib --release --manifest-path rust/Cargo.toml --target-dir build
	$(QUIET)cp "build/$(RUSTARCH)/release/${RUST_LIB}" "$@"

build/%.o: src/%.S
	$(QUIET)echo "  AS    $@"
	$(QUIET)mkdir -p $(DEPDIR)
	$(QUIET)mkdir -p "$(dir $@)"
	$(QUIET)$(AS) -c $(BASE_CFLAGS) -MMD -MF $(DEPDIR)/$(*F).d -MQ "$@" -MP -o $@ $<

$(BUILD_FP_OBJS): build/%.o: src/%.c
	$(QUIET)echo "  CC FP $@"
	$(QUIET)mkdir -p $(DEPDIR)
	$(QUIET)mkdir -p "$(dir $@)"
	$(QUIET)$(CC) -c $(BASE_CFLAGS) -MMD -MF $(DEPDIR)/$(*F).d -MQ "$@" -MP -o $@ $<

build/%.o: src/%.c
	$(QUIET)echo "  CC    $@"
	$(QUIET)mkdir -p $(DEPDIR)
	$(QUIET)mkdir -p "$(dir $@)"
	$(QUIET)$(CC) -c $(CFLAGS) -MMD -MF $(DEPDIR)/$(*F).d -MQ "$@" -MP -o $@ $<

# special target for usage by m1n1.loadobjs
invoke_cc:
	$(QUIET)$(CC) -c $(CFLAGS) -Isrc -o $(OBJFILE) $(CFILE)

build/$(NAME).elf: $(BUILD_ALL_OBJS) m1n1.ld
	$(QUIET)echo "  LD    $@"
	$(QUIET)$(LD) -T m1n1.ld $(LDFLAGS) -o $@ $(BUILD_ALL_OBJS)

build/$(NAME)-raw.elf: $(BUILD_ALL_OBJS) m1n1-raw.ld
	$(QUIET)echo "  LDRAW $@"
	$(QUIET)$(LD) -T m1n1-raw.ld $(LDFLAGS) -o $@ $(BUILD_ALL_OBJS)

build/$(NAME).macho: build/$(NAME).elf
	$(QUIET)echo "  MACHO $@"
	$(QUIET)$(OBJCOPY) -O binary --strip-debug $< $@

build/$(NAME).bin: build/$(NAME)-raw.elf
	$(QUIET)echo "  RAW   $@"
	$(QUIET)$(OBJCOPY) -O binary --strip-debug $< $@

update_tag:
	$(QUIET)mkdir -p build
	$(QUIET)./version.sh > build/build_tag.tmp
	$(QUIET)cmp -s build/build_tag.h build/build_tag.tmp 2>/dev/null || \
	( mv -f build/build_tag.tmp build/build_tag.h && echo "  TAG   build/build_tag.h" )

update_cfg:
	$(QUIET)mkdir -p build
	$(QUIET)for i in $(CFG); do echo "#define $$i"; done > build/build_cfg.tmp
	$(QUIET)cmp -s build/build_cfg.h build/build_cfg.tmp 2>/dev/null || \
	( mv -f build/build_cfg.tmp build/build_cfg.h && echo "  CFG   build/build_cfg.h" )

build/build_tag.h: update_tag
build/build_cfg.h: update_cfg

build/%.bin: data/%.bin
	$(QUIET)echo "  IMG   $@"
	$(QUIET)mkdir -p "$(dir $@)"
	$(QUIET)cp $< $@

build/%.o: build/%.bin
	$(QUIET)echo "  BIN   $@"
	$(QUIET)mkdir -p "$(dir $@)"
	$(QUIET)$(OBJCOPY) -I binary -B aarch64 -O elf64-littleaarch64 $< $@

build/%.bin: font/%.bin
	$(QUIET)echo "  CP    $@"
	$(QUIET)mkdir -p "$(dir $@)"
	$(QUIET)cp $< $@

build/main.o: build/build_tag.h build/build_cfg.h src/main.c
build/usb_dwc3.o: build/build_tag.h src/usb_dwc3.c
build/chainload.o: build/build_cfg.h src/usb_dwc3.c

-include $(DEPDIR)/*

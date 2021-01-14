ARCH := aarch64-linux-gnu-

CFLAGS := -O2 -Wall -Wundef -Werror=strict-prototypes -fno-common -fno-PIE \
	-Werror=implicit-function-declaration -Werror=implicit-int \
	-ffreestanding -mabi=lp64 -fpic -ffunction-sections -fdata-sections

LDFLAGS := -T m1n1.ld -EL -maarch64elf --no-undefined -X -shared -Bsymbolic \
	-z notext --no-apply-dynamic-relocs --orphan-handling=warn --strip-debug \
	-z nocopyreloc --gc-sections -pie

OBJECTS := bootlogo_128.o bootlogo_256.o fb.o main.o proxy.o start.o startup.o \
	string.o uart.o uartproxy.o utils.o utils_asm.o vsprintf.o

BUILD_OBJS := $(patsubst %,build/%,$(OBJECTS))
NAME := m1n1
TARGET := m1n1.macho

DEPDIR := build/.deps

CC := $(ARCH)gcc
AS := $(ARCH)gcc
LD := $(ARCH)ld
OBJCOPY := $(ARCH)objcopy

.PHONY: all clean format
all: build/$(TARGET)
clean:
	rm -rf build/*
format:
	clang-format -i src/*.c src/*.h

build/%.o: src/%.S
	@echo "  AS    $@"
	@mkdir -p $(DEPDIR)
	@$(AS) -c $(CFLAGS) -Wp,-MMD,$(DEPDIR)/$(*F).d,-MQ,"$@",-MP -o $@ $<

build/%.o: src/%.c
	@echo "  CC    $@"
	@mkdir -p $(DEPDIR)
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
	@$(OBJCOPY) -I binary -O elf64-littleaarch64 $< $@

build/main.o: build/build_tag.h src/main.c

-include $(DEPDIR)/*




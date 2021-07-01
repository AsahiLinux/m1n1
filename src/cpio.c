/* SPDX-License-Identifier: MIT */

#include <string.h>

#include "cpio.h"
#include "malloc.h"
#include "types.h"
#include "utils.h"

#define CPIO_MAX_FILES 20

#define CPIO_MODE_DIR  0040755
#define CPIO_MODE_FILE 0100644

#define CPIO_HEADER_MAGIC "070701"

struct cpio_header {
    char magic[6];
    char inode[8];
    char mode[8];
    char uid[8];
    char gid[8];
    char nlink[8];
    char mtime[8];
    char filesize[8];
    char devmajor[8];
    char devminor[8];
    char rdevmajor[8];
    char rdevminor[8];
    char namesize[8];
    char checksum[8];
} PACKED;

struct cpio {
    u32 n_files;
    struct {
        const u8 *ptr;
        size_t sz;
        const char *name;
        size_t name_sz;
        struct cpio_header hdr;
    } files[CPIO_MAX_FILES];
};

static char hex(u8 c)
{
    if (c <= 9)
        return '0' + c;
    return 'a' + c - 10;
}

static void write_hex32(char *p, u32 val)
{
    for (unsigned int i = 0; i < 8; ++i) {
        u32 shift = 28 - (4 * i);
        p[i] = hex((val >> shift) & 0xf);
    }
}

struct cpio *cpio_init(void)
{
    struct cpio *c = malloc(sizeof(*c));
    if (!c)
        return NULL;

    c->n_files = 0;
    return c;
}

int cpio_add(struct cpio *c, const char *name, u64 mode, const u8 *bfr, size_t sz)
{
    struct cpio_header *hdr;

    if (c->n_files >= CPIO_MAX_FILES) {
        printf("cpio: cannot add more than %d files.\n", CPIO_MAX_FILES);
        return -1;
    }

    c->files[c->n_files].ptr = bfr;
    c->files[c->n_files].sz = sz;
    c->files[c->n_files].name = name;
    c->files[c->n_files].name_sz = strlen(name) + 1;

    hdr = &c->files[c->n_files].hdr;
    memcpy(hdr->magic, CPIO_HEADER_MAGIC, 6);
    write_hex32(hdr->mode, mode);
    write_hex32(hdr->nlink, 1);
    write_hex32(hdr->filesize, sz);
    write_hex32(hdr->namesize, strlen(name) + 1);

    c->n_files++;

    return 0;
}

int cpio_add_file(struct cpio *c, const char *name, const u8 *bfr, size_t sz)
{
    return cpio_add(c, name, CPIO_MODE_FILE, bfr, sz);
}

int cpio_add_dir(struct cpio *c, const char *name)
{
    return cpio_add(c, name, CPIO_MODE_DIR, NULL, 0);
}

size_t cpio_get_size(struct cpio *c)
{
    size_t sz = 0;

    for (u32 i = 0; i < c->n_files; ++i) {
        sz += sizeof(struct cpio_header);
        sz += c->files[i].name_sz;
        sz = ALIGN_UP(sz, 4);
        sz += c->files[i].sz;
        sz = ALIGN_UP(sz, 4);
    }

    return sz;
}

size_t cpio_finalize(struct cpio *c, u8 *bfr, size_t bfr_size)
{
    size_t off = 0;

    if (cpio_get_size(c) > bfr_size)
        return 0;

    for (u32 i = 0; i < c->n_files; ++i) {
        memcpy(bfr + off, &c->files[i].hdr, sizeof(struct cpio_header));
        off += sizeof(struct cpio_header);

        memcpy(bfr + off, c->files[i].name, c->files[i].name_sz);
        off += c->files[i].name_sz;
        off = ALIGN_UP(off, 4);

        memcpy(bfr + off, c->files[i].ptr, c->files[i].sz);
        off += c->files[i].sz;
        off = ALIGN_UP(off, 4);
    }

    return off;
}

void cpio_free(struct cpio *c)
{
    free(c);
}

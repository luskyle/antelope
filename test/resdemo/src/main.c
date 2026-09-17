/* 资源打包演示：一个程序同时用三种形态携带资源并打印，验证各自的分发路径。

   1. data_files —— 目录分发：资源复制进输出目录，程序按"可执行文件所在目录"定位
      （/proc/self/exe，与当前工作目录无关，这是真实应用的做法）
   2. embed     —— 单文件分发：ld -r -b binary 嵌入的二进制经 _binary_ 符号直接访问
   3. gresource —— 单文件分发：glib-compile-resources 编译进二进制，
      ELF constructor 自动注册，GResource API 按前缀路径读取
*/

#define _GNU_SOURCE
#include <gio/gio.h>

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* embed：assets/payload.bin → _binary_assets_payload_bin_start/_end（路径转下划线） */
extern const unsigned char _binary_assets_payload_bin_start[];
extern const unsigned char _binary_assets_payload_bin_end[];

static char *exec_dir(void)
{
    char buf[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", buf, sizeof(buf) - 1);
    if (n < 0) {
        return strdup(".");
    }
    buf[n] = '\0';
    char *slash = strrchr(buf, '/');
    if (slash == NULL) {
        return strdup(".");
    }
    *slash = '\0';
    return strdup(buf[0] == '\0' ? "/" : buf);
}

static char *read_file(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (f == NULL) {
        return NULL;
    }
    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    rewind(f);
    char *data = malloc((size_t)len + 1);
    if (data != NULL) {
        size_t got = fread(data, 1, (size_t)len, f);
        data[got] = '\0';
    }
    fclose(f);
    return data;
}

static void print_payload_hex(const unsigned char *start, const unsigned char *end)
{
    size_t len = (size_t)(end - start);
    unsigned char checksum = 0;
    size_t show = len < 8 ? len : 8;

    printf("        payload: %zu bytes, first bytes: ", len);
    for (size_t i = 0; i < show; i++) {
        printf("%02x ", start[i]);
    }
    for (size_t i = 0; i < len; i++) {
        checksum = (unsigned char)(checksum + start[i]);
    }
    printf("  checksum: 0x%02x\n", checksum);
}

int main(void)
{
    printf("== Antelope 资源打包演示 ==\n\n");

    /* 1) data_files：目录分发（相对可执行文件定位，cwd 无关） */
    char *dir = exec_dir();
    if (dir == NULL) {
        return 1;
    }
    char banner_path[PATH_MAX];
    snprintf(banner_path, sizeof(banner_path), "%s/assets/banner.txt", dir);
    char *banner = read_file(banner_path);
    printf("[1] data_files  -> %s\n", banner_path);
    if (banner == NULL) {
        printf("    !! banner.txt 未找到（构建时由 data_files 复制）\n");
    } else {
        printf("    %s", banner);
    }
    free(banner);

    /* 2) embed：单文件分发（_binary_ 符号） */
    const unsigned char *start = _binary_assets_payload_bin_start;
    const unsigned char *end = _binary_assets_payload_bin_end;
    printf("[2] embed       -> _binary_assets_payload_bin_start\n");
    print_payload_hex(start, end);

    /* 3) gresource：单文件分发（ELF constructor 自动注册） */
    GError *error = NULL;
    GBytes *notes = g_resources_lookup_data("/com/antelope/demo/data/share/notes.txt",
                                            G_RESOURCE_LOOKUP_FLAGS_NONE, &error);
    printf("[3] gresource   -> /com/antelope/demo/data/share/notes.txt\n");
    if (notes == NULL) {
        printf("    !! notes.txt 未找到（构建时由 gresource 编入）: %s\n",
               error ? error->message : "unknown");
        if (error != NULL) {
            g_error_free(error);
        }
    } else {
        gsize size = 0;
        const char *data = g_bytes_get_data(notes, &size);
        printf("    %.*s", (int)size, data);
        g_bytes_unref(notes);
    }

    printf("\n== 分发形态说明 ==\n");
    printf("    data_files: 目录分发，改资源后 antel build 重新同步，可替换\n");
    printf("    embed/gresource: 单文件分发，拷走一个二进制就带全资源\n");

    free(dir);
    return 0;
}
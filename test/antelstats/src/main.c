/* antelstats 命令行工具：读 CSV，输出统计报表。
   library 经版本化共享库（libantelstats.so.1.0.0 + soname）链接；
   本文件会被三份配置编译：app（普通）、cov（coverage）、san（sanitize）。 */
#include "antelstats.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void print_usage(const char *prog)
{
    printf("用法: %s <data.csv> [--heap-bug]\n", prog);
    printf("  读取每行一个数值的 CSV，输出均值/标准差/中位数/极值。\n");
    printf("  --heap-bug  故意堆越界写（配合 sanitize: [\"address\"] 演示 ASan 捕获）\n");
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    int heap_bug = 0;
    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--heap-bug") == 0) {
            heap_bug = 1;
        }
    }

    if (heap_bug) {
        char *buf = malloc(4);
        if (buf == NULL) {
            return 1;
        }
        /* 越界写（UB）：读回让它至少可观察。注意 -O1 以上 GCC 会把 UB 访问
           优化掉、ASan 随之失效，所以消毒器构建必须关优化（san.json 用 -O0 -g） */
        buf[100] = 1;
        printf("heap-bug: byte100=%d\n", buf[100]);
        free(buf);
    }

    double *data = NULL;
    size_t count = 0;
    int rc = csv_read(argv[1], &data, &count);
    if (rc != 0) {
        fprintf(stderr, "读取 %s 失败（返回码 %d）\n", argv[1], rc);
        return 1;
    }
    if (count == 0) {
        fprintf(stderr, "%s 里没有数值\n", argv[1]);
        csv_free(data);
        return 1;
    }

    printf("== antelstats v%s ==\n", antelstats_version());
    printf("样本数   : %zu\n", count);
    printf("均值     : %.3f\n", stats_mean(data, count));
    printf("标准差   : %.3f\n", stats_stddev(data, count));
    printf("中位数   : %.3f\n", stats_median(data, count));
    printf("最小值   : %.3f\n", stats_min(data, count));
    printf("最大值   : %.3f\n", stats_max(data, count));

    csv_free(data);
    return 0;
}
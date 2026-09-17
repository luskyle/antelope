/* antelstats 命令行工具：内置样本数据，输出统计报表。
   库功能经版本化共享库（libantelstats.so.1.0.0 + soname）链接；
   运行不需要任何外部文件，数据内嵌在本源码里。 */
#include "antelstats.h"

#include <stdio.h>

static const double samples[] = {
    3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3,
    2, 3, 8, 4, 6, 2, 6, 4, 3, 3, 8, 3, 2, 7, 9, 5,
};

int main(void)
{
    size_t count = sizeof(samples) / sizeof(samples[0]);

    printf("== antelstats v%s ==\n", antelstats_version());
    printf("样本数   : %zu\n", count);
    printf("均值     : %.3f\n", stats_mean(samples, count));
    printf("标准差   : %.3f\n", stats_stddev(samples, count));
    printf("中位数   : %.3f\n", stats_median(samples, count));
    printf("最小值   : %.3f\n", stats_min(samples, count));
    printf("最大值   : %.3f\n", stats_max(samples, count));
    return 0;
}
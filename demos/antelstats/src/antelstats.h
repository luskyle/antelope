/* antelstats 公共头：统计分析库的接口 */
#ifndef ANTELSTATS_H
#define ANTELSTATS_H

#include <stddef.h>

/* ---- 统计（src/stats.c） ---- */
double stats_mean(const double *data, size_t count);
double stats_stddev(const double *data, size_t count);
double stats_min(const double *data, size_t count);
double stats_max(const double *data, size_t count);
double stats_median(const double *data, size_t count);

/* ---- CSV（src/csv.c） ---- */
/* 读取每行一个数值的 CSV 文件，返回值数组与长度；文件打不开返回 -1 */
int csv_read(const char *path, double **out, size_t *count);
void csv_free(double *data);

/* ---- 运行期版本信息（src/version.c，经版本化共享库导出） ---- */
const char *antelstats_version(void);

#endif
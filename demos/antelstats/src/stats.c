#include "antelstats.h"

#include <math.h>
#include <stdlib.h>

double stats_mean(const double *data, size_t count)
{
    double sum = 0.0;
    for (size_t i = 0; i < count; i++) {
        sum += data[i];
    }
    return count == 0 ? 0.0 : sum / (double)count;
}

double stats_stddev(const double *data, size_t count)
{
    if (count < 2) {
        return 0.0;
    }
    double mean = stats_mean(data, count);
    double sum_sq = 0.0;
    for (size_t i = 0; i < count; i++) {
        double diff = data[i] - mean;
        sum_sq += diff * diff;
    }
    return sqrt(sum_sq / (double)(count - 1));
}

double stats_min(const double *data, size_t count)
{
    if (count == 0) {
        return 0.0;
    }
    double value = data[0];
    for (size_t i = 1; i < count; i++) {
        if (data[i] < value) {
            value = data[i];
        }
    }
    return value;
}

double stats_max(const double *data, size_t count)
{
    if (count == 0) {
        return 0.0;
    }
    double value = data[0];
    for (size_t i = 1; i < count; i++) {
        if (data[i] > value) {
            value = data[i];
        }
    }
    return value;
}

static int double_cmp(const void *a, const void *b)
{
    double x = *(const double *)a;
    double y = *(const double *)b;
    return (x > y) - (x < y);
}

double stats_median(const double *data, size_t count)
{
    if (count == 0) {
        return 0.0;
    }
    double *sorted = malloc(count * sizeof(double));
    if (sorted == NULL) {
        return 0.0;
    }
    for (size_t i = 0; i < count; i++) {
        sorted[i] = data[i];
    }
    qsort(sorted, count, sizeof(double), double_cmp);

    double median = (count % 2 == 0)
        ? (sorted[count / 2 - 1] + sorted[count / 2]) / 2.0
        : sorted[count / 2];
    free(sorted);
    return median;
}
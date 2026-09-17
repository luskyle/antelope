#include "stats.h"

static int calls = 0;

double stats_sum(const double *values, int count)
{
    double total = 0.0;

    for (int i = 0; i < count; i++) {
        total += values[i];
    }
    calls++;

    return total;
}

double stats_mean(const double *values, int count)
{
    if (count <= 0) {
        return 0.0;
    }

    return stats_sum(values, count) / count;
}

int stats_calls(void)
{
    return calls;
}
#include <stdio.h>
#include <stdlib.h>

#include "stats.h"
#include "fmt.h"

int main(int argc, char **argv)
{
    double values[16];
    int count = 0;

    for (int i = 1; i < argc && count < 16; i++) {
        values[count++] = atof(argv[i]);
    }

    printf("antel cdemo %s\n", fmt_version());
    printf("sum  = %.2f\n", stats_sum(values, count));
    printf("mean = %.2f\n", stats_mean(values, count));
    return 0;
}
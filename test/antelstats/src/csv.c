#include "antelstats.h"

#include <stdio.h>
#include <stdlib.h>

int csv_read(const char *path, double **out, size_t *count)
{
    FILE *file = fopen(path, "r");
    if (file == NULL) {
        return -1;
    }

    double *buffer = NULL;
    size_t used = 0;
    size_t capacity = 0;
    double value;

    while (fscanf(file, "%lf", &value) == 1) {
        if (used == capacity) {
            size_t next = capacity == 0 ? 8 : capacity * 2;
            double *grown = realloc(buffer, next * sizeof(double));
            if (grown == NULL) {
                free(buffer);
                fclose(file);
                return -2;
            }
            buffer = grown;
            capacity = next;
        }
        buffer[used++] = value;
    }
    fclose(file);

    *out = buffer;
    *count = used;
    return 0;
}

void csv_free(double *data)
{
    free(data);
}
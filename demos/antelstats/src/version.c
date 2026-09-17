#include "antelstats.h"

const char *antelstats_version(void)
{
    /* 与 antel.json 的 version 保持一致；改动后 antel build 重编并重链接 */
    return "1.0.0";
}
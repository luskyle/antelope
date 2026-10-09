from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / ".antel" / "lvgl" / "lv_conf.h"
CONFIG = """\
#ifndef LV_CONF_H
#define LV_CONF_H

#define LV_COLOR_FORMAT_DEFAULT LV_COLOR_FORMAT_RGB565
#define LV_USE_OS 0
#define LV_USE_STDLIB_MALLOC LV_STDLIB_CLIB

#endif
"""


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(CONFIG, encoding="utf-8")


if __name__ == "__main__":
    main()

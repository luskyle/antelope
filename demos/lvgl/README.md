# LVGL 9.6

Fetches the LVGL `release/v9.6` branch and builds its portable core, upstream
examples, and upstream demos as Antel static-library targets. Target source
lists are maintained directly in the target JSON files; platform-specific
display/input drivers and optional third-party codec libraries are intentionally
excluded. This keeps the demo independent of a window system while covering
LVGL's core widgets, drawing, fonts, themes, examples, and demos.

Run from this directory. The initial fetch requires Git and network access;
building requires Python 3, a C compiler and `ar`:

```bash
antel fetch-ref -f static
antel rebuild -f static
antel rebuild -f shared
antel rebuild -f examples
antel rebuild -f demos
antel rebuild -f window
antel run -f window
```

The outputs are:

| Target | Antel config | Output |
| --- | --- | --- |
| `lvgl` static library | `static.json` | `.antel/build/lvgl_static/liblvgl.a` |
| `lvgl` shared library | `shared.json` | `.antel/build/lvgl_shared/liblvgl.so.9.6` |
| `lvgl_examples` archive | `examples.json` | `.antel/build/lvgl_examples_examples/liblvgl_examples.a` |
| `lvgl_demos` archive | `demos.json` | `.antel/build/lvgl_demos_demos/liblvgl_demos.a` |
| SDL2 window application | `window.json` | `.antel/build/lvgl_window_demo_window/lvgl_window_demo` |

Each target JSON declares the LVGL ref directly. Its `before_build` hook runs
`prepare_lv_conf.py`, which generates `.antel/lvgl/lv_conf.h` (RGB565 color
format, OS integration disabled, desktop libc heap allocator). The shared library uses SONAME
`liblvgl.so.9`. The current release branch produces 386 core objects, 326
example objects, and 84 demo objects. The examples and demos are archives, not
standalone executables; consumers link the desired archive with one of the
LVGL core libraries.

The window application introduces Antelope's JSON-driven build model through
three interactive pages: an overview of refs, `before_build`, incremental
compilation, and target types; a live, illustrative build-activity monitor; and
a widget gallery. The gallery demonstrates LVGL charts, bar indicators,
buttons, sliders, switches, checkboxes, event callbacks, timers, and custom
styles. The live-update switch pauses/resumes the metrics, and the slider
changes their refresh interval. The SDL2 development files and a working
desktop display are required. Press Escape or close the window to exit.

Upstream CMake also conditionally defines the `lvgl_thorvg` internal library
when ThorVG is enabled in the LVGL configuration. The current `lv_conf.h` keeps
that optional backend disabled. Enabling it and the upstream test suite requires
additional per-target configurations and dependencies; those are not part of
this portable-target demo.

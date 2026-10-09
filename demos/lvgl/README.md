# LVGL 9.6 with Antel

This demo fetches the official LVGL `release/v9.6` branch and builds its
portable core, upstream examples, and upstream demos using Antel. It
demonstrates how to compile a substantial third-party C library without
invoking CMake: each output is an Antel JSON target, source files are selected
in those target descriptions, and Antel handles compilation, archiving, and
linking. Platform-specific display/input drivers and optional third-party
codec libraries are excluded from the portable library targets.

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

`fetch-ref` clones LVGL into `.antel/refs/lvgl`; all generated configuration,
object files, archives, and executables stay under `.antel`. The `-f` value is the configuration filename without its `.json`
suffix. Re-run `antel build -f <target>` for an incremental build of a target
after editing it.

## Build targets

The outputs are:

| Target | Antel config | Output |
| --- | --- | --- |
| `lvgl` static library | `static.json` | `.antel/build/lvgl_static/liblvgl.a` |
| `lvgl` shared library | `shared.json` | `.antel/build/lvgl_shared/liblvgl.so.9.6` |
| `lvgl_examples` archive | `examples.json` | `.antel/build/lvgl_examples_examples/liblvgl_examples.a` |
| `lvgl_demos` archive | `demos.json` | `.antel/build/lvgl_demos_demos/liblvgl_demos.a` |
| SDL2 window application | `window.json` | `.antel/build/lvgl_window_demo_window/lvgl_window_demo` |

All four library/archive target JSON files declare the LVGL ref directly and
maintain their source selections as JSON; they do not run LVGL's CMake
configuration or generated build system. Each `before_build` hook runs
`prepare_lv_conf.py` to generate `.antel/lvgl/lv_conf.h`. This keeps the
generated header out of the source tree and enables RGB565, disables OS
integration, selects the desktop libc allocator, and enables Montserrat fonts
from 18px through 32px, with 18px as the default. The shared library uses
SONAME `liblvgl.so.9`. On the configured `release/v9.6` source list, the core
builds 386 objects, examples 326, and demos 84. Examples and demos are static
archives, not standalone applications; a consumer links them with an LVGL core
library.

The window target is a separate SDL2 consumer of the generated static library.
Build `static` before `window`; the window's `link_args` points directly to
`.antel/build/lvgl_static/liblvgl.a`. Its only project source is
`window_demo.c`; it uses the generated LVGL config and headers from the local
ref. Antel obtains SDL2 compile/link flags through `pkg-config`, so SDL2
development files, `pkg-config`, a C compiler, and a desktop display are
required. Run the application with `antel run -f window`, or invoke the output
binary directly.

## Window demo

The window is both an introduction to Antelope and a showcase of LVGL's
interface-building features. Its three pages are:

1. **Overview** — JSON-based target configuration, Git refs, `before_build`,
   incremental compilation, target types, an animated build activity chart,
   and a button/slider interaction.
2. **Build performance** — live illustrative CPU and memory indicators, a
   rolling line chart, and a summary of Antel capabilities. The metrics are
   simulated UI data, not measurements collected from the host build.
3. **LVGL component gallery** — interactive switch, checkbox, slider, reset
   button, color palette, and examples of LVGL charting, bars, event callbacks,
   timers, and custom styling. The switch pauses/resumes metric updates; the
   overview slider adjusts their refresh interval.

The application window is 1620x1020. LVGL renders the 1080x680 design surface
at 150% with object transforms; the text itself is rendered with Montserrat at
18px by default, 24px for section headings, and 32px for page headings. This
keeps the interface crisp instead of scaling a bitmap. Press Escape or close
the window to exit.

Upstream CMake also conditionally defines the `lvgl_thorvg` internal library
when ThorVG is enabled in the LVGL configuration. The current `lv_conf.h` keeps
that optional backend disabled. Enabling it and the upstream test suite requires
additional per-target configurations and dependencies; those are not part of
this portable-target demo.

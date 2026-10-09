# Examples & Screenshots

The example projects shipped with the repository live under `demos/` — all of them build and run for real. Below, each screenshot has its exact config next to it, so you can copy and reproduce. Configs are not limited to the name `antel.json`: `antel init` creates that file by default, and `-f` selects another JSON config. Upstream projects commonly use multiple configs for their libraries, tools, and tests. See the [success-case index](success-cases.md) for more projects.

## gtkcalc: GTK calculator (`pkg_config` integration) { #case-gtkcalc }

Location: `demos/gtkcalc/`. A calculator written with libadwaita (GTK 4), demonstrating the most common GUI project shape: **GUI + external library**. It never hand-writes `-I`/`-l` — everything comes from `pkg_config`.

![gtkcalc UI](images/demo_gtkcalc.png)

**antel.json** (`demos/gtkcalc/antel.json`):

```json
{
    "projectName": "gtkcalc",
    "target_type": "exe",
    "compiler": "gxx",
    "source": [
        "main.c"
    ],
    "exclude_source": [],
    "include_directories": [],
    "compile_args": [
        "-O2",
        "-Wall"
    ],
    "link_args": [],
    "report": false,
    "pkg_config": [
        "libadwaita-1"
    ]
}
```

**Config highlights**:

- `pkg_config: ["libadwaita-1"]`: at build time antel runs `pkg-config --cflags/--libs libadwaita-1` automatically, injecting `-I/usr/include/libadwaita-1` and friends into every compile unit and appending `-ladwaita-1 -lgtk-4 ...` to the link line. With the libadwaita dev package installed, one line of config is all it takes
- Install the dependency (Ubuntu 22.04):

  ```bash
  sudo apt install libadwaita-1-dev
  ```

- Build and run:

  ```bash
  cd demos/gtkcalc
  antel rebuild
  ./.antel/build/gtkcalc_antel/gtkcalc
  ```

- The program also takes `--auto-close N` (seconds) for unattended verification — e.g. `./.antel/build/gtkcalc_antel/gtkcalc --auto-close 3` in CI opens the window and exits on its own after 3 seconds

!!! note "libadwaita 1.1 API constraints (code already adapted)"
    This demo targets libadwaita 1.1 / GTK 4.6 as shipped with Ubuntu 22.04. Three pitfalls trip up newcomers, all commented in the source:

    1. `AdwApplicationWindow` has **no titlebar area** — the window buttons (close/minimize/maximize) come from an `AdwHeaderBar` at the top of the content; calling `gtk_window_set_titlebar` is rejected by libadwaita and crashes;
    2. Content must be set with `adw_application_window_set_content`; `gtk_window_set_child` is equally rejected;
    3. `g_application_run` parses and rejects unknown command-line options, so custom arguments (like `--auto-close`) must be stripped from argv first.

## resdemo: resource packaging (`data_files` / `gresource` / `embed`) { #case-resdemo }

Location: `demos/resdemo/`. One program carries resources in all three forms, and the UI itself is resource-driven — a complete tour of the distribution options:

- **data_files — directory distribution**: `assets/` is copied into the output directory and can be replaced at any time; the program locates it via `/proc/self/exe` (independent of the working directory)
- **gresource — single-file distribution**: the whole UI (`main.ui`), styles (`style.css`), icon (`logo.png`) and text (`notes.txt`) are compiled into the executable; GtkBuilder / CSS provider load them straight from the resource path
- **embed — single-file distribution**: `assets/payload.bin` is embedded into the ELF via `ld -r -b binary`; the program accesses it through `_binary_` symbols

![resdemo UI](images/demo_resdemo.png)

**antel.json** (`demos/resdemo/antel.json`):

```json
{
    "projectName": "resdemo",
    "target_type": "exe",
    "compiler": "gxx",
    "source": [
        "src/main.c"
    ],
    "exclude_source": [],
    "include_directories": [],
    "compile_args": [
        "-O2",
        "-Wall"
    ],
    "link_args": [],
    "report": false,
    "pkg_config": [
        "libadwaita-1"
    ],
    "data_files": [
        "assets"
    ],
    "gresource": "gresource.gresource.xml",
    "embed": [
        "assets/payload.bin"
    ]
}
```

**File layout**:

```text
demos/resdemo/
├── antel.json                 # config above
├── gresource.gresource.xml    # gresource manifest (prefix + file aliases)
├── assets/
│   ├── banner.txt             # copied by data_files; not referenced in the gresource XML
│   ├── logo.png               # referenced by gresource; also copied by data_files (harmless)
│   └── payload.bin            # embedded by embed; not referenced in the gresource XML
├── data/
│   ├── ui/main.ui             # GtkBuilder UI description (gresource)
│   ├── css/style.css          # UI styles (gresource)
│   └── share/notes.txt        # runtime text (gresource)
└── src/main.c                 # code reading all three forms
```

**gresource.gresource.xml**:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gresources>
  <gresource prefix="/com/antelope/demo">
    <file alias="ui/main.ui">data/ui/main.ui</file>
    <file alias="css/style.css">data/css/style.css</file>
    <file alias="img/logo.png">assets/logo.png</file>
    <file alias="share/notes.txt">data/share/notes.txt</file>
  </gresource>
</gresources>
```

**Trade-offs between the three forms**:

| Form | Distribution | Best for | Access from code |
| --- | --- | --- | --- |
| `data_files` | directory (resources sit next to the executable) | replaceable, large, hot-updatable resources | plain file read (located relative to `/proc/self/exe`) |
| `gresource` | single file (compiled into the binary) | GTK/GLib UI, styles, icons, text | `g_resources_lookup_data` / `gtk_builder_new_from_resource` |
| `embed` | single file (compiled into the binary) | any binary: firmware, fonts, keymaps, config | `_binary_<path with non-alnum→_>_start/_end/_size` symbols |

**Incremental behavior** (also the contract asserted in tests):

- edit `assets/banner.txt` → `antel build` re-syncs the copy
- edit `assets/payload.bin` → no compile unit goes stale, but the **resource change drives a relink** and the embedded content updates
- edit `data/css/style.css` or `data/share/notes.txt` → the gresource source is regenerated → the gresource unit recompiles → relink

**Build and run**:

```bash
cd demos/resdemo
antel rebuild
./.antel/build/resdemo_antel/resdemo
```

The switch at the bottom-left toggles dark/light theme (colors from `style.css` compiled in via gresource); the button on the right re-reads the `data_files` banner from disk — both interactions demonstrate "change a resource → build → the UI follows".

### Logs & build artifact analysis

Every stage of a build lands an auditable artifact, and `antel analyze` folds them all into one visual report. This is what the `demos/resdemo/.antel/build/resdemo_antel/log/` directory actually contains after a build:

| File | Contents |
| --- | --- |
| `resdemo.gxx` | the full compile commands executed (`gcc ... -I/usr/include/libadwaita-1 ... -o .antel/build/resdemo_antel/obj/src_main.o`) |
| `resdemo.make` | full output when running through the make backend (whether compiles were skipped/rebuilt) |
| `antel.mk` | internal rule file (generated — don't hand-edit; `make -f` reproduces the same compile) |
| `resdemo_link.sh` | the link script — linking *is* running this script; read `-ladwaita-1 -lgtk-4 ...` and all library deps ahead of time |
| `linkInfor` | full link output — the first place to look when linking fails |
| `hashes` | hash baseline recording every input file and its md5 from the last successful build |
| `report.html` | the visual analysis report produced by `antel analyze` (self-contained single file, open in a browser) |

**Walk through resdemo with the report** (run `antel analyze`, then open `.antel/build/resdemo_antel/report.html`):

- **Resources**: expanded to file level — 10 resource files, `data_files` 3 items (banner.txt/logo.png/payload.bin with type & size), `gresource` 6 items (XML + main.ui/style.css/logo.png/notes.txt + the generated `gresource.c` at 142.3 KB), `embed` 1 item (payload.bin 128 B + `_binary_assets_payload_bin` symbol); each resource carries a ✓ copied/embedded/compiled-in status
- **Symbol table**: 98 symbols classified by nm kind (functions/data/BSS/undefined references), `t exec_dir`, `T main` and friends each in their own chip
- **Compile flag statistics**: `-O2×2  -Wall×2` (plus -I header paths) — optimization level and warning switches at a glance
- **Dynamic dependencies**: NEEDED lists `libadwaita-1.so.0 libgtk-4.so.1 libgio-2.0.so.0 ...`, followed by the full ldd resolution (address and path per entry)
- **Incremental status**: whether a hash baseline exists, changed files, stale list — mirroring `log/hashes`, `log/hashes_diff`, `log/stale_files`
- **Header dependencies**: derived from `obj/*.o.d` — which headers `src/main.c` pulls in

**Troubleshooting path**: break the code → `antel rebuild` fails → look at the compile commands in `log/<project>.gxx` first, then the diagnostics summary in `report.html`; link failure → `log/linkInfor` plus the link script; incremental doubts → `log/hashes_diff` and `log/stale_files`. Every number is the output of a real tool (`file`/`nm`/`readelf`/`ldd`/`gcov`) and can be verified directly.

!!! note "Why incremental can be trusted"
    `glib-compile-resources` emits **byte-identical output** for identical input (verified), so the gresource source can safely join antel's hash baseline; `ld -r -b binary` symbol naming follows a deterministic rule: `assets/payload.bin` → `_binary_assets_payload_bin_start/_end/_size` (every non-alphanumeric character becomes `_`). Both rules are explicit contracts in DESIGN.md and the tests.

## libyaml: public upstream project (`ref`) { #case-libyaml }

Location: `demos/libyaml/`. This demo uses `ref` to fetch the public libyaml
`release/0.2.5` branch, then compiles its eight C translation units with
Antelope. The config explicitly lists source files and include paths. Version
macros that CMake normally puts in a generated header are passed directly to the
compiler, so no CMakeLists or generated header is needed.

The first build requires network access and Git:

```bash
cd demos/libyaml
antel rebuild
```

The upstream source is cached under `.antel/refs/libyaml`, and the static library
is written to `.antel/build/yaml_antel/libyaml.a`. `antel clean` preserves the reference
checkout.

## cJSON: public JSON library (`ref`) { #case-cjson }

Location: `demos/cjson/`. This demo fetches the public cJSON `master` branch
through `ref` and builds separate static/shared parser and JSON Utils libraries,
upstream Unity, `cJSON_test`, `parse_examples` and `old_utils_tests`: eight
targets, without a local entry point or a CMake invocation.

```bash
cd demos/cjson
antel fetch-ref
antel rebuild
for config in shared utils-static utils-shared unity demo parse-examples utils-tests; do
    antel rebuild -f "$config" || exit 1
done
ar t .antel/build/cjson_antel/libcjson.a
./.antel/build/cJSON_test_demo/cJSON_test
(cd .antel/build/parse_examples_parse-examples && ./parse_examples)
./.antel/build/old_utils_tests_utils-tests/old_utils_tests
```

The first run needs Git and network access. The source is cached under
`.antel/refs/cjson`; `antel rebuild` also downloads a missing reference before
compilation.
Fetch first so that `data_files` can deploy the upstream parsing fixtures.
Run the parsing executable from its output directory. The two test programs
verify 15 parsing cases and six Utils test groups, loading locally built shared
libraries through relative rpaths. Build configuration dependencies in the
order shown above. This is a representative subset, not the complete upstream
test or fuzzing suite. See
[`demos/cjson/README.md`](https://github.com/luskyle/antelope/blob/main/demos/cjson/README.md)
for the target list and version notes.

## libpng: static/shared targets (`ref`) { #case-libpng }

Location: `demos/libpng/`. This mirrors upstream CMake's default
`PNG_STATIC=ON` and `PNG_SHARED=ON` with `static.json` and `shared.json`. On
x86_64 the configs also enable
`PNG_INTEL_SSE_OPT` and compile the two SSE2 sources. `shared.json` links zlib
through `pkg_config`; consumers of the static archive must link zlib and libm.
`before_build` uses the upstream prebuilt config header and generates the ELF
version script with the C preprocessor and AWK; the libpng targets need no CMake.

See the [libpng case study](libpng-case-study.md) for generated files, the PNG
window application, and isolated installation and removal.

```bash
cd demos/libpng
antel fetch-ref -f static
python3 prepare_icc_fixture.py
antel rebuild -f static
antel rebuild -f shared
ar t .antel/build/png16_static/libpng16.a | wc -l
readelf -d .antel/build/png16_shared/libpng16.so.16.60.git | grep SONAME
```

Each library target contains 17 upstream objects. The shared artifact is
`libpng16.so.16.60.git` with SONAME `libpng16.so.16` and the usual symlinks. The
first build requires Git, Python 3, a C compiler, AWK, pkg-config, network access,
and zlib development files. `before_build` generates the config header and ELF
version script; Antel compiles the library targets.

Upstream CMake also registers six test executables and two tools. They have
separate Antel configs: `pngtest.json`, `pnggetset.json`, `pngvalid.json`,
`pngstest.json`, `pngunknown.json`, `pngimage.json`, `pngfix.json`, and
`png-fix-itxt.json`. Each links the shared target above:

```bash
for target in pngtest pnggetset pngvalid pngstest pngunknown pngimage pngfix png-fix-itxt; do
    antel rebuild -f "$target"
done
```

Representative runs use test inputs shipped in the fetched upstream tree:

```bash
./.antel/build/pngtest_pngtest/pngtest .antel/build/pngtest_pngtest/testdata/pngtest.png /tmp/png-roundtrip.png
./.antel/build/pnggetset_pnggetset/pnggetset
./.antel/build/pngvalid_pngvalid/pngvalid --gamma-16-to-8
./.antel/build/pngunknown_pngunknown/pngunknown --strict default=discard .antel/build/pngunknown_pngunknown/testdata/pngtest.png
./.antel/build/pngimage_pngimage/pngimage --list-combos --log .antel/build/pngimage_pngimage/testdata/pngsuite/basn0g08.png
./.antel/build/pngstest_pngstest/pngstest --log --tmpfile /tmp/ps- .antel/build/pngstest_pngstest/testdata/testpngs/gray-1.png
./.antel/build/pngfix_pngfix/pngfix --quiet .antel/build/pngfix_pngfix/testdata/pngtest.png
./.antel/build/png-fix-itxt_png-fix-itxt/png-fix-itxt < .antel/build/png-fix-itxt_png-fix-itxt/testdata/pngtest.png > /tmp/png-fixed.png
```

Four additional programs from `contrib/examples/` also have configs:
`example-iccfrompng`, `example-pngpixel`, `example-pngtopng`, and
`example-simpleover`.

```bash
for target in example-iccfrompng example-pngpixel example-pngtopng example-simpleover; do
    antel rebuild -f "$target"
done
./.antel/build/iccfrompng_example-iccfrompng/iccfrompng .antel/build/iccfrompng_example-iccfrompng/testdata/icc-profile.png
./.antel/build/pngpixel_example-pngpixel/pngpixel 0 0 .antel/build/pngpixel_example-pngpixel/testdata/pngtest.png
./.antel/build/pngtopng_example-pngtopng/pngtopng .antel/build/pngtopng_example-pngtopng/testdata/pngtest.png /tmp/pngtopng.png
./.antel/build/simpleover_example-simpleover/simpleover .antel/build/simpleover_example-simpleover/testdata/background.png /tmp/simpleover.png
```

## yaml-cpp: C++ YAML library (`ref`) { #case-yaml-cpp }

Location: `demos/yaml-cpp/`. The demo fetches yaml-cpp `master` and compiles the
upstream core and contrib sources as a C++11 static library, without a local
consumer.

```bash
cd demos/yaml-cpp
antel rebuild
ar t .antel/build/yaml-cpp_antel/libyaml-cpp.a | wc -l
```

The first build requires Git and network access.

## json-c: library, CLI and test targets (`ref` and Python feature probes) { #case-json-c }

Location: `demos/json-c/`. json-c needs platform-probed generated headers. Each
Antel configuration uses `before_build` to invoke `prepare_json_c.py`; the
script probes the host C compiler and writes the headers directly. No CMake
configuration or build is used. Antel builds the static/shared
libraries, the upstream `json_parse` app and three representative parser, JSON
Pointer and JSON Patch tests.

```bash
cd demos/json-c
antel fetch-ref
antel rebuild
for config in shared json-parse test-parse test-json-pointer test-json-patch; do
    antel rebuild -f "$config" || exit 1
done
ar t .antel/build/json-c_antel/libjson-c.a | wc -l
printf '{"library":"json-c","built_by":"Antel"}\n' | ./.antel/build/json_parse_json-parse/json_parse
TEST_PARSE_CHUNKSIZE=7 ./.antel/build/test_parse_test-parse/test_parse
./.antel/build/test_json_pointer_test-json-pointer/test_json_pointer
./.antel/build/test_json_patch_test-json-patch/test_json_patch .antel/build/test_json_patch_test-json-patch/testdata
```

Both libraries use the same 14 upstream translation units. Tests load the
locally built shared library through relative rpaths, and the JSON Patch fixtures
are deployed with `data_files`. See
[`demos/json-c/README.md`](https://github.com/luskyle/antelope/blob/main/demos/json-c/README.md)
for all targets.

## libuv: Linux event loop (`ref`) { #case-libuv }

Location: `demos/libuv/`. Upstream's default targets include shared `uv` and
static `uv_a` libraries; with tests enabled it also defines shared/static test
runners and a static benchmark runner. `prepare_libuv.py` selects Linux source
files and writes Antel configs; Antel handles compilation without invoking
CMake.

```bash
cd demos/libuv
antel fetch-ref
python3 prepare_libuv.py
antel rebuild
antel rebuild -f shared
antel rebuild -f tests-static
antel rebuild -f tests-shared
antel rebuild -f benchmarks
```

Outputs include `.antel/build/uv_antel/libuv.a`, versioned shared library
`.antel/build/uv_shared/libuv.so.1.0.0`, two test runners, and a benchmark runner.
The test config includes all 185 upstream test sources applicable to Linux.
Consumers of the static archive need pthread, dl, and rt.

## libgit2: large Git library (`ref` and Python-generated config) { #case-libgit2 }

Location: `demos/libgit2/`. `prepare_antelope.py` selects Linux sources,
generates the feature header and target configs, and Antel builds the upstream
static/shared libraries, CLI, `lg2` example, and two test runners. The build
does not invoke CMake; the tests use upstream Clar's Python generator.

```bash
cd demos/libgit2
antel fetch-ref -f generated
python3 prepare_antelope.py

antel rebuild -f generated       # static library
antel rebuild -f shared          # versioned shared library
antel rebuild -f cli             # git2 CLI
antel rebuild -f lg2             # upstream example tool
antel rebuild -f tests-libgit2   # offline libgit2 tests
antel rebuild -f tests-util      # utility tests

ar t .antel/build/git2_generated/libgit2.a | wc -l
readelf -d .antel/build/git2_shared/libgit2.so.1.9.0 | grep SONAME
./.antel/build/git2_cli/git2 version
ldd .antel/build/lg2_lg2/lg2 | grep libgit2
(cd .antel/build/libgit2_tests_tests-libgit2 && ./libgit2_tests)
(cd .antel/build/util_tests_tests-util && ./util_tests -v)
```

The archive contains 196 objects; the shared library has SONAME
`libgit2.so.1.9`. `lg2` uses a relative rpath to the shared library, while the
CLI and test runners link against the Antel-built static archive. The libgit2
test runner excludes online, stress, and performance tests. The build requires
Linux, Git, Python 3, OpenSSL/PCRE/zlib development packages, and pthreads. All
target configs declare the same `ref`, with the initial ref defined in
`generated.json`; a separate `refs.json` is not needed. See
[`demos/libgit2/README.md`](https://github.com/luskyle/antelope/blob/main/demos/libgit2/README.md)
for the full target details.

## antelstats: shared library & consumer { #case-antelstats }

Location: `demos/antelstats/`. A small statistics tool: the shared library `libantelstats` provides mean/stddev/median helpers, and the executable calls them to print a report. **Only two config files** — the library's production shape and the executable's consumer shape — nothing fancy; sample data is baked into `main.c`, so running needs no external input.

```text
demos/antelstats/
├── antel.json    # versioned shared lib libantelstats.so.1.0.0 (multi-file: stats/csv/version)
├── app.json      # executable: links by soname, loads via rpath
└── src/          # antelstats.h / stats.c / csv.c / version.c / main.c
```

**antel.json** (versioned shared library):

```json
{
    "projectName": "antelstats",
    "target_type": "shared",
    "compiler": "gxx",
    "source": ["src/stats.c", "src/csv.c", "src/version.c"],
    "include_directories": ["src"],
    "compile_args": ["-O2", "-Wall", "-fPIC"],
    "report": false,
    "version": "1.0.0"
}
```

The output directory holds `libantelstats.so.1.0.0` (the real file) plus two symlinks `libantelstats.so.1` and `libantelstats.so`; `readelf -d` shows `SONAME = libantelstats.so.1`.

**app.json** (executable consumer, linked and loaded by soname):

```json
{
    "projectName": "app",
    "target_type": "exe",
    "compiler": "gxx",
    "source": ["src/main.c"],
    "compile_args": ["-O2", "-Wall", "-Isrc"],
    "link_args": ["-L.antel/build/antelstats_antel", "-lantelstats"],
    "report": false,
    "rpath": ["$ORIGIN/../antelstats_antel"]
}
```

Key point: `.c` files inside `include_directories` participate in the build (by design), so a project consuming the library should **only use `-I` for headers and never point `include_directories` into the library source dir**, or the library gets statically recompiled into the consumer. The `$ORIGIN` in `rpath` expands to the executable's own directory at runtime, so `ldd` loads by SONAME:

```text
libantelstats.so.1 => .../.antel/build/antelstats_antel/libantelstats.so.1
```

Build & run (two commands, no external input):

```bash
cd demos/antelstats
antel rebuild                 # versioned shared library + symlinks
antel rebuild -f app && ./.antel/build/app_app/app          # embedded data prints the stats report
antel analyze -f app          # generate the visual report .antel/build/app_app/report.html
```

!!! note "How to use sanitize / coverage"
    This demo doesn't make separate configs for them — they are one- or two-line switches in any `antel.json`, already covered by `tests/test_sanitize_coverage.py`. When you need them, add `"sanitize": ["address"]` (when debugging memory issues remember to pair it with `-O0 -g`; above `-O1` GCC folds the undefined out-of-bounds access away and ASan never fires) or `"coverage": true` (run then `gcov` for the report).

!!! tip "Visual analysis report"
    `antel analyze` produces a self-contained `report.html` in the output directory — 10 analysis dimensions: artifacts, incremental status, compile flag statistics, resources, symbol table, header dependencies, size distribution, dynamic dependencies, compile commands, log inventory. Open it directly in a browser. The full resdemo effect with a block-by-block walkthrough lives in [Report Example](report.md); command usage in [Commands](commands.md).
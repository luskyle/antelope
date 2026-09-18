# Examples & Screenshots

The example projects shipped with the repository live under `demos/` — all of them build and run for real. Below, each screenshot has its exact config next to it, so you can copy and reproduce.

## gtkcalc: GTK calculator (`pkg_config` integration)

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
  ./gtkcalc_antel/gtkcalc
  ```

- The program also takes `--auto-close N` (seconds) for unattended verification — e.g. `./gtkcalc_antel/gtkcalc --auto-close 3` in CI opens the window and exits on its own after 3 seconds

!!! note "libadwaita 1.1 API constraints (code already adapted)"
    This demo targets libadwaita 1.1 / GTK 4.6 as shipped with Ubuntu 22.04. Three pitfalls trip up newcomers, all commented in the source:

    1. `AdwApplicationWindow` has **no titlebar area** — the window buttons (close/minimize/maximize) come from an `AdwHeaderBar` at the top of the content; calling `gtk_window_set_titlebar` is rejected by libadwaita and crashes;
    2. Content must be set with `adw_application_window_set_content`; `gtk_window_set_child` is equally rejected;
    3. `g_application_run` parses and rejects unknown command-line options, so custom arguments (like `--auto-close`) must be stripped from argv first.

## resdemo: resource packaging (`data_files` / `gresource` / `embed`)

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
./resdemo_antel/resdemo
```

The switch at the bottom-left toggles dark/light theme (colors from `style.css` compiled in via gresource); the button on the right re-reads the `data_files` banner from disk — both interactions demonstrate "change a resource → build → the UI follows".

### Logs & build artifact analysis

Every stage of a build lands an auditable artifact, and `antel analyze` folds them all into one visual report. This is what the `demos/resdemo/resdemo_antel/log/` directory actually contains after a build:

| File | Contents |
| --- | --- |
| `resdemo.gxx` | the full compile commands executed (`gcc ... -I/usr/include/libadwaita-1 ... -o resdemo_antel/obj/src_main.o`) |
| `resdemo.make` | full output when running through the make backend (whether compiles were skipped/rebuilt) |
| `antel.mk` | internal rule file (generated — don't hand-edit; `make -f` reproduces the same compile) |
| `resdemo_link.sh` | the link script — linking *is* running this script; read `-ladwaita-1 -lgtk-4 ...` and all library deps ahead of time |
| `linkInfor` | full link output — the first place to look when linking fails |
| `hashes` | hash baseline recording every input file and its md5 from the last successful build |
| `report.html` | the visual analysis report produced by `antel analyze` (self-contained single file, open in a browser) |

**Walk through resdemo with the report** (run `antel analyze`, then open `resdemo_antel/report.html`):

- **Resources**: expanded to file level — 10 resource files, `data_files` 3 items (banner.txt/logo.png/payload.bin with type & size), `gresource` 6 items (XML + main.ui/style.css/logo.png/notes.txt + the generated `gresource.c` at 142.3 KB), `embed` 1 item (payload.bin 128 B + `_binary_assets_payload_bin` symbol); each resource carries a ✓ copied/embedded/compiled-in status
- **Symbol table**: 98 symbols classified by nm kind (functions/data/BSS/undefined references), `t exec_dir`, `T main` and friends each in their own chip
- **Compile flag statistics**: `-O2×2  -Wall×2` (plus -I header paths) — optimization level and warning switches at a glance
- **Dynamic dependencies**: NEEDED lists `libadwaita-1.so.0 libgtk-4.so.1 libgio-2.0.so.0 ...`, followed by the full ldd resolution (address and path per entry)
- **Incremental status**: whether a hash baseline exists, changed files, stale list — mirroring `log/hashes`, `log/hashes_diff`, `log/stale_files`
- **Header dependencies**: derived from `obj/*.o.d` — which headers `src/main.c` pulls in

**Troubleshooting path**: break the code → `antel rebuild` fails → look at the compile commands in `log/<project>.gxx` first, then the diagnostics summary in `report.html`; link failure → `log/linkInfor` plus the link script; incremental doubts → `log/hashes_diff` and `log/stale_files`. Every number is the output of a real tool (`file`/`nm`/`readelf`/`ldd`/`gcov`) and can be verified directly.

!!! note "Why incremental can be trusted"
    `glib-compile-resources` emits **byte-identical output** for identical input (verified), so the gresource source can safely join antel's hash baseline; `ld -r -b binary` symbol naming follows a deterministic rule: `assets/payload.bin` → `_binary_assets_payload_bin_start/_end/_size` (every non-alphanumeric character becomes `_`). Both rules are explicit contracts in DESIGN.md and the tests.

## antelstats: shared library & consumer

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
    "link_args": ["-Lantelstats_antel", "-lantelstats"],
    "report": false,
    "rpath": ["$ORIGIN/../antelstats_antel"]
}
```

Key point: `.c` files inside `include_directories` participate in the build (by design), so a project consuming the library should **only use `-I` for headers and never point `include_directories` into the library source dir**, or the library gets statically recompiled into the consumer. The `$ORIGIN` in `rpath` expands to the executable's own directory at runtime, so `ldd` loads by SONAME:

```text
libantelstats.so.1 => .../antelstats_antel/libantelstats.so.1
```

Build & run (two commands, no external input):

```bash
cd demos/antelstats
antel rebuild                 # versioned shared library + symlinks
antel rebuild -f app && ./app_app/app          # embedded data prints the stats report
antel analyze -f app          # generate the visual report app_app/report.html
```

!!! note "How to use sanitize / coverage"
    This demo doesn't make separate configs for them — they are one- or two-line switches in any `antel.json`, already covered by `tests/test_sanitize_coverage.py`. When you need them, add `"sanitize": ["address"]` (when debugging memory issues remember to pair it with `-O0 -g`; above `-O1` GCC folds the undefined out-of-bounds access away and ASan never fires) or `"coverage": true` (run then `gcov` for the report).

!!! tip "Visual analysis report"
    `antel analyze` produces a self-contained `report.html` in the output directory — 10 analysis dimensions: artifacts, incremental status, compile flag statistics, resources, symbol table, header dependencies, size distribution, dynamic dependencies, compile commands, log inventory. Open it directly in a browser. The full resdemo effect with a block-by-block walkthrough lives in [Report Example](report.md); command usage in [Commands](commands.md).
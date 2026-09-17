# Antelope

[![CI](https://github.com/luskyle/antelope/actions/workflows/ci.yml/badge.svg)](https://github.com/luskyle/antelope/actions/workflows/ci.yml)
[![Pages](https://github.com/luskyle/antelope/actions/workflows/pages.yml/badge.svg)](https://luskyle.github.io/antelope/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](<https://img.shields.io/badge/python-3.9%20%7C%203.11%20%7C%203.13-blue.svg>)](https://www.python.org/)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/logo-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/images/logo.svg">
  <img src="docs/images/logo.png" alt="Antelope" width="180">
</picture>

*A small and nimble C/C++ build tool. Point it at an `antel.json` and it turns your project into a static library, shared library, or executable — no Makefile to maintain, no extra build language to learn.*

> When I first started working with C/C++, I poured a lot of effort into mastering cmake, make, and gcc — and even more into finally sorting out how they relate to each other. In time I could use them fluently to build my projects. Meson avoided writing cmake, sure, but it didn't actually lighten the configuration burden. I'm here to write programs, yet I kept spending serious energy on things that have nothing to do with the code itself. Every time I thought about starting a C/C++ project, it hurt.
>
> Why should it be this hard? Why can't compiling a C/C++ project be as simple as writing a JSON file? That's how Antelope was born. Around 2022, Antelope already had a working prototype — but many features were still missing, and life kept getting in the way, so I couldn't find the time to finish it properly. As coding agents grew more powerful, I finally broke free from the heavy "old-school programming." With an agent's help, my ideas got built in no time.
>
> By writing a single JSON file, you can say goodbye to cmake. Stop worrying about the complicated build backend — leave it to Antelope. Beyond compiling and linking, it generates a visual project analysis report from 10 different angles, so you truly understand what your project produces.
>
> — Author: luskyle

## Features

- **Configuration is the build script**: compiler flags, linker flags, target type and toolchain are all declared in `antel.json`, committed and reviewed alongside the source code
- **Parallel builds**: compile units are built in parallel by default (`jobs` is tunable), preferring the `make` tool as the executor (`backend: auto`, falling back to the built-in executor when `make` is missing — antel still decides *what* to compile); `compile_commands.json` is emitted for clangd and friends
- **Dependency-based incremental builds**: every compile unit records `-MMD` dependencies, so a header change rebuilds only the affected sources; missing objects or dep files are rebuilt automatically
- **Aggregated diagnostics**: parallel compile output is captured per unit — success prints just a warning count, failure replays each file's diagnostics grouped and counted instead of being drowned in interleaved output
- **Visual analysis report**: `report: true` or `antel analyze` produces a self-contained `report.html` covering artifacts, incremental state, compiler flags, symbols, header dependencies, size distribution, dynamic dependencies and log inventory — open it in any browser
- **Third-party libraries without copying flags**: `pkg_config: ["libcurl"]` injects `pkg-config`'s `--cflags/--libs` automatically, no hand-written `-I`/`-l`
- **One-click resource packaging**: `data_files` (copied into the output dir), `gresource` (GLib resources compiled into the binary), `embed` (any binary embedded via `ld -r -b binary`) — directory distribution or single-file distribution; resource changes trigger recompilation/relinking automatically
- **Versioned shared libraries**: `version` / `soname` / `rpath` produce `libX.so.<version>` plus symlinks; consumers link against the SONAME and load it via `$ORIGIN` rpath
- **Sanitizers & coverage**: `sanitize: ["address", "undefined"]` and `coverage: true` inject the flags in one line; run the binary and `gcov` produces a coverage report
- **Fail fast**: a non-zero exit from compiling, linking, analyzing or running stops the build and exits non-zero — failure is never mistaken for success
- **Traceable artifacts**: every executed compile command and link script lands in `log/`, with symbol tables, dynamic dependencies and other analysis for later audit

## Install

```bash
python3 antelope_install.py
```

## Quick start

```bash
antel init       # interactively generate antel.json
antel rebuild    # full build from scratch
antel build      # build only what changed
antel run        # run the produced executable
antel analyze    # generate report.html visual analysis
```

## Commands

| Command       | What it does                                                            |
| ------------- | ----------------------------------------------------------------------- |
| init          | interactively generate antel.json                                       |
| build         | build the changed parts                                                 |
| sync-baseline | refresh the hash baseline without compiling (align bookkeeping after hand-running a rule file) |
| rebuild       | rebuild everything, whether it was built before or not                  |
| clean         | remove all build output, intermediates and targets                      |
| link          | link only, without compiling                                            |
| analyze       | generate the visual analysis report `report.html`                       |
| run           | run the produced executable                                             |

All commands except `init` accept `--file` / `-f` to select a config file (default `antel`, i.e. `antel.json`).

## Compiler support

| compiler | driver        | static lib | shared lib / executable   |
| -------- | ------------- | ---------- | ------------------------- |
| gxx      | gcc/g++       | ✓          | g++ -shared / g++ -s      |
| llvm     | clang         | ✓          | clang++ (untested)        |
| msvc     | cl            | ✓          | not implemented, errors out |

## Documentation

Full documentation lives at [https://luskyle.github.io/antelope/](https://luskyle.github.io/antelope/):

| Page                                                                  | Contents                                                                    |
| --------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| [Quick Start](https://luskyle.github.io/antelope/en/quick-start/)      | install, init, minimal config, build & run                                  |
| [Configuration](https://luskyle.github.io/antelope/en/configuration/)  | every antel.json field (incl. pkg_config / data_files / gresource / embed)  |
| [Examples](https://luskyle.github.io/antelope/en/examples/)            | full configs and running results of the demos                               |
| [Commands](https://luskyle.github.io/antelope/en/commands/)            | command parameters, behavior and exit codes                                 |
| [Incremental Build](https://luskyle.github.io/antelope/en/incremental-build/) | when things rebuild, how the hash baseline and dep files work        |
| [Compilers](https://luskyle.github.io/antelope/en/compilers/)          | gxx / llvm / msvc support and target types                                  |
| [Development](https://luskyle.github.io/antelope/en/development/)      | testing, packaging, release flow and workflows                               |

Built-in examples under `demos/` (all buildable and runnable): `helloworld` (single file), `cdemo` (multi-file), `gtkcalc` (libadwaita calculator), `resdemo` (resource packaging GUI), `antelstats` (versioned shared library + sanitizer/coverage).

## Development

```bash
python3 -m pip install -e '.[test]'
python3 -m pytest
```

If a third-party pytest plugin interferes at startup (for example the `launch_testing` shipped by ROS 2), use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest` instead.

Preview the docs site locally:

```bash
python3 -m pip install -r docs/requirements.txt
zensical serve
```

## License

[Apache-2.0](LICENSE)

The project logo uses the goat glyph from Microsoft [Fluent Emoji](https://github.com/microsoft/fluentui-emoji) (MIT, sourced from the fluent-emoji-flat collection via Iconify). Files live under `docs/images/`: `logo.svg` and `logo-dark.svg` are the light- and dark-background variants, `favicon.svg` is the site icon (with an embedded `prefers-color-scheme` dark branch); the license text is in `LICENSE-fluent-emoji.txt`.
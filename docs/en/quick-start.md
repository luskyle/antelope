# Quick Start

## Installation

```bash
python3 antelope_install.py
```

The install script builds a wheel and installs it with `sudo pip` into the system interpreter's executable path, leaving you with the `antel` command. If you'd rather not touch the system environment, you can also install it in a virtual environment:

```bash
python3 -m pip install .
```

Requires Python 3.8 or later. The runtime dependencies `hash_calc`, `alive_progress`, `prompt_toolkit`, and `click` are resolved automatically by pip.

## Initializing the configuration

Run this in your project's source directory:

```bash
antel init
```

`init` walks you through a series of prompts asking for the configuration file name, project name, target type, and compiler type, then generates `antel.json`. The default compile arguments template already includes `-fPIC`, so it works for shared libraries out of the box.

## Filling in antel.json

A minimal working configuration looks like this:

```json
{
  "projectName": "helloworld",
  "target_type": "exe",
  "compiler": "gxx",
  "source": ["helloworld.c"],
  "exclude_source": [],
  "include_directories": ["include"],
  "compile_args": ["-std=c++17", "-w", "-Os", "-fPIC"],
  "link_args": ["-lm"],
  "report": false
}
```

See the [Configuration](configuration.md) reference for what each field means; `source` and `include_directories` are the starting points for incremental builds.

## Building and running

```bash
antel rebuild    # full rebuild — use it the first time or to force a rebuild
antel build      # build only the parts that changed
antel run        # run the built executable (exe targets only)
```

Build output goes under `./<project-name>_<config-file-name>/`; with the configuration above you'll get:

```text
helloworld_antel/
├── helloworld          # built target
├── obj/                # object files and dependency files
│   ├── helloworld.o
│   └── helloworld.o.d
└── log/                # compile commands, link scripts, hash baseline, symbol analysis
```

## Next steps

- Want to understand "when and why things get rebuilt" → [Incremental Build](incremental-build.md)
- Need a static or shared library → [Configuration](configuration.md) and [Compiler Support](compilers.md)
- Want third-party libraries or bundled runtime resources → `pkg_config` / `data_files` / `gresource` / `embed` in the [Configuration](configuration.md) reference
- Curious what a complete, runnable project looks like → [Examples](examples.md) (GTK calculator, resource packaging demo)
- Plan to hook it into CI or scripts → the exit-code conventions in [Commands](commands.md)
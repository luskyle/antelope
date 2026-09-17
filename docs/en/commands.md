# Command Reference

```text
用法：antel [OPTIONS] COMMAND [ARGS]...
```

| Command | Purpose | Supports `-f` |
| ------- | ------- | -------------- |
| `init`  | Interactively generate `antel.json` | No |
| `build` | Build the changed parts of the project | Yes |
| `sync-baseline` | Only refresh the hash baseline without compiling (to realign bookkeeping after manually running internal rule files) | Yes |
| `rebuild` | Rebuild the project regardless of whether it has been built before | Yes |
| `clean` | Remove build outputs, including all intermediate files and generated targets | Yes |
| `link`  | Link only, without compiling | Yes |
| `analyze` | Generate a visual analysis report `report.html` | Yes |
| `run`   | Run the compiled result | Yes |

All commands except `init` accept `--file` / `-f` to specify the configuration file name, which defaults to `antel`, corresponding to `antel.json`:

```bash
antel rebuild -f gcc
antel build --file release
```

The output directory is suffixed with the configuration file name (`<project name>_<configuration name>`), so the same source tree can produce different targets with different configurations without any interference.

## build and rebuild

```bash
antel build      # compile only what changed; does nothing if nothing changed
antel rebuild    # wipe obj/ and log/, full rebuild
```

How `build` decides what to compile is described in [Incremental Build](incremental-build.md): a source file is recompiled only when it or one of its dependencies has changed, or when its object file or dependency file is missing. When nothing differs, it only prints 「项目没有改动」 and does nothing else.

Use `rebuild` for the first build, after `clean`, or whenever you suspect the incremental state is off.

## clean

Deletes the entire output directory (`<project name>_<configuration name>/`), including generated targets, object files, logs, and the hash baseline. Since the baseline is deleted too, running `antel build` right after `clean` performs a full build — no need for `rebuild` first.

## link

Links only, without compiling. Use it to confirm that the link flags and library dependencies are correct, or to regenerate targets after manually adding object files to `obj/`.

## analyze

Generates a **visual analysis report**: a `report.html` in the output directory (a self-contained single-file HTML with inline CSS and no external dependencies — just open it in a browser). The report covers 10 analysis dimensions:

| Section | Content |
| ------- | ------- |
| **Artifacts** | Path, size, and file type of generated targets (detected via `file`); targets not built are flagged |
| **Incremental status** | Whether the hash baseline exists, files changed since the baseline, and stale files to rebuild |
| **Compile flag statistics** | Word frequency of `-O` / `-std` / `-D` / `-W` / `-f` flags, for a quick glance at optimization levels and macro definitions |
| **Resources** | Present only when resources are configured: each data_files entry expanded to file level (type / size / copied or not), the gresource XML and every file it references (prefix, compiled in or not, size of the generated `gresource.c`), each embed file (`_binary_` symbol, embedded or not) |
| **Symbol table** | Per-source-file symbol totals and categories (functions / data / BSS / undefined references), with one distinct chip per symbol and clear boundaries |
| **Header dependencies** | Which headers each source file depends on, inferred from the `.d` files |
| **Object size distribution** | A pure-CSS bar chart with unit-annotated sizes on the right |
| **Dynamic dependencies** | NEEDED entries of exe/shared (via readelf) and the ldd resolution results |
| **Compile commands** | The commands verbatim from `compile_commands.json` |
| **Log inventory** | Listing of the files and sizes (B/KB/MB) in `log/` |

```bash
antel analyze
```

The report automatically covers every source file in the configuration, with no configuration field required. Generating it automatically after a successful build is enabled with `report: true` (see [Configuration](configuration.md)); both paths produce an identical report.

## run

Valid only for projects whose `target_type` is `exe`; it directly executes the generated executable:

```bash
antel run
```

If the target type is not `exe`, or the executable does not exist yet, it reports a clear error and exits with a non-zero exit code.

## Exit codes

| Situation | Exit code |
| --------- | --------- |
| Command succeeded | 0 |
| Configuration file missing, wrong field types, or illegal values | 1 |
| Any of compile, link, analyze, or run fails | 1, and the failing command's own exit code is recorded in the error message |

There is a single convention: **an exit code of 0 means the step really succeeded**. If compilation or linking fails, it does not continue, nor does it print success messages like 「链接完毕」, so the command can be chained directly with `&&` or used in CI.

```bash
antel rebuild && antel run
```

## Common combinations

```bash
# full build, then run immediately
antel rebuild && antel run

# build with an alternative config producing a shared library
antel rebuild -f shared

# debug linking: relink only, then check the link script and link output
antel link -f release
cat release_release/log/*_link.sh
cat release_release/log/linkInfor
```
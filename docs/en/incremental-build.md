# Incremental Build

`antel build` has a single goal: **never recompile what has not changed, and never leave a stale target behind**.

## Where the data comes from

A single compilation produces two files at once:

```text
obj/src_main.o     object file
obj/src_main.o.d   dependency file, produced by -MMD -MF
```

The dependency file records the inputs that compilation actually read, including the source file itself and every header it includes (system headers excluded):

```text
helloworld_antel/obj/main.o: main.c include/foo.h
```

This dependency list is the key to incremental decisions. It solves a problem the source list alone cannot: `source` only lists `.c` files, so changing a header changes no source file's hash — yet the affected compile units must be rebuilt.

## Deciding what to recompile

`build` proceeds in three steps:

1. **Compute hash changes**: compute an md5 for every source file in the configuration, every file under `include_directories`, and every path that appeared in the dependency files of the last build; compare them against the baseline `log/hashes` to get the set of changed files
2. **Pick out the affected compile units**: walk through each source file in the configuration; any of the following means it needs recompiling
   - The object file is missing (deleted manually, or a build interrupted)
   - The dependency file is missing (e.g., a full compile has never completed)
   - The source file itself is in the changed set
   - A file in this compile unit's dependency file is in the changed set
3. **Compile as needed, then link in one pass**: compile only the source files picked in step 2, relink, then refresh the hash baseline with every input of this build. Compilation runs in parallel by default (`jobs`, see [Configuration](configuration.md)); the concurrency level only affects speed, never the outcome

Both the change list and the recompile list are written to disk for inspection:

```text
log/hashes_diff    changed files, with their before/after hashes
log/stale_files    sources actually recompiled this time
```

## An example

Three source files share one header:

```text
a.c  b.c  main.c        all #include "inc/common.h"
```

Change only `inc/common.h`, then run `antel build`:

```text
计算文件 hash...
发生变化的文件：1
全部待编译文件：3
需重新编译文件：2
```

Only `a.c` and `b.c` are recompiled; `main.c` is left untouched. Now change only `main.c`, and `需重新编译文件：1` (files to recompile: 1).

## Hash baseline

`log/hashes` records every input file of the **last successful build** along with its md5. The baseline is refreshed only after a build succeeds, so a failed build is never treated as "already built".

If the baseline file is missing, or contains something unrecognizable (e.g., a legacy-format baseline left over from upgrading an older version), it prints a notice and handles the build as a full build; a single `rebuild` brings you back to incremental state.

## When incremental is not used

| Situation | Behavior |
| --------- | -------- |
| Baseline missing (first build, after `clean`) | All source files are treated as changed; performs a full build |
| Baseline format unrecognizable | Same as above, plus a printed notice |
| `obj/` or `log/` deleted | Object files are missing; recompile them one by one |
| Some object file deleted manually | Recompile that object file only, leaving the rest untouched |
| Running `antel rebuild` | Clears `obj/` and `log/`, unconditionally rebuilds everything |

## FAQ

**`build` says 「项目没有改动」 but I definitely changed something?**

First check `log/hashes_diff`: if it is empty, the changed file is not in the tracked scope. Only files under `source`, files under `include_directories`, and dependencies recorded by the previous compile take part in the decision. For example, a header that no source file ever includes will not trigger a rebuild when changed — and that is correct. If you confirm the changed file is within the tracked scope, run `antel rebuild` to rebuild the baseline.

**Why did changing a header recompile only part of the source files?**

That is exactly the role of the dependency file: only the compile units that include the header need recompiling. You can see each compile unit's actual dependencies in `log/<output directory>/obj/*.d`.

**If a build fails, can the baseline be corrupted?**

No. The build stops immediately when compilation or linking returns non-zero; the baseline is refreshed only after a successful build, so the next `build` still recompiles the part that failed.
<div class="hero" markdown>
<img src="images/logo.svg" alt="Antelope" class="hero-logo hero-logo--light">
<img src="images/logo-dark.svg" alt="Antelope" class="hero-logo hero-logo--dark">

# Antelope

<p class="hero-tagline">A small, nimble C/C++ compile-and-link tool. Read one <code>antel.json</code> and it builds your project into a static library, a shared library, or an executable — no makefiles, no extra build language.</p>

<div class="hero-actions">
<a href="quick-start/" class="md-button md-button--primary">Get Started</a>
<a href="commands/" class="md-button">Command Reference</a>
<a href="https://github.com/luskyle/antelope/releases" class="md-button">Download v1.2</a>
</div>
</div>

<div class="grid cards" markdown>

-   :material-file-cog-outline:{ .lg .middle } **Configuration as the build script**

    ---

    Compile arguments, link arguments, target type, and compiler type all live in `antel.json`. The build mirrors the configuration one-to-one, so it can be committed alongside your source and reviewed together.

    [:octicons-arrow-right-24: Configuration](configuration.md)

-   :material-clock-fast:{ .lg .middle } **Dependency-based incremental builds**

    ---

    Every compile unit records its `-MMD` dependencies: touch a header and only the affected source files are rebuilt; missing object files or dependency files are rebuilt automatically.

    [:octicons-arrow-right-24: Incremental Build](incremental-build.md)

-   :material-alert-circle-outline:{ .lg .middle } **Aggregated diagnostics**

    ---

    Parallel build output is captured per compile unit: successes are reduced to a warning count, failures are replayed in full, grouped by file with counts — no more drowning in interleaved output.

    [:octicons-arrow-right-24: Commands & Exit Codes](commands.md)

-   :material-chart-box-outline:{ .lg .middle } **Visual analysis reports**

    ---

    Set `report: true` or run `antel analyze` to generate a self-contained `report.html`: artifacts, incremental status, compile arguments, symbol tables, header dependencies, size distribution, dynamic dependencies, and a log listing — open it directly in your browser.

    [:octicons-arrow-right-24: Command Reference](commands.md)

-   :material-package-variant-closed:{ .lg .middle } **Versioned shared libraries**

    ---

    `version` / `soname` / `rpath`: produces `libX.so.<version>` with symlinks; consumers link against the SONAME and load via the `$ORIGIN` rpath.

    [:octicons-arrow-right-24: Configuration](configuration.md)

-   :material-bug-outline:{ .lg .middle } **Sanitizers and coverage**

    ---

    `sanitize: ["address"]` / `coverage: true` inject ASan and gcov instrumentation with a single flag; run your program and a coverage report is at hand.

    [:octicons-arrow-right-24: Configuration](configuration.md)

</div>

## Four commands to get started

```bash
python3 antelope_install.py   # installs the antel command
antel init                    # interactively generates antel.json
antel rebuild                 # full build
antel run                     # runs the built executable
```

## Artifacts

| Target type | Artifact             | Description                                                       |
| ----------- | -------------------- | ----------------------------------------------------------------- |
| `static`    | `lib<project-name>.a` | Static library, stripped automatically after the build            |
| `shared`    | `lib<project-name>.so` | Shared library, linked via the compiler driver                    |
| `exe`       | `<project-name>`     | Executable, run directly with `antel run`                         |

Compilers supported are `gxx` (gcc/g++), `llvm` (clang), and `msvc` (cl); linking of shared libraries and executables is currently implemented only for the gxx and llvm paths, see [Compiler Support](compilers.md).

## Where to start

| What you want to do                          | Read this page                        |
| -------------------------------------------- | ------------------------------------- |
| Get a minimal project up and running         | [Quick Start](quick-start.md)         |
| Understand every field of antel.json         | [Configuration](configuration.md)     |
| See complete projects configured and running | [Examples](examples.md)               |
| Look up command flags and exit codes         | [Commands](commands.md)               |
| Understand when a rebuild happens            | [Incremental Build](incremental-build.md) |
| Switch compilers or target types             | [Compiler Support](compilers.md)      |
| Run tests, package, and release              | [Development](development.md)         |
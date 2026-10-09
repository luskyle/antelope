# Case Study: Building libpng with Antelope

libpng is a C library for reading and writing PNG images. This case connects a
real upstream library to Antelope: fetch sources, prepare generated files, build
static and shared libraries, run a PNG window application against the shared
library, and install and uninstall an isolated package.

The configs live in [demos/libpng](https://github.com/luskyle/antelope/tree/main/demos/libpng).
Results here describe Linux/x86_64 with libpng `1.6.60.git`, not a guarantee for
all platforms or optional upstream configurations.

## Working Targets

| Target | Antel config | Verified result |
| --- | --- | --- |
| Static library | `static.json` | `libpng16.a`, containing 17 implementation objects |
| Shared library | `shared.json` | Versioned so, SONAME, and library symlinks |
| Upstream tests | Six configs including `pngtest`, `pnggetset`, and `pngvalid` | Builds and representative test runs |
| Upstream tools | `pngfix`, `png-fix-itxt` | Builds and sample inputs |
| Contrib examples | Four configs including `example-iccfrompng` | Independent consumers of the shared library |
| PNG window | `pngviewer.json` | Displays the Antelope logo with file opening and zoom |
| Installation | `install.json` | Isolated package, manifest-based removal, user-file preservation |

These results do not certify the full upstream CTest matrix. Antelope does not
automatically translate arbitrary CMake projects: the demo explicitly specifies
sources, flags, and preparation commands.

## Build the Libraries

Install Antelope using [Quick Start](quick-start.md). Dependencies are Git,
Python 3, a C/C++ toolchain, AWK, pkg-config, and zlib development files. The viewer
also needs GTK 3 development files and a graphical desktop session.

For Debian/Ubuntu:

```bash
sudo apt install build-essential git gawk pkg-config zlib1g-dev libgtk-3-dev
```

From the repository root:

```bash
cd demos/libpng
antel fetch-ref -f static
antel rebuild -f static
antel rebuild -f shared
ar t .antel/build/png16_static/libpng16.a | wc -l
readelf -d .antel/build/png16_shared/libpng16.so.16.60.git | grep SONAME
```

`ref` shallow-clones the upstream `libpng16` branch into `.antel/refs/libpng/`.
Both targets compile 15 core sources and two Intel SSE2 sources, enabling
`PNG_INTEL_SSE_OPT=1`. The shared target adds `-fPIC` and uses
`pkg_config: ["zlib"]`. Static consumers must still link zlib and libm.

!!! note "The upstream branch can change"
    The ref is not pinned to a commit, and existing checkouts do not update
    automatically. After fetching newer sources, check the source list and the
    `version` in `shared.json`; the version and object count here are a snapshot.

## Prepare Files Without CMake

Compilation needs a configuration header; the versioned shared library also
needs an ELF version script. `before_build` runs `prepare_libpng.py` after refs
are ready but before incremental scanning and compilation:

```json
{
  "before_build": [
    {
      "command": ["python3", "prepare_libpng.py"],
      "outputs": [
        ".antel/build/libpng-generated/pnglibconf.h",
        ".antel/build/libpng-generated/libpng.vers"
      ]
    }
  ]
}
```

The helper copies upstream `scripts/pnglibconf.h.prebuilt` rather than inventing
configuration macros. It preprocesses upstream `scripts/vers.c` and runs upstream
`scripts/dfn.awk` to produce the symbol version script. In this comparison,
`libpng.vers` matched the CMake-generated script byte for byte. The prebuilt
header is not a replacement for every optional CMake configuration; customized
features may need a different preparation step.

Declared outputs participate in change detection: dependency changes recompile
affected sources, and version script changes trigger relinking. Failed commands
or missing declared outputs abort the build. No CMake invocation is needed for
these library targets. See [Configuration](configuration.md#before_build).

## Versioned Shared Library

```text
.antel/build/png16_shared/
  libpng16.so.16.60.git
  libpng16.so.16 -> libpng16.so.16.60.git
  libpng16.so -> libpng16.so.16.60.git
```

The SONAME is `libpng16.so.16`. The config declares `version: "16.60.git"` and
passes `-Wl,--version-script=.antel/build/libpng-generated/libpng.vers` to the linker.

## A Window Using the Built so

![GTK viewer decoding the Antelope logo with the locally built libpng](../images/libpng-viewer.png)

Actual window capture: the checkerboard shows transparency; the status bar lists
image dimensions, zoom, and the loaded libpng version.

```bash
antel rebuild -f pngviewer
./.antel/build/pngviewer_pngviewer/pngviewer
./.antel/build/pngviewer_pngviewer/pngviewer /path/to/image.png
```

GTK 3 provides the window, chooser, and drawing surface. PNG decoding directly
calls the built libpng's `png_image_begin_read_from_file` and
`png_image_finish_read`, not GTK's image loader. With no path, `data_files`
supplies Antelope's transparent PNG logo.

The window offers Open, Zoom In, Zoom Out, Fit to Window, and a transparency
checkerboard. Invalid images leave the current image intact. Limits are 16384
pixels per dimension and 256 MiB of decoded RGBA data.

```bash
ldd .antel/build/pngviewer_pngviewer/pngviewer | grep libpng
./.antel/build/pngviewer_pngviewer/pngviewer --smoke-test
```

The verified loader path points to `.antel/build/png16_shared/libpng16.so.16`; the logo decodes
to `512 x 512`. The smoke test renders a window, saves its capture to
`/tmp/antel-pngviewer.png`, and exits.

## Isolated Installation and Removal

The demo's `install.json` contains:

```json
{
  "projectName": "libpng",
  "install_path": "/usr/local"
}
```

`antel install` creates `/usr/local/libpng/`, not scattered system files. It
installs all built targets by default. Add `"projects": ["png16", "pngviewer"]`
to install only the libraries and viewer.

```text
/usr/local/libpng/
  .antel-install
  bin/
  lib/
  share/
```

Executables go to `bin/`, libraries and symlinks to `lib/`, and deployed resources
to `share/`. `.antel-install` records installed relative paths and owning build
projects. Do not delete or edit it: it is not required to run programs, but is
needed for safe install and uninstall management.

```bash
# Run from demos/libpng; /usr/local usually requires administrator privileges
sudo antel install
/usr/local/libpng/bin/pngviewer
sudo antel uninstall
```

The viewer uses `$ORIGIN/../lib` and relative resource paths. A temporary-prefix
test verified that moving the entire package still loads its own so and logo.
For other upstream programs without an installation RPATH, set the package's
`LD_LIBRARY_PATH` for that invocation rather than registering a global cache.

Uninstall removes only manifest entries, cleans empty directories, and preserves
added user files without needing the original build tree. Legacy empty markers
must first be upgraded by reinstalling. Earlier scattered system installations
require explicit `uninstall --legacy-system`; preview with `--dry-run` first.
See [Commands](commands.md#uninstall).

## More Upstream Programs

After fetching the source, prepare the ICC fixture and build the remaining targets:

```bash
python3 prepare_icc_fixture.py
for target in pngtest pnggetset pngvalid pngstest pngunknown pngimage pngfix png-fix-itxt; do
    antel rebuild -f "$target"
done
for target in example-iccfrompng example-pngpixel example-pngtopng example-simpleover; do
    antel rebuild -f "$target"
done
./.antel/build/pngtest_pngtest/pngtest .antel/build/pngtest_pngtest/testdata/pngtest.png /tmp/png-roundtrip.png
./.antel/build/pngvalid_pngvalid/pngvalid --gamma-16-to-8
```

See [Examples](examples.md#libpng-staticshared-targets-ref) and the demo README for
the input files each program expects. The case demonstrates an actual library's
source, generated files, dependencies, applications, and distribution workflow,
not a replacement library built around a minimal hello-world consumer.
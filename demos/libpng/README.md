# libpng: PNG codec through `ref`

This demo mirrors libpng CMake's default `PNG_STATIC=ON` and `PNG_SHARED=ON` as
two Antel configurations. Both compile the same upstream translation units;
`shared.json` adds PIC and CMake's ABI/versioned SONAME. The x86_64 CMake
configuration also enables `PNG_INTEL_SSE_OPT` and two SSE2 source files. zlib
is linked by `shared.json` through `pkg_config`; static-archive consumers need
to link zlib and libm themselves.

Run from this directory. The first setup needs Git, Python 3, a C compiler, AWK,
pkg-config, network access, and zlib development files. `before_build` runs
`prepare_libpng.py` automatically before each target build; test configs use
`data_files` from the fetched ref:

```bash
antel fetch-ref -f static
python3 prepare_icc_fixture.py
antel rebuild -f static
antel rebuild -f shared
ar t png16_static/libpng16.a | wc -l
readelf -d png16_shared/libpng16.so.16.60.git | grep SONAME
```

Both targets contain 17 upstream implementation objects. The shared
configuration produces `libpng16.so.16.60.git`, SONAME `libpng16.so.16`, and
the usual symlinks. Antel's prepare step copies upstream's standard
`pnglibconf.h` to `build/libpng-generated` and generates `libpng.vers` from
upstream `vers.c` with the C preprocessor and `dfn.awk`; CMake is not needed.

## Upstream CMake executables

The `PNG_TESTS` block defines six standalone test programs and the
`PNG_SHARED && PNG_TOOLS` block defines two utilities. Each has its own Antel
config; they link the shared target above and do not compile another copy of
libpng:

| Upstream target  | Antel config          | Purpose                               |
| ---------------- | --------------------- | ------------------------------------- |
| `pngtest`      | `pngtest.json`      | PNG read/write round-trip             |
| `pnggetset`    | `pnggetset.json`    | Chunk getter/setter round-trips       |
| `pngvalid`     | `pngvalid.json`     | Transform and gamma validation        |
| `pngstest`     | `pngstest.json`     | Simplified API format conversion      |
| `pngunknown`   | `pngunknown.json`   | Unknown-chunk handling                |
| `pngimage`     | `pngimage.json`     | Image read/write transform checks     |
| `pngfix`       | `pngfix.json`       | Inspect/repair PNG compressed streams |
| `png-fix-itxt` | `png-fix-itxt.json` | Repair legacy iTXt chunk lengths      |

After the library setup above, build all eight programs:

```bash
for target in pngtest pnggetset pngvalid pngstest pngunknown pngimage pngfix png-fix-itxt; do
	antel rebuild -f "$target"
done
```

Representative upstream tests use files from the fetched source tree:

```bash
./pngtest_pngtest/pngtest pngtest_pngtest/testdata/pngtest.png /tmp/png-roundtrip.png
./pnggetset_pnggetset/pnggetset
./pngvalid_pngvalid/pngvalid --gamma-16-to-8
./pngunknown_pngunknown/pngunknown --strict default=discard pngunknown_pngunknown/testdata/pngtest.png
./pngimage_pngimage/pngimage --list-combos --log pngimage_pngimage/testdata/pngsuite/basn0g08.png
./pngstest_pngstest/pngstest --log --tmpfile /tmp/ps- pngstest_pngstest/testdata/testpngs/gray-1.png
```

The CMake target `pngtest` expects a PNG input; test assets are in the fetched
source tree. The commands above use one representative case per test executable,
not the full CTest matrix.

## Contrib examples

Four additional, independent programs under `contrib/examples/` have configs:

| Program        | Antel config                | Use                                                         |
| -------------- | --------------------------- | ----------------------------------------------------------- |
| `iccfrompng` | `example-iccfrompng.json` | Extract an embedded ICC profile; needs a PNG containing one |
| `pngpixel`   | `example-pngpixel.json`   | Print an image pixel                                        |
| `pngtopng`   | `example-pngtopng.json`   | Read and rewrite PNG using the simplified API               |
| `simpleover` | `example-simpleover.json` | Composite PNG sprites over a background                     |

Build the four examples:

```bash
for target in example-iccfrompng example-pngpixel example-pngtopng example-simpleover; do
	antel rebuild -f "$target"
done
```

`data_files` copies the relevant images into each target's output directory:
pngtest/pngunknown/pngfix/png-fix-itxt and three image examples use upstream
`pngtest.png`; pngimage gets `pngsuite/`, pngstest gets `testpngs/`, and
iccfrompng gets the generated ICC-profile fixture.

Run the examples against the copied images; generated files go to `/tmp`:

```bash
./iccfrompng_example-iccfrompng/iccfrompng iccfrompng_example-iccfrompng/testdata/icc-profile.png
./pngpixel_example-pngpixel/pngpixel 0 0 pngpixel_example-pngpixel/testdata/pngtest.png
./pngtopng_example-pngtopng/pngtopng pngtopng_example-pngtopng/testdata/pngtest.png /tmp/pngtopng.png
./simpleover_example-simpleover/simpleover simpleover_example-simpleover/testdata/background.png /tmp/simpleover.png
./pngfix_pngfix/pngfix --quiet pngfix_pngfix/testdata/pngtest.png
./png-fix-itxt_png-fix-itxt/png-fix-itxt < png-fix-itxt_png-fix-itxt/testdata/pngtest.png > /tmp/png-fixed.png
```

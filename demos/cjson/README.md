# cJSON: public project through `ref`

This demo fetches the public [cJSON](https://github.com/DaveGamble/cJSON)
`master` branch and builds a representative subset of its upstream CMake
targets with Antelope. No CMake invocation or locally written entry point is
needed. The configurations are verified on Linux with GCC.

## Targets

| Configuration | Upstream target | Output |
| --- | --- | --- |
| `antel.json` | `cjson-static` | `.antel/build/cjson_antel/libcjson.a` |
| `shared.json` | `cjson` | `.antel/build/cjson_shared/libcjson.so.1.7.19` |
| `utils-static.json` | `cjson_utils-static` | `.antel/build/cjson_utils_utils-static/libcjson_utils.a` |
| `utils-shared.json` | `cjson_utils` | `.antel/build/cjson_utils_utils-shared/libcjson_utils.so.1.7.19` |
| `unity.json` | `unity` | `.antel/build/unity_unity/libunity.a` |
| `demo.json` | `cJSON_test` | `.antel/build/cJSON_test_demo/cJSON_test` |
| `parse-examples.json` | `parse_examples` | `.antel/build/parse_examples_parse-examples/parse_examples` |
| `utils-tests.json` | `old_utils_tests` | `.antel/build/old_utils_tests_utils-tests/old_utils_tests` |

This corresponds to enabling upstream `BUILD_SHARED_AND_STATIC_LIBS` and
`ENABLE_CJSON_UTILS`, but selects only two Unity test executables. It does not
reproduce the entire upstream test or fuzzing suite. Core and Utils are separate
libraries, unlike the previous combined archive. Static Utils consumers must
link `libcjson_utils.a`, then `libcjson.a`, and `-lm`.

Shared libraries include the ABI-1 SONAME and version symlinks. Version `1.7.19`
matches the currently checked-out upstream version; `master` is not an immutable
pin. When refreshing the reference cache, check the upstream version and update
both shared configurations if necessary.

## Build and run

Run from this directory, in dependency order. Fetch first because the parsing
test declares upstream input files as `data_files`:

```bash
antel fetch-ref
antel rebuild
for config in shared utils-static utils-shared unity demo parse-examples utils-tests; do
    antel rebuild -f "$config" || exit 1
done
ar t .antel/build/cjson_antel/libcjson.a
ar t .antel/build/cjson_utils_utils-static/libcjson_utils.a

./.antel/build/cJSON_test_demo/cJSON_test
(cd .antel/build/parse_examples_parse-examples && ./parse_examples)
./.antel/build/old_utils_tests_utils-tests/old_utils_tests
```

`parse_examples` reads the `inputs/` directory copied into its output directory
by Antel. Run it from that directory: it verifies 15 parsing cases.
`old_utils_tests` verifies six groups covering JSON Pointer, sorting and merge
patches without external data. `cJSON_test` prints upstream's JSON examples.
The executables and shared Utils use relative rpaths to load the locally built
libraries; no `LD_LIBRARY_PATH` or system installation is required.

The cloned source is cached under `.antel/refs/cjson`. Individual library builds
also fetch it automatically if missing, but dependencies between configurations
are built explicitly in the order above.

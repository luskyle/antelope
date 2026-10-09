# json-c: upstream project through `ref`

This demo fetches the public json-c `master` branch. A Python `before_build`
script probes the host C compiler and generates json-c's platform headers
directly in `.antel/build/json-c-config/`. Neither CMake configuration nor a
CMake build is required.

## Targets

| Configuration | Upstream target | Output |
| --- | --- | --- |
| `antel.json` | `json-c-static` | `.antel/build/json-c_antel/libjson-c.a` |
| `shared.json` | `json-c` | `.antel/build/json-c_shared/libjson-c.so.5.5.0` |
| `json-parse.json` | `json_parse` | `.antel/build/json_parse_json-parse/json_parse` |
| `test-parse.json` | `test_parse` | `.antel/build/test_parse_test-parse/test_parse` |
| `test-json-pointer.json` | `test_json_pointer` | `.antel/build/test_json_pointer_test-json-pointer/test_json_pointer` |
| `test-json-patch.json` | `test_json_patch` | `.antel/build/test_json_patch_test-json-patch/test_json_patch` |

The two library configurations each compile the same 14 upstream production
translation units. The selected application and tests link the Antel-built
shared library through relative rpaths. This is a representative subset of
upstream targets, not the complete test suite.

## Build and run

Run from this directory:

```bash
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

Each configuration invokes the shared `prepare_json_c.py` script from
`before_build`. It probes headers, functions and type sizes with the configured
C compiler, then generates `config.h`, `json_config.h`, `json.h`, and
`apps_config.h` directly under `.antel/build/json-c-config/`. These declared outputs participate in incremental
change detection. Antel writes the static and shared libraries, `json_parse`,
and the three selected test executables. The JSON Patch fixture files are
copied into the test output by `data_files`. The source cache is
`.antel/refs/json-c`.
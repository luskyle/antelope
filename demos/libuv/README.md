# libuv: Linux event loop through `ref`

This demo fetches libuv `v1.x` and builds its Linux/POSIX targets with Antel;
the build does not invoke CMake. The upstream default target set includes the
shared library `uv` and static library `uv_a`. With tests enabled, upstream
also defines shared and static test runners plus a static benchmark runner.

Run from this directory. The first step needs Git and network access:

```bash
antel fetch-ref
python3 prepare_libuv.py
antel rebuild
antel rebuild -f shared
antel rebuild -f tests-static
antel rebuild -f tests-shared
antel rebuild -f benchmarks
```

The generated targets are:

| Upstream target | Antel config | Output |
| --- | --- | --- |
| `uv_a` | `antel.json` | `.antel/build/uv_antel/libuv.a` |
| `uv` | `shared.json` | `.antel/build/uv_shared/libuv.so.1.0.0` |
| `uv_run_tests_a` | `tests-static.json` | `.antel/build/uv_run_tests_a_tests-static/uv_run_tests_a` |
| `uv_run_tests` | `tests-shared.json` | `.antel/build/uv_run_tests_tests-shared/uv_run_tests` |
| `uv_run_benchmarks_a` | `benchmarks.json` | `.antel/build/uv_run_benchmarks_a_benchmarks/uv_run_benchmarks_a` |

The test runner contains all 185 Linux-applicable upstream `test-*.c` files.
List tests without running them:

```bash
cd .antel/refs/libuv
../../../.antel/build/uv_run_tests_a_tests-static/uv_run_tests_a --list
```

The demo currently targets Linux. Consumers of the static archive need
`pthread`, `dl`, and `rt`; the test runners additionally link `m` and `util`.

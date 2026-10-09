# libgit2: Antel-only build through `ref`

This demo fetches the public libgit2 `main` branch and builds the upstream
library, CLI, example program, and test runners with Antel. `prepare_antelope.py`
selects Linux sources, writes the generated feature header, and creates the
target configs. CMake is not invoked.

Requirements: Linux, Git, Python 3, OpenSSL, PCRE, and zlib development packages.
The build uses the system pthread library.

Run from this directory:

```bash
antel fetch-ref -f generated
python3 prepare_antelope.py

antel rebuild -f generated       # static archive
antel rebuild -f shared          # versioned shared library
antel rebuild -f cli             # git2 command-line tool
antel rebuild -f lg2             # upstream example tool
antel rebuild -f tests-libgit2   # offline libgit2 test runner
antel rebuild -f tests-util      # utility test runner
```

The static archive contains 196 library objects. The shared library has SONAME
`libgit2.so.1.9`; `lg2` links against it using a relative rpath. The CLI and both
test runners link against the Antel-built static archive. Clar's Python generator
creates the test suites; online, stress, and performance tests are excluded from
the libgit2 test runner.

Representative checks:

```bash
ar t .antel/build/git2_generated/libgit2.a | wc -l
readelf -d .antel/build/git2_shared/libgit2.so.1.9.0 | grep SONAME
./.antel/build/git2_cli/git2 version
ldd .antel/build/lg2_lg2/lg2 | grep libgit2
(cd .antel/build/libgit2_tests_tests-libgit2 && ./libgit2_tests)
(cd .antel/build/util_tests_tests-util && ./util_tests -v)
```

Every target config carries the same `ref`. `generated.json` is the initial ref
source, so no separate `refs.json` file is needed. Preparation runs as
Antel's `before_build` step to keep the feature header and Clar suites in sync
with the checked-out revision.

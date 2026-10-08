# libgit2: configured C project through `ref`

This demo fetches the public libgit2 `main` branch. Its CMake configure step
selects the platform implementation and generates feature headers plus
`compile_commands.json`; a small helper converts that database into an Antel
config. Antel compiles all selected upstream sources into a static archive.

Run from this directory. CMake configures but does not build libgit2:

```bash
antel fetch-ref -f refs
cmake -S .antel/refs/libgit2 -B build/libgit2-config \
  -DBUILD_TESTS=OFF -DBUILD_CLI=OFF -DBUILD_EXAMPLES=OFF \
  -DBUILD_SHARED_LIBS=OFF -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
python3 prepare_antelope.py
antel rebuild -f generated
ar t git2_generated/libgit2.a | wc -l
```

The generated config records the source files and compile definitions selected by
the current CMake configuration. It selects 196 upstream translation units. The
demo uses the system OpenSSL, PCRE, and zlib development packages; consumers of
the archive need their link flags.
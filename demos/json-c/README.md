# json-c: configured upstream project through `ref`

This demo fetches the public json-c `master` branch. json-c needs platform
feature-test headers, so CMake is used only to configure and generate those
headers; Antelope compiles the upstream production C files into a static archive.

Run from this directory:

```bash
antel fetch-ref
cmake -S .antel/refs/json-c -B build/json-c-config \
  -DBUILD_TESTING=OFF -DBUILD_APPS=OFF \
  -DBUILD_SHARED_LIBS=OFF -DBUILD_STATIC_LIBS=ON \
  -DDISABLE_EXTRA_LIBS=ON
antel rebuild
ar t json-c_antel/libjson-c.a | wc -l
```

The configure step generates `config.h`, `json_config.h`, and `json.h`; it does
not compile the library. Antel writes `json-c_antel/libjson-c.a` from the 14
upstream translation units. The source cache is `.antel/refs/json-c`.
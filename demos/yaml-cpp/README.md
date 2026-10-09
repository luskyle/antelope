# yaml-cpp: C++ library through `ref`

This demo fetches the public yaml-cpp `master` branch and compiles the upstream
core and contrib translation units as a C++11 static library with Antelope.

Run from this directory. The first build needs Git and network access:

```bash
antel rebuild
ar t .antel/build/yaml-cpp_antel/libyaml-cpp.a | wc -l
```

The archive contains 32 yaml-cpp upstream objects. The source checkout is cached
under `.antel/refs/yaml-cpp`.
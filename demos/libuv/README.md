# libuv: Linux event loop through `ref`

This demo fetches the public libuv `v1.x` branch and builds the Linux/POSIX
implementation selected by upstream CMake as a static library.

Run from this directory. The first build needs Git and network access:

```bash
antel rebuild
ar t uv_antel/libuv.a | wc -l
```

The archive contains the 35 selected Linux/POSIX objects. The source list
excludes Windows, macOS, and other Unix platform implementations. Consumers
linking the archive will need `pthread`, `dl`, and `rt`.
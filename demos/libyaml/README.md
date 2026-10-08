# libyaml: Git ref

This demo builds the public [libyaml](https://github.com/yaml/libyaml) 0.2.5
source tree as a static library. Its `ref` entry shallow-clones the upstream
`release/0.2.5` branch before Antelope scans and compiles the listed sources.

Run from this directory; the first build needs network access and Git:

```bash
antel rebuild
```

The resulting library is `yaml_antel/libyaml.a`. The upstream CMake build
generates `config.h` only to provide version macros; this demo passes those
macros directly to the compiler, so no CMake setup is needed. The reference
checkout is cached under `.antel/refs/libyaml` and is preserved by `antel clean`.
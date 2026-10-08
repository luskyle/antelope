# cJSON: public project through `ref`

This demo fetches the public [cJSON](https://github.com/DaveGamble/cJSON)
`master` branch and builds its parser and JSON Utils module as a static library
with Antelope.

Run from this directory. The first command fetches the source without compiling;
`antel rebuild` also fetches it automatically if it is not present:

```bash
antel fetch-ref
antel rebuild
ar t cjson_antel/libcjson.a
```

The archive contains only the upstream cJSON core and JSON Utils objects. The
cloned source is cached under `.antel/refs/cjson`.
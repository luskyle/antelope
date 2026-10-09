# Success Cases

This index collects verified Antel build cases, including built-in examples and public upstream projects fetched through `ref` and built from Antel configs. Projects may keep multiple JSON configs to describe separate libraries, tools, and tests. Follow **Build details** for the configuration walkthrough, or **Project source** for the corresponding case directory in this repository.

<div class="grid cards" markdown>

-   **[libgit2](examples.md#case-libgit2)**

    ---

    A large Git implementation. The case covers static and shared libraries, command-line tools, and test runners.

    [:octicons-arrow-right-24: Build details](examples.md#case-libgit2) · [Project source](https://github.com/luskyle/antelope/tree/main/demos/libgit2)

-   **[libuv](examples.md#case-libuv)**

    ---

    A cross-platform asynchronous I/O library, demonstrating Antel descriptions for the upstream library and related targets.

    [:octicons-arrow-right-24: Build details](examples.md#case-libuv) · [Project source](https://github.com/luskyle/antelope/tree/main/demos/libuv)

-   **[json-c](examples.md#case-json-c)**

    ---

    A C JSON library case with library, CLI, and selected test targets; configuration probes are handled by Python.

    [:octicons-arrow-right-24: Build details](examples.md#case-json-c) · [Project source](https://github.com/luskyle/antelope/tree/main/demos/json-c)

-   **[cJSON](examples.md#case-cjson)**

    ---

    A lightweight C JSON library, using multiple configs to build representative project artifacts.

    [:octicons-arrow-right-24: Build details](examples.md#case-cjson) · [Project source](https://github.com/luskyle/antelope/tree/main/demos/cjson)

-   **[libpng](libpng-case-study.md)**

    ---

    The PNG image library, demonstrating static and shared libraries and their installation layout.

    [:octicons-arrow-right-24: Case study](libpng-case-study.md) · [Example config](examples.md#case-libpng) · [Project source](https://github.com/luskyle/antelope/tree/main/demos/libpng)

-   **[yaml-cpp](examples.md#case-yaml-cpp)**

    ---

    A C++ YAML library demonstrating Antel configuration for a larger C++ project.

    [:octicons-arrow-right-24: Build details](examples.md#case-yaml-cpp) · [Project source](https://github.com/luskyle/antelope/tree/main/demos/yaml-cpp)

-   **[libyaml](examples.md#case-libyaml)**

    ---

    A pure-C YAML parser, demonstrating fetching and building upstream source with `ref`.

    [:octicons-arrow-right-24: Build details](examples.md#case-libyaml) · [Project source](https://github.com/luskyle/antelope/tree/main/demos/libyaml)

-   **[GTK calculator](examples.md#case-gtkcalc)**

    ---

    A GTK 4/libadwaita desktop app, demonstrating system dependency integration through `pkg_config`.

    [:octicons-arrow-right-24: Build details](examples.md#case-gtkcalc)

-   **[Resource packaging (resdemo)](examples.md#case-resdemo)**

    ---

    Demonstrates data-file copying, GLib resources, and binary embedding for distribution.

    [:octicons-arrow-right-24: Build details](examples.md#case-resdemo)

-   **[AntelStats](examples.md#case-antelstats)**

    ---

    An Antel bootstrap case: build a shared library and link it from a consumer program.

    [:octicons-arrow-right-24: Build details](examples.md#case-antelstats)

</div>

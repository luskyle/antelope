# 成功案例

这里汇总仓库中已验证的 Antel 构建案例，包括仓库内置示例，以及通过 `ref` 获取并由 Antel 配置构建的公开上游项目。项目可包含多份 JSON 配置，以分别描述不同库、工具和测试目标。点击“构建详情”查看示例页中的配置与说明，“项目源码”跳转到本仓库中对应的案例目录。

<div class="grid cards" markdown>

-   **[libgit2](examples.md#case-libgit2)**

    ---

    大型 Git 实现。案例覆盖静态库、共享库、命令行工具及测试运行器。

    [:octicons-arrow-right-24: 构建详情](examples.md#case-libgit2) · [项目源码](https://github.com/luskyle/antelope/tree/main/demos/libgit2)

-   **[libuv](examples.md#case-libuv)**

    ---

    跨平台异步 I/O 库，展示 Antel 对上游库及相关构建目标的描述。

    [:octicons-arrow-right-24: 构建详情](examples.md#case-libuv) · [项目源码](https://github.com/luskyle/antelope/tree/main/demos/libuv)

-   **[LVGL](examples.md#case-lvgl)**

    ---

    官方 LVGL 9.6 核心与 UI 库由 Antel 构建；另有 SDL2 窗体介绍 Antelope，并展示交互式图表与控件。

    [:octicons-arrow-right-24: 构建详情](examples.md#case-lvgl) · [项目源码](https://github.com/luskyle/antelope/tree/main/demos/lvgl)

-   **[json-c](examples.md#case-json-c)**

    ---

    C 语言 JSON 库案例，包含库、命令行工具和选定的测试目标；配置探测由 Python 脚本完成。

    [:octicons-arrow-right-24: 构建详情](examples.md#case-json-c) · [项目源码](https://github.com/luskyle/antelope/tree/main/demos/json-c)

-   **[cJSON](examples.md#case-cjson)**

    ---

    轻量级 C JSON 库，使用多份配置构建项目中的代表性产物。

    [:octicons-arrow-right-24: 构建详情](examples.md#case-cjson) · [项目源码](https://github.com/luskyle/antelope/tree/main/demos/cjson)

-   **[libpng](libpng-case-study.md)**

    ---

    PNG 图像处理库，演示静态库、共享库及其安装布局。

    [:octicons-arrow-right-24: 案例专题](libpng-case-study.md) · [示例配置](examples.md#case-libpng) · [项目源码](https://github.com/luskyle/antelope/tree/main/demos/libpng)

-   **[yaml-cpp](examples.md#case-yaml-cpp)**

    ---

    C++ YAML 库，展示大型 C++ 项目的 Antel 配置方式。

    [:octicons-arrow-right-24: 构建详情](examples.md#case-yaml-cpp) · [项目源码](https://github.com/luskyle/antelope/tree/main/demos/yaml-cpp)

-   **[libyaml](examples.md#case-libyaml)**

    ---

    纯 C YAML 解析库，展示使用 `ref` 获取并构建上游代码。

    [:octicons-arrow-right-24: 构建详情](examples.md#case-libyaml) · [项目源码](https://github.com/luskyle/antelope/tree/main/demos/libyaml)

-   **[GTK calculator](examples.md#case-gtkcalc)**

    ---

    GTK 4/libadwaita 桌面程序，演示通过 `pkg_config` 集成系统依赖。

    [:octicons-arrow-right-24: 构建详情](examples.md#case-gtkcalc)

-   **[资源打包 resdemo](examples.md#case-resdemo)**

    ---

    展示资源文件复制、GLib 资源和二进制嵌入等分发方式。

    [:octicons-arrow-right-24: 构建详情](examples.md#case-resdemo)

-   **[AntelStats](examples.md#case-antelstats)**

    ---

    Antel 自举案例：构建共享库并由消费者程序链接使用。

    [:octicons-arrow-right-24: 构建详情](examples.md#case-antelstats)

</div>

<div class="hero" markdown>
<img src="images/logo.svg" alt="Antelope" class="hero-logo">

# Antelope

<p class="hero-tagline">小巧敏捷的 C/C++ 编译链接工具。读一个 <code>antel.json</code>，把项目编成静态库、共享库或可执行程序——不生成 makefile，也不引入额外的构建语言。</p>

<div class="hero-actions">
<a href="quick-start/" class="md-button md-button--primary">快速开始</a>
<a href="commands/" class="md-button">命令参考</a>
<a href="https://github.com/luskyle/antelope/releases" class="md-button">下载 v1.0</a>
</div>
</div>

<div class="grid cards" markdown>

-   :material-file-cog-outline:{ .lg .middle } **配置即构建脚本**

    ---

    编译参数、链接参数、目标类型、编译器类型都写在 `antel.json` 里，构建方式与配置一一对应，可以随源码一起提交、一起评审。

    [:octicons-arrow-right-24: 配置参考](configuration.md)

-   :material-clock-fast:{ .lg .middle } **基于依赖的增量构建**

    ---

    每个编译单元都记录 `-MMD` 依赖，改动头文件只重编受影响的源文件；目标文件或依赖文件缺失时自动补编。

    [:octicons-arrow-right-24: 增量构建](incremental-build.md)

-   :material-alert-circle-outline:{ .lg .middle } **失败即中断**

    ---

    编译、链接、分析、运行任一环节返回非 0 都立即终止，以非 0 退出码结束，不会把失败当成功。

    [:octicons-arrow-right-24: 命令与退出码](commands.md)

-   :material-clipboard-text-outline:{ .lg .middle } **产物可追溯**

    ---

    实际执行的编译命令与链接脚本落盘到 `log/`，附带符号表、重定位表、动态依赖等分析结果，便于事后核查与归档。

    [:octicons-arrow-right-24: 构建目录布局](configuration.md)

</div>

## 四条命令上手

```bash
python3 antelope_install.py   # 安装 antel 命令
antel init                    # 交互式生成 antel.json
antel rebuild                 # 全量构建
antel run                     # 运行生成的可执行程序
```

## 生成物

| 目标类型   | 生成物                | 说明                                   |
| ---------- | --------------------- | -------------------------------------- |
| `static`   | `lib<项目名>.a`       | 静态库，构建后自动 strip               |
| `shared`   | `lib<项目名>.so`      | 共享库，经编译器驱动链接               |
| `exe`      | `<项目名>`            | 可执行程序，可用 `antel run` 直接执行  |

编译器支持 `gxx`（gcc/g++）、`llvm`（clang）、`msvc`（cl）；共享库与可执行程序的链接目前只实现了 gxx 与 llvm 路径，详见[编译器支持](compilers.md)。

## 从哪看起

| 想做的事                     | 看这一页                              |
| ---------------------------- | ------------------------------------- |
| 先跑通一个最小项目           | [快速开始](quick-start.md)            |
| 搞清楚 antel.json 的每个字段 | [配置参考](configuration.md)          |
| 查命令的参数与退出码         | [命令参考](commands.md)               |
| 理解什么时候会重新编译       | [增量构建](incremental-build.md)      |
| 换编译器或换目标类型         | [编译器支持](compilers.md)            |
| 跑测试、打包、发版           | [开发与发布](development.md)          |
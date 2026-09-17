<div class="hero" markdown>
<img src="images/logo.svg" alt="Antelope" class="hero-logo hero-logo--light">
<img src="images/logo-dark.svg" alt="Antelope" class="hero-logo hero-logo--dark">

# Antelope

<p class="hero-tagline">小巧敏捷的 C/C++ 编译链接工具。读一个 <code>antel.json</code>，把项目编成静态库、共享库或可执行程序——不生成 makefile，也不引入额外的构建语言。</p>

<div class="hero-actions">
<a href="quick-start/" class="md-button md-button--primary">快速开始</a>
<a href="commands/" class="md-button">命令参考</a>
<a href="https://github.com/luskyle/antelope/releases" class="md-button">下载 v1.2</a>
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

-   :material-alert-circle-outline:{ .lg .middle } **诊断聚合**

    ---

    并行编译的输出按单元捕获：成功只汇总警告数，失败按文件分组整块回放、给出计数，不再被并发刷屏淹没。

    [:octicons-arrow-right-24: 命令与退出码](commands.md)

-   :material-chart-box-outline:{ .lg .middle } **可视化分析报告**

    ---

    `report: true` 或 `antel analyze` 生成自包含的 `report.html`：产物、增量状态、编译参数、符号表、头文件依赖、大小分布、动态依赖与日志清单，浏览器直接打开。

    [:octicons-arrow-right-24: 命令参考](commands.md)

-   :material-package-variant-closed:{ .lg .middle } **版本化共享库**

    ---

    `version` / `soname` / `rpath`：产出 `libX.so.<版本>` 与软链，消费端按 SONAME 链接、`$ORIGIN` rpath 加载。

    [:octicons-arrow-right-24: 配置参考](configuration.md)

-   :material-bug-outline:{ .lg .middle } **消毒器与覆盖率**

    ---

    `sanitize: ["address"]` / `coverage: true` 一键注入 ASan 与 gcov 插桩，运行后即可出覆盖率报告。

    [:octicons-arrow-right-24: 配置参考](configuration.md)

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
| 看完整工程的配置与运行效果   | [示例与效果图](examples.md)           |
| 查命令的参数与退出码         | [命令参考](commands.md)               |
| 理解什么时候会重新编译       | [增量构建](incremental-build.md)      |
| 换编译器或换目标类型         | [编译器支持](compilers.md)            |
| 跑测试、打包、发版           | [开发与发布](development.md)          |
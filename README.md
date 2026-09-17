# Antelope

[![CI](https://github.com/luskyle/antelope/actions/workflows/ci.yml/badge.svg)](https://github.com/luskyle/antelope/actions/workflows/ci.yml)
[![Pages](https://github.com/luskyle/antelope/actions/workflows/pages.yml/badge.svg)](https://luskyle.github.io/antelope/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.11%20%7C%203.13-blue.svg)](https://www.python.org/)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/logo-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/images/logo.svg">
  <img src="docs/images/logo.png" alt="Antelope" width="180">
</picture>

小巧敏捷的 C/C++ 编译链接工具。读一个 `antel.json`，把项目编成静态库、共享库或可执行程序；不生成 makefile，也不引入额外的构建语言。

## 特性

- **配置即构建脚本**：编译参数、链接参数、目标类型、编译器类型都写在 `antel.json` 里，可以随源码一起提交与评审
- **并行编译**：默认按 CPU 并行编译各编译单元（`jobs` 可调），并优先用 make 工具执行（`backend: auto`，没有 make 时自动回退内置执行器；仍由 antel 决定编什么）；同时输出 `compile_commands.json` 供 clangd 等工具使用
- **基于依赖的增量构建**：每个编译单元都记录 `-MMD` 依赖，改头文件只重编受影响的源文件，目标文件或依赖文件缺失时自动补编
- **第三方库零手抄**：`pkg_config: ["libcurl"]` 自动注入 `pkg-config` 的 `--cflags/--libs`，不手写 `-I`/`-l`
- **运行资源一键打包**：`data_files`（复制进输出目录）、`gresource`（GLib 资源编进二进制）、`embed`（任意二进制经 `ld -r -b binary` 嵌入）三种形态，支持目录分发与单文件分发；资源变化自动触发重编/重链
- **失败即中断**：编译、链接、分析、运行任一环节返回非 0 都立即终止，以非 0 退出码结束，不会把失败当成功
- **产物可追溯**：实际执行的编译命令与链接脚本落盘到 `log/`，附带符号表、动态依赖等分析结果，便于事后核查

## 安装

```bash
python3 antelope_install.py
```

## 快速开始

```bash
antel init       # 交互式生成 antel.json
antel rebuild    # 全量构建
antel build      # 只编发生变化的部分
antel run        # 运行生成的可执行程序
```

## 命令

| 命令      | 作用                                           |
| --------- | ---------------------------------------------- |
| init      | 交互式生成 antel.json                          |
| build     | 构建项目差异部分                               |
| rebuild   | 重新构建项目。不管项目有否被构建过，都重新构建 |
| clean     | 清除构建生成，包括所有中间文件与生成目标       |
| link      | 只链接而不编译                                 |
| analyze   | 自动分析指定的 c/c++ 源文件                    |
| run       | 执行编译后的结果                               |

除 init 外的命令都支持 `--file` / `-f` 指定配置文件，默认为 antel。

## 编译器支持

| compiler | 编译命令 | 静态库 | 共享库 / 可执行程序    |
| -------- | -------- | ------ | ---------------------- |
| gxx      | gcc/g++  | ✓      | g++ -shared / g++ -s   |
| llvm     | clang    | ✓      | clang++（未验证）      |
| msvc     | cl       | ✓      | 尚未实现，会直接报错   |

## 文档

完整文档在 [https://luskyle.github.io/antelope/](https://luskyle.github.io/antelope/)：

| 页面                                                       | 内容                                            |
| ---------------------------------------------------------- | ----------------------------------------------- |
| [快速开始](https://luskyle.github.io/antelope/quick-start/) | 安装、init、最小配置、构建与运行                |
| [配置参考](https://luskyle.github.io/antelope/configuration/) | antel.json 全部字段（含 pkg_config / data_files / gresource / embed）与构建目录布局 |
| [示例与效果图](https://luskyle.github.io/antelope/examples/) | GTK 计算器、资源打包演示的完整配置与运行效果 |
| [命令参考](https://luskyle.github.io/antelope/commands/)    | 各命令的参数、行为与退出码                      |
| [增量构建](https://luskyle.github.io/antelope/incremental-build/) | 什么时候重编，hash 基线与依赖文件如何工作  |
| [编译器支持](https://luskyle.github.io/antelope/compilers/) | gxx / llvm / msvc 与目标类型的支持细节          |
| [开发与发布](https://luskyle.github.io/antelope/development/) | 测试、打包、发版流程与工作流                  |

自带示例（`test/` 下，均可直接构建运行）：`helloworld`（单文件）、`cdemo`（多文件）、`gtkcalc`（libadwaita 计算器）、`resdemo`（资源打包 GUI 演示）。

## 开发

```bash
python3 -m pip install -e '.[test]'
python3 -m pytest
```

若环境中安装了会干扰 pytest 启动的第三方插件（例如 ROS 2 提供的 launch_testing），改用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest`。

文档站本地预览：

```bash
python3 -m pip install -r docs/requirements.txt
zensical serve
```

## 许可

[Apache-2.0](LICENSE)

项目 logo 使用 Microsoft [Fluent Emoji](https://github.com/microsoft/fluentui-emoji) 的山羊图标（MIT，经 Iconify 的 fluent-emoji-flat 集合取得）。文件都在 `docs/images/` 下：`logo.svg` 与 `logo-dark.svg` 分别是浅色底与深色底版本，`favicon.svg` 是站点图标（内置 prefers-color-scheme 深色分支），许可原文见 `LICENSE-fluent-emoji.txt`。
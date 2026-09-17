# 快速开始

## 安装

```bash
python3 antelope_install.py
```

安装脚本会构建 wheel 并用 `sudo pip` 把它装到系统解释器的可执行路径下，成功之后就有 `antel` 命令。不希望动系统环境时，也可以在虚拟环境里安装：

```bash
python3 -m pip install .
```

要求 Python 3.8 及以上。运行期依赖 `hash_calc`、`alive_progress`、`prompt_toolkit`、`click`，由 pip 自动解析。

## 初始化配置

在项目源码所在目录执行：

```bash
antel init
```

`init` 会用对话框依次询问配置文件名称、项目名、目标类型与编译器类型，然后生成 `antel.json`。默认定下的编译参数模板已经带上 `-fPIC`，可以直接用于共享库。

## 填写 antel.json

最小可用的配置长这样：

```json
{
  "projectName": "helloworld",
  "target_type": "exe",
  "compiler": "gxx",
  "source": ["helloworld.c"],
  "exclude_source": [],
  "include_directories": ["include"],
  "compile_args": ["-std=c++17", "-w", "-Os", "-fPIC"],
  "link_args": ["-lm"],
  "report": false
}
```

字段含义见[配置参考](configuration.md)，其中 `source` 与 `include_directories` 是增量构建的起点。

## 构建与运行

```bash
antel rebuild    # 全量构建，第一次或需要强制重建时用
antel build      # 只编发生变化的部分
antel run        # 运行生成的可执行程序（仅 exe 目标）
```

构建结果放在 `./<项目名>_<配置文件名>/` 下，例如上面的配置会得到：

```text
helloworld_antel/
├── helloworld          # 生成目标
├── obj/                # 目标文件与依赖文件
│   ├── helloworld.o
│   └── helloworld.o.d
└── log/                # 编译命令、链接脚本、hash 基线、符号分析
```

## 接下来

- 想搞明白「什么时候会重编、为什么」→ [增量构建](incremental-build.md)
- 要生成静态库或共享库 → [配置参考](configuration.md)与[编译器支持](compilers.md)
- 想用第三方库或打包运行资源 → [配置参考](configuration.md) 里的 `pkg_config` / `data_files` / `gresource` / `embed`
- 想看完整可运行的工程长什么样 → [示例与效果图](examples.md)（GTK 计算器、资源打包演示）
- 想接进 CI 或脚本 → [命令参考](commands.md)里的退出码约定
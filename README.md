# Antelope

![](images/logo.png)

小巧敏捷的编译链接工具。专注于编译各类 c/c++ 项目，以生成静态库、共享库、可执行程序。

## 安装

```bash
python3 antelope_install.py
```

安装会调用 `sudo pip`，把 `antel` 命令装到系统解释器的可执行路径下。

## 快速开始

切换到生成目录，如 `./test/`，初始化 `antel.json`

```bash
antel init
```

填写 antel.json 各项内容。其中各项含义如下表所示

| 参数名              | 含义                                                                            |
| ------------------- | ------------------------------------------------------------------------------- |
| projectName         | 项目名，任意字符，如 helloworld                                                 |
| source              | 参与项目编译的所有 c/c++ 文件相对编译位置的路径，如 ["helloworld.c"]            |
| exclude_source      | 保留字段，当前不参与构建                                                        |
| include_directories | 项目需引入的编译路径，其中的源文件会参与编译，头文件会参与变更检测              |
| target_type         | 生成的目标类型，可为 static，shared，exe。不区分大小写。                        |
| compiler            | 所用编译器类型，可为 msvc，gxx，llvm。不区分大小写。                            |
| compile_args        | 传递给编译器的编译参数。生成共享库时需自带 -fPIC，init 生成的模板已包含         |
| link_args           | 传递给连接器的链接参数，字符串数组，如 ["-ldl"]                                 |
| analyze_files       | 要自动分析的 c/c++ 源文件                                                       |

填写完毕后，执行命令

```bash
# 开始构建项目
antel rebuild
```

构建结果位于 `./{projectName}_{配置文件名}/` 下，其中 `obj/` 存放目标文件与依赖文件，`log/` 存放编译命令、链接脚本、hash 基线以及生成目标的符号、依赖分析结果。

## 命令

antel 可接受的参数如下表所示

| 参数名  | 含义                                           |
| ------- | ---------------------------------------------- |
| init    | 初始化 antel.json                              |
| build   | 构建项目差异部分                               |
| rebuild | 重新构建项目。不管项目有否被构建过，都重新构建 |
| clean   | 清除构建生成，包括所有中间文件与生成目标       |
| link    | 只链接而不编译                                 |
| analyze | 自动分析指定的 c/c++ 源文件                    |
| run     | 执行编译后的结果                               |

以上除 init 外的命令都支持 `--file` / `-f` 指定配置文件，默认为 antel。

## 增量构建

- 每个源文件编译时同步生成 `.d` 依赖文件（`-MMD -MF`），源文件与其 include 的头文件（含系统头文件之外的全部依赖）都参与变更检测
- hash 基线记录上次成功构建的全部输入文件，`antel build` 只重编发生变化的源文件，以及依赖了变化头文件的源文件
- 目标文件或依赖文件缺失时自动补编，`antel clean` 之后可直接用 `antel build` 全量构建
- 编译或链接返回非 0 时立即终止，以非 0 退出码结束，不会产出目标，也不会打印「链接完毕」。命令的完整输出记录在 `log/` 下的编译命令记录与 linkInfor 中

## 编译器支持情况

| compiler | 编译命令 | 链接                                                    |
| -------- | -------- | ------------------------------------------------------- |
| gxx      | gcc/g++  | ar / g++                                                |
| llvm     | clang    | ar / clang++（未验证）                                  |
| msvc     | cl       | ar；共享库与可执行程序尚未实现，会直接报错并退出        |

## 测试

```bash
python3 -m pip install -e '.[test]'
python3 -m pytest
```

若环境中安装了会干扰 pytest 启动的第三方插件（例如 ROS 2 提供的 launch_testing），改用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest`。
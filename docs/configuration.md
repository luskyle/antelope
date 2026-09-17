# 配置参考

`antel.json` 由 `antel init` 生成，也可以手写。全部字段如下：

| 字段                | 类型       | 必填 | 含义                                                                 |
| ------------------- | ---------- | ---- | -------------------------------------------------------------------- |
| projectName         | 字符串     | 是   | 项目名，同时决定输出目录名与生成目标名，不能为空，且只能含字母、数字、下划线、点与连字符 |
| source              | 字符串数组 | 是   | 参与编译的 c/c++ 源文件路径，相对配置文件所在目录，不能为空          |
| include_directories | 字符串数组 | 否   | 头文件搜索路径，作为 `-I` 传给编译器，其中的文件参与变更检测         |
| target_type         | 字符串     | 是   | `static`、`shared`、`exe`，不区分大小写                              |
| compiler            | 字符串     | 是   | `msvc`、`gxx`、`llvm`，不区分大小写                                  |
| compile_args        | 字符串数组 | 否   | 传给编译器的编译参数                                                 |
| link_args           | 字符串数组 | 否   | 传给链接器的链接参数，如 `["-ldl"]`，只能是字符串数组                |
| analyze_files       | 字符串数组 | 否   | `antel analyze` 要分析的目标文件所对应的源文件                       |
| jobs                | 整数       | 否   | 并行编译的单元数，默认 `min(8, CPU 核数)`；填 `1` 即串行             |
| backend             | 字符串     | 否   | 执行编译的工具，`auto`（默认：有 make 就用 make，没有则回退内置执行器）／`make`／`antel` |
| compile_commands    | 布尔       | 否   | 是否输出 `compile_commands.json`，默认 `true`                        |
| response_file       | 字符串     | 否   | 链接命令行过长时是否改用响应文件，`auto`（默认）／`always`／`never`  |
| exclude_source      | 字符串数组 | 否   | 保留字段，当前不参与构建                                             |

!!! warning "取值非法的字段会直接报错退出"
    `target_type` 与 `compiler` 只接受上表列出的取值，写错会以非 0 退出码结束并提示可选值；`source` 为空、`projectName` 为空或含非法字符、`link_args` 不是数组、`jobs` 不是正整数、`backend` 或 `response_file` 取值非法同样会报错。不存在「静默退回默认值」这种行为。

## 字段细节

### source

路径相对配置文件所在目录，子目录用 `/` 分隔：

```json
{
  "source": ["src/main.c", "src/util.c"]
}
```

每个源文件编译成 `obj/` 下的一个目标文件，命名规则是把路径分隔符替换成下划线：`src/main.c` → `obj/src_main.o`。因此 `src/main.c` 与 `src_main.c` 会撞到同一个目标文件名，需要避开。

### include_directories

两个作用：作为 `-I` 参数传给编译器；其中的 `.h`、`.c`、`.cc`、`.cpp` 参与变更检测，所以放在这里的头文件被修改后能被发现。

与源文件同目录的头文件不必写进来——它们由编译时生成的 `.d` 依赖文件覆盖，见[增量构建](incremental-build.md)。

### compile_args

原样拼进编译命令，写法与顺序由你负责：

- 生成共享库时必须带 `-fPIC`，`antel init` 的模板已包含，工具不会再自动追加
- `-std=`、`-O*`、`-w`、`-fno-rtti`、`-D` 宏定义等都写在这里

### link_args

```json
{
  "link_args": ["-lpthread", "-ldl"]
}
```

以 `-l` 开头的项会被识别为系统库，其余按原样追加到链接命令末尾。写成字符串（如 `"link_args": "-ldl"`）会被判为配置错误并直接报错退出。

### analyze_files

只影响 `antel analyze`：它对这里列出的每个源文件，用 `objdump -x` 分析对应的目标文件。

### jobs

并行编译的单元数，默认 `min(8, CPU 核数)`，填 `1` 即串行。并行只影响编译阶段的推进速度，不改变产物内容——同一份输入在串行与并行下产出的目标文件与可执行文件完全一致（测试里有断言）。代价是多进程输出会交错，需要按文件逐条阅读诊断信息时用 `jobs: 1`。

### backend

指定由谁来执行编译，默认 `auto`：**优先用 make，机器上没有 make 时自动回退到内置并行执行器**（会在配置摘要里标出实际用的执行器，例如 `auto → make` / `auto → antel（未找到 make）`）。也可显式填 `make` 或 `antel`。

无论哪种，**"编什么"始终由 antel 决定**（hash 基线 + `-MMD` 依赖），make 只负责把它们并行编完：

- antel 会生成一份内部规则文件 `<输出目录>/log/antel.mk`（每次构建重建、头部带"生成物勿改"标记）。它**不是交付物**，项目根不会出现 Makefile，也不需要你维护。
- 交给 make 之前，antel 会**先删掉本轮判定为过期的目标文件**。因为 make 按时间戳判定，实测把"已是最新"的目标交给它会被直接跳过；而按 hash 判定这些目标确实过期，删掉才能确保重建。
- make 的完整输出记录在 `<输出目录>/log/<项目名>.make`。
- 两种执行器的产物一致（测试里对可执行文件做了字节比对）。

实测（150 个编译单元、8 核）：两种执行器耗时基本持平（约 1.1–1.3 秒）。用 make 的收益不在于更快，而在于与 make 工具链的一致性（可以手工 `make -f <输出目录>/log/antel.mk` 复现同一次编译）。

#### 从 make 里调用 antel

如果 antel 是被 make 调用的（环境里有 `MAKEFLAGS`），它不会在内部再叠加并行：内置执行器退回 `jobs: 1`，make 执行器则**不传 `-j`**，把并行度交给外层——否则会覆盖外层预算。

已知限制：make 的 jobserver 管道不会穿过 antel 传给它启动的子 make（Python 启动子进程时会关闭继承的文件描述符），因此嵌套 make 会打印 `jobserver 不可用: 正使用 -j1` 并串行执行。这是**安全方向**的降级（不会超额并行），代价是这一层失去并行；需要共享 jobserver 时，请让外层用 `+` 前缀并等后续批次补上 fd 透传。

### compile_commands

默认 `true`，每次构建都会重写 `<输出目录>/compile_commands.json`，逐条记录每个编译单元完整的命令行（给结构化 `arguments`，不用在含空格路径上不可靠的 `command` 字符串）。clangd 只在源码目录树里查找这个文件，因此需要显式指向输出目录，二选一：

```bash
# 方式一：启动参数
clangd --compile-commands-dir=<输出目录>
```

```yaml
# 方式二：项目根放一份 .clangd
CompileFlags:
  CompilationDatabase: <输出目录>
```

### response_file

链接命令行过长时（默认阈值 10 万字符，例如对象文件极多）改用响应文件传参：`auto` 只在超阈值时启用，`always` 始终启用，`never` 关闭。`ar` 不支持响应文件，静态库链接不会走这条路。

## 构建目录

输出目录是 `./<projectName>_<配置文件名>/`：配置文件名 `antel.json`、项目名 `helloworld`，输出目录就是 `helloworld_antel/`。

| 路径 | 内容 |
| --- | --- |
| `<输出目录>/<项目名>` | 可执行目标（`exe`） |
| `<输出目录>/lib<项目名>.a`、`lib<项目名>.so` | 静态库、共享库目标 |
| `<输出目录>/obj/*.o` | 目标文件 |
| `<输出目录>/obj/*.o.d` | 每个编译单元的依赖文件，由 `-MMD -MF` 生成 |
| `<输出目录>/compile_commands.json` | 供 clangd 等工具解析的编译数据库，可用 `compile_commands: false` 关闭 |
| `<输出目录>/log/hashes` | hash 基线，记录上次成功构建的全部输入文件 |
| `<输出目录>/log/hashes_diff` | 本次相对基线发生变化的文件及前后 hash |
| `<输出目录>/log/stale_files` | 本次实际需要重新编译的源文件清单 |
| `<输出目录>/log/<项目名>.<compiler>` | 本次执行的完整编译命令 |
| `<输出目录>/log/antel.mk` | 内部规则文件（`backend: make` 时生成，每次构建重建，不是交付物） |
| `<输出目录>/log/<项目名>.make` | 用 make 执行编译时的完整输出 |
| `<输出目录>/log/<项目名>_link.sh` | 本次执行的链接脚本，链接就是执行这个脚本 |
| `<输出目录>/log/<项目名>_link.rsp` | 链接命令行过长时使用的响应文件（`response_file` 控制） |
| `<输出目录>/log/linkInfor` | 链接过程的完整输出 |
| `<输出目录>/log/readelf_*`、`ldd_*`、`nm_*`、`symbol_*`、`archive_*`、`objdump_*` | 生成目标的符号表、动态依赖、归档内容等分析结果 |
| `<输出目录>/log/<obj>/objdump-x` | `antel analyze` 对单个目标文件的分析结果 |

`antel clean` 会删除整个输出目录，包括生成目标与上表全部内容。
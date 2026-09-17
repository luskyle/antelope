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
| analyze_files       | 字符串数组 | 否   | **已废弃**：报告自动覆盖全部源文件，此字段不再读取              |
| report              | 布尔       | 否   | 构建成功后自动生成可视化报告 `report.html`（默认 `false`），不参与编译 |
| jobs                | 整数       | 否   | 并行编译的单元数，默认 `min(8, CPU 核数)`；填 `1` 即串行             |
| backend             | 字符串     | 否   | 执行编译的工具，`auto`（默认：有 make 就用 make，没有则回退内置执行器）／`make`／`antel` |
| compile_commands    | 布尔       | 否   | 是否输出 `compile_commands.json`，默认 `true`                        |
| response_file       | 字符串     | 否   | 链接命令行过长时是否改用响应文件，`auto`（默认）／`always`／`never`  |
| pkg_config          | 字符串数组 | 否   | 外部库清单，逐包注入 `pkg-config` 的 `--cflags/--libs` 输出，如 ["libcurl"] |
| data_files          | 数组       | 否   | 运行资源复制进输出目录，字符串（`from==to`）或 `{"from": 源, "to": 目标}` |
| gresource           | 字符串     | 否   | GLib 资源描述文件（`.gresource.xml`），资源编进可执行文件（单文件分发） |
| embed               | 字符串数组 | 否   | 任意二进制嵌入可执行文件（单文件分发），程序用 `_binary_` 符号访问 |
| sanitize            | 字符串数组 | 否   | 消毒器清单，每个元素编译与链接都加 `-fsanitize=<item>`，如 ["address"] |
| coverage            | 布尔       | 否   | 是否插桩覆盖率：编译加 `-fprofile-arcs -ftest-coverage`，链接加 `--coverage` |
| version             | 字符串     | 否   | 共享库版本号（如 `"1.0.0"`），产出 `libX.so.<版本>` 并生成软链 |
| soname              | 字符串     | 否   | 共享库 soname（如 `"libX.so.1"`），缺省由 version 主版本推导 |
| rpath               | 字符串数组 | 否   | 链接时加 `-Wl,-rpath,<path>`，便于按 soname 加载共享库 |
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

**已废弃**：早期版本用它指定「antel analyze 要分析哪些源文件」。现在的分析报告自动覆盖配置里的全部源文件，此字段不再读取，可以放心删掉。模板已换成 `report`。

### report

构建成功后自动生成可视化分析报告（`<输出目录>/report.html`）：

```json
{
    "report": true
}
```

- **不参与编译**：不加任何编译参数、产物字节与 `report: false` 完全一致、也不进 hash 基线——只是构建成功后多跑一次分析
- 需要随时手动生成时用 `antel analyze`，效果与 `report: true` 的构建一样
- 报告内容见[命令参考](commands.md)的 analyze 一节

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

### pkg_config

外部库清单，例如 `["libcurl", "sqlite3"]`。构建时对每个包运行 `pkg-config --cflags/--libs`，把输出注入编译与链接命令：

- `--cflags` 的 `-I` / `-D` 等追加在每个编译命令里（排在你的 `compile_args` 之后，所以你的 `-I` 优先级更高），同时进入 `compile_commands.json`，clangd 也受益
- `--libs` 的 `-L` / `-l` 追加在链接命令末尾（静态库的 `ar` 归档不参与链接，天然跳过）

包不存在、或机器上没有 pkg-config 命令时直接报错退出，不会静默丢参数。

### data_files

运行资源（图片、配置文件、脚本等）在构建时复制进输出目录，程序按相对路径读取。适合可替换、体积大的资源。写法二选一：

```json
{
  "data_files": ["assets"]
}
```

```json
{
  "data_files": [
    {"from": "assets", "to": "assets"},
    {"from": "config/settings.ini", "to": "settings.ini"}
  ]
}
```

- 字符串形态：`from` 与 `to` 同名，源目录整体复制（保持内部结构），源文件按名复制
- 对象形态：`from` 是项目目录下的源，`to` 是输出目录下的目标；目标是目录或文件由源决定
- 源文件进入 hash 基线：修改后 `antel build` 会重新同步
- `antel clean` 连同输出目录一并回收

### gresource

GLib 资源，把图片、CSS、UI 描述等编译成 C 源码再编进可执行文件——**单文件分发**，拷走一个二进制就带全资源。需要 `glib-compile-resources`（GTK 开发包通常自带）：

```json
{
  "gresource": "gresource.gresource.xml"
}
```

`gresource.gresource.xml` 里 `<gresource prefix="/io/github/luskyle/app">` 指定访问前缀，`<file>` 列资源路径。gio 绑定由 `pkg_config` 提供，如 `"pkg_config": ["libadwaita-1"]`。程序里直接用 GResource API 读取：

```c
GBytes *bytes = g_resources_lookup_data("/io/github/luskyle/app/img/logo.png",
                                         G_RESOURCE_LOOKUP_FLAGS_NONE, NULL);
```

生成的 `gresource.c` 作为普通编译单元参与构建，它的 hash 进入基线：改资源文件 → 自动重新生成、重编、重链。生成的代码自带 ELF constructor，资源无需手动注册。工作目录在构建时是项目根，xml 内相对路径以它为准；`antel clean` 回收生成物。

### embed

任意二进制（图片、模型、按键映射等）用 `ld -r -b binary` 嵌入可执行文件，**单文件分发**。适合非 GLib 的通用 C/C++ 工程：

```json
{
  "embed": ["assets/logo.png", "assets/firmware.bin"]
}
```

C 代码里用自动生成的符号访问，符号名是路径（非字母数字字符全换成下划线）加上 `_binary_` 前缀与 `_start`/`_end`/`_size` 后缀：

```c
/* assets/logo.png → _binary_assets_logo_png_start/_end */
extern const unsigned char _binary_assets_logo_png_start[];
extern const unsigned char _binary_assets_logo_png_end[];
```

嵌入文件进入 hash 基线：修改后 `antel build` 会重新生成 `.o` 并重链接（即使没有源文件变化）。产物在 `<输出目录>/obj/embed_<序号>.o`，随 `antel clean` 回收。

### sanitize

消毒器开关，编译与链接同时生效（链接阶段必须带工具链运行时，例如 ASan 的 `libasan`）：

```json
{
  "sanitize": ["address", "undefined"]
}
```

每个元素对应一条 `-fsanitize=<item>`，追加在每个编译单元与链接命令里。可以组合多个：

- `address`：内存错误检测（越界、use-after-free）
- `undefined`：未定义行为检测
- `leak`、`thread` 等均按 `-fsanitize=` 语义透传，工具链不支持时直接报错

!!! warning "启用消毒器要关优化"
    带 `-O1` 以上优化时，GCC 会把未定义行为的访问直接优化掉，ASan 插桩也随之消失，导致检测不到。调试内存问题时请配合 `-O0 -g`（见 `test/antelstats/san.json` 的完整做法）。

### coverage

覆盖率插桩：

```json
{
  "coverage": true
}
```

编译加 `-fprofile-arcs -ftest-coverage`（生成 `.gcno`），链接加 `--coverage`。运行一次可执行程序后，与之对应的 `.gcda` 落在 `obj/` 里（与 `.gcno` 同目录），之后即可用 `gcov`（或 lcov）出报告：

```bash
antel rebuild && antel run
cd <输出目录>/obj && gcov <对应目标>.gcda
```

`.gcno`/`.gcda` 都在输出目录内，`antel clean` 一并回收。

### version / soname / rpath 版本化动态库

`target_type: shared` 时，给库一个版本号，antel 就产出 `libX.so.<版本>` 并生成软链：

```json
{
  "target_type": "shared",
  "version": "1.0.0"
}
```

产物与链接参数：

- 真实文件 `libX.so.1.0.0`（链接命令带 `-Wl,-soname,libX.so.1`，soname 由主版本号推导）
- 软链 `libX.so.1 -> libX.so.1.0.0`、`libX.so -> libX.so.1`，供编译期 `-lX` 与运行期按 soname 查找
- 显式指定 `soname` 优先于推导，例如 `"soname": "libcustom.so.3"`
- `GENERATED_TARGETS` 已覆盖 `*.so.*`，rebuild/clean 会回收版本化文件与软链

**消费端**：可执行程序依赖这个库时，用 `link_args` 指到库目录、用 `rpath` 让运行期能找到（`test/antelstats/app.json` 是完整示例）：

```json
{
  "link_args": ["-Lantelstats_antel", "-lantelstats"],
  "rpath": ["$ORIGIN/../antelstats_antel"]
}
```

`$ORIGIN` 在运行期展开成可执行文件所在目录，因此 `rpath` 支持相对定位，拷走整个输出目录树也能跑。验证：`readelf -d` 若显示 SONAME 且 `ldd` 能按它解析，说明版本化链路是通的。

## 一个完整的配置示例

把上面所有字段放在一起，一个「GUI 可执行程序 + 第三方库 + 三种资源形态」的完整配置（取自 `test/resdemo`，运行效果见[示例与效果图](examples.md)）：

```json
{
    "projectName": "resdemo",
    "target_type": "exe",
    "compiler": "gxx",
    "source": ["src/main.c"],
    "exclude_source": [],
    "include_directories": ["include"],
    "compile_args": ["-O2", "-Wall"],
    "link_args": ["-lm"],
    "jobs": 8,
    "backend": "auto",
    "compile_commands": true,
    "report": false,
    "pkg_config": ["libadwaita-1"],
    "data_files": ["assets"],
    "gresource": "gresource.gresource.xml",
    "embed": ["assets/payload.bin"]
}
```

## 构建目录

输出目录是 `./<projectName>_<配置文件名>/`：配置文件名 `antel.json`、项目名 `helloworld`，输出目录就是 `helloworld_antel/`。

| 路径 | 内容 |
| --- | --- |
| `<输出目录>/<项目名>` | 可执行目标（`exe`） |
| `<输出目录>/lib<项目名>.a`、`lib<项目名>.so` | 静态库、共享库目标 |
| `<输出目录>/obj/*.o` | 目标文件 |
| `<输出目录>/obj/*.o.d` | 每个编译单元的依赖文件，由 `-MMD -MF` 生成 |
| `<输出目录>/obj/embed_<序号>.o` | `embed` 嵌入的二进制目标（参与链接，随 clean 回收） |
| `<输出目录>/gresource.c` | `gresource` 生成的资源源码（作为编译单元参与构建） |
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
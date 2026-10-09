# 示例与效果图

仓库自带的示例工程都在 `demos/` 下，都是真实可构建、可运行的项目。下面的效果图与配置一一对应，照抄即可复现。

## gtkcalc：GTK 计算器（`pkg_config` 集成）

位置：`demos/gtkcalc/`。一个用 libadwaita（GTK 4）写的计算器，演示最常见的图形项目形态：**GUI + 外部库**。它不手写任何 `-I`/`-l`，全靠 `pkg_config` 注入。

![gtkcalc 界面](images/demo_gtkcalc.png)

**antel.json**（`demos/gtkcalc/antel.json`）：

```json
{
    "projectName": "gtkcalc",
    "target_type": "exe",
    "compiler": "gxx",
    "source": [
        "main.c"
    ],
    "exclude_source": [],
    "include_directories": [],
    "compile_args": [
        "-O2",
        "-Wall"
    ],
    "link_args": [],
    "report": false,
    "pkg_config": [
        "libadwaita-1"
    ]
}
```

**配置要点**：

- `pkg_config: ["libadwaita-1"]`：构建时 antel 自动执行 `pkg-config --cflags/--libs libadwaita-1`，把 `-I/usr/include/libadwaita-1` 等编译参数注入每个编译单元，把 `-ladwaita-1 -lgtk-4 ...` 追加到链接命令末尾。装好 libadwaita 开发包后一行配置就能编
- 装依赖（Ubuntu 22.04）：

  ```bash
  sudo apt install libadwaita-1-dev
  ```

- 构建与运行：

  ```bash
  cd demos/gtkcalc
  antel rebuild
  ./.antel/build/gtkcalc_antel/gtkcalc
  ```

- 程序还带了 `--auto-close N`（秒）参数用于无人值守验证，例如 CI 里 `./.antel/build/gtkcalc_antel/gtkcalc --auto-close 3` 会打开窗口 3 秒后自行退出

!!! note "libadwaita 1.1 的几个 API 约束（代码已适配）"
    这套 demo 按 Ubuntu 22.04 自带的 libadwaita 1.1 / GTK 4.6 编写，有三个新手容易踩的点，源码里都有注释：

    1. `AdwApplicationWindow` **没有标题栏区域**——窗口按钮（关闭/最小化/最大化）来自内容顶部的 `AdwHeaderBar`，调 `gtk_window_set_titlebar` 会被 libadwaita 拒绝并崩溃；
    2. 内容必须用 `adw_application_window_set_content` 设置，`gtk_window_set_child` 同样被拒绝；
    3. `g_application_run` 会解析并拒绝未知命令行选项，自定义参数（如 `--auto-close`）要先从 argv 里剥掉。

## resdemo：运行资源打包（`data_files` / `gresource` / `embed`）

位置：`demos/resdemo/`。一个程序同时用三种形态携带资源，界面本身也由资源驱动，用来演示完整的资源分发方案：

- **data_files —— 目录分发**：`assets/` 复制进输出目录，可替换；程序按 `/proc/self/exe` 定位（与当前工作目录无关）
- **gresource —— 单文件分发**：整个界面（`main.ui`）、样式（`style.css`）、图标（`logo.png`）、文本（`notes.txt`）全部编译进可执行文件，GtkBuilder / CSS provider 直接按资源路径加载
- **embed —— 单文件分发**：`assets/payload.bin` 经 `ld -r -b binary` 嵌入 ELF，程序用 `_binary_` 符号访问

![resdemo 界面](images/demo_resdemo.png)

**antel.json**（`demos/resdemo/antel.json`）：

```json
{
    "projectName": "resdemo",
    "target_type": "exe",
    "compiler": "gxx",
    "source": [
        "src/main.c"
    ],
    "exclude_source": [],
    "include_directories": [],
    "compile_args": [
        "-O2",
        "-Wall"
    ],
    "link_args": [],
    "report": false,
    "pkg_config": [
        "libadwaita-1"
    ],
    "data_files": [
        "assets"
    ],
    "gresource": "gresource.gresource.xml",
    "embed": [
        "assets/payload.bin"
    ]
}
```

**配套文件结构**：

```text
demos/resdemo/
├── antel.json                 # 上面的配置
├── gresource.gresource.xml    # gresource 清单（prefix 与文件别名）
├── assets/
│   ├── banner.txt             # data_files 复制；gresource XML 里未引用
│   ├── logo.png               # gresource 引用，同时也会被 data_files 复制（无妨）
│   └── payload.bin            # embed 嵌入；gresource XML 里未引用
├── data/
│   ├── ui/main.ui             # GtkBuilder 界面描述（gresource 引用）
│   ├── css/style.css          # 界面样式（gresource 引用）
│   └── share/notes.txt        # 运行期读取的文本（gresource 引用）
└── src/main.c                 # 三种形态的读取代码
```

**gresource.gresource.xml**：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gresources>
  <gresource prefix="/com/antelope/demo">
    <file alias="ui/main.ui">data/ui/main.ui</file>
    <file alias="css/style.css">data/css/style.css</file>
    <file alias="img/logo.png">assets/logo.png</file>
    <file alias="share/notes.txt">data/share/notes.txt</file>
  </gresource>
</gresources>
```

**三种形态的取舍**：

| 形态 | 分发形态 | 适合 | 程序侧访问 |
| --- | --- | --- | --- |
| `data_files` | 目录（资源在可执行文件旁边） | 可替换、体积大、要热更新的资源 | 普通文件读取（相对 `/proc/self/exe` 定位） |
| `gresource` | 单文件（编进二进制） | GTK/GLib 工程的界面、样式、图标、文本 | `g_resources_lookup_data` / `gtk_builder_new_from_resource` |
| `embed` | 单文件（编进二进制） | 任意二进制：固件、字体、按键映射、配置文件 | `_binary_<路径转下划线>_start/_end/_size` 符号 |

**增量行为**（这也是写进测试里的契约）：

- 改 `assets/banner.txt` → `antel build` 重新同步拷贝
- 改 `assets/payload.bin` → 没有任何编译单元变 stale，但**资源变化会驱动重链接**，程序内嵌内容跟着更新
- 改 `data/css/style.css` 或 `data/share/notes.txt` → gresource 源重新生成 → 重编 gresource 单元 → 重链接

**构建与运行**：

```bash
cd demos/resdemo
antel rebuild
./.antel/build/resdemo_antel/resdemo
```

窗口内左下角的开关切换深色/浅色主题（颜色来自 gresource 编进去的 `style.css`），右侧按钮重新从磁盘读取 `data_files` 的 banner——两个交互都演示「改资源 → build → 界面跟着变」。

### 日志与构建产物分析

构建时每个环节都会落盘一份可复核的产物，`antel analyze` 把这些数据汇总成一页可视化报告。这是 resdemo 构建后 `demos/resdemo/.antel/build/resdemo_antel/log/` 下的实际内容：

| 文件 | 内容 |
| --- | --- |
| `resdemo.gxx` | 本次执行的完整编译命令（gcc ... `-I/usr/include/libadwaita-1` ... `-o .antel/build/resdemo_antel/obj/src_main.o`） |
| `resdemo.make` | 走 make 后端时的完整输出（实际编译是否跳过/重编） |
| `antel.mk` | 内部规则文件（生成物勿改；手工 `make -f` 可复现同一次编译） |
| `resdemo_link.sh` | 链接脚本，链接就是执行这个脚本——能提前看到 `-ladwaita-1 -lgtk-4 ...` 全部库依赖 |
| `linkInfor` | 链接过程的完整输出，链接失败时的第一现场 |
| `hashes` | hash 基线，记录上次成功构建的全部输入文件与 md5 |
| `report.html` | `antel analyze` 生成的可视化分析报告（自包含单文件，浏览器打开） |

**用报告逐项核对 resdemo**（`antel analyze` 后打开 `.antel/build/resdemo_antel/report.html`）：

- **资源情况**：展开到文件级——10 个资源文件，`data_files` 3 项（banner.txt/logo.png/payload.bin 的类型与大小）、`gresource` 6 项（XML + main.ui/style.css/logo.png/notes.txt + 生成的 `gresource.c` 142.3 KB）、`embed` 1 项（payload.bin 128 B + `_binary_assets_payload_bin` 符号）；每种资源带 ✓ 已复制/已编入/已嵌入状态
- **目标符号表**：98 个符号按 nm 类型分类（函数/数据/BSS/未定义引用），`t exec_dir`、`T main` 等每个符号一个独立 chip
- **编译参数统计**：`-O2×2  -Wall×2`（配合 -I 头文件路径），一眼确认优化级别与警告开关
- **动态依赖**：NEEDED 列出 `libadwaita-1.so.0 libgtk-4.so.1 libgio-2.0.so.0 ...`，下面是 ldd 完整解析（每条含地址与路径）
- **增量状态**：hash 基线是否存在、本次变化文件、待重编清单——与 `log/hashes`、`log/hashes_diff`、`log/stale_files` 一一对应
- **头文件依赖**：从 `obj/*.o.d` 反推 `src/main.c` 依赖的头文件

**排查路径**：改坏代码 → `antel rebuild` 失败 → 先看 `log/<项目名>.gxx` 的编译命令、再看 `report.html` 的诊断汇总；链接失败 → `log/linkInfor` + 链接脚本；怀疑增量判断 → `log/hashes_diff` 与 `log/stale_files`。所有数据都是真实工具（`file`/`nm`/`readelf`/`ldd`/`gcov`）的输出，可直接复核。

!!! note "为什么能放心走增量"
    `glib-compile-resources` 对同样的输入生成**逐字节相同**的输出（已实测），因此 gresource 源可以安全进入 antel 的 hash 基线；`ld -r -b binary` 的符号命名是确定的规则：`assets/payload.bin` → `_binary_assets_payload_bin_start/_end/_size`（路径里非字母数字字符全部换成下划线）。这两条是设计文档（DESIGN.md）与测试里明确的契约。

## libyaml：公开上游项目（ref）

位置：`demos/libyaml/`。这个示例通过 `ref` 获取公开的 libyaml `release/0.2.5`
分支，并由 Antelope 编译 8 个 C 源文件。配置显式列出源文件和头文件路径；原先由
CMake 生成的版本宏改为直接传给编译器，因此不需要 CMakeLists 或生成头文件。

首次构建需要网络和 Git：

```bash
cd demos/libyaml
antel rebuild
```

上游源码缓存在 `.antel/refs/libyaml`，静态库位于 `.antel/build/yaml_antel/libyaml.a`。引用缓存
不会被 `antel clean` 删除。

## cJSON：公开 JSON 库（ref）

位置：`demos/cjson/`。示例通过 `ref` 获取 cJSON 的公开 `master` 分支，由 Antel 将
核心解析器和 JSON Utils 分别编译成静态/共享库，并构建上游 Unity 库、`cJSON_test`、
`parse_examples` 和 `old_utils_tests`，共 8 个目标。不添加本地入口程序，也无需 CMake。

```bash
cd demos/cjson
antel fetch-ref
antel rebuild
for config in shared utils-static utils-shared unity demo parse-examples utils-tests; do
    antel rebuild -f "$config" || exit 1
done
ar t .antel/build/cjson_antel/libcjson.a
./.antel/build/cJSON_test_demo/cJSON_test
(cd .antel/build/parse_examples_parse-examples && ./parse_examples)
./.antel/build/old_utils_tests_utils-tests/old_utils_tests
```

首次运行需要 Git 和网络。源码缓存在 `.antel/refs/cjson`；直接运行 `antel rebuild`
也会在编译前自动下载缺失的引用。
解析测试的输入文件通过 `data_files` 部署，必须先预取源码，并从该测试输出目录运行。
两个测试程序分别验证 15 项解析用例和 6 组 Utils 用例；可执行文件通过相对 rpath
加载本地构建的共享库。此示例选择上游目标的代表性子集，不覆盖全部测试或 fuzzing。
配置依赖按上述顺序构建；完整目标清单和版本说明见
[`demos/cjson/README.md`](https://github.com/luskyle/antelope/blob/main/demos/cjson/README.md)。

## libpng：static/shared 双目标（ref）

位置：`demos/libpng/`。对应上游 CMake 默认的 `PNG_STATIC=ON` 和 `PNG_SHARED=ON`，
分别由 `static.json`、`shared.json` 构建静态库和版本化共享库。
当前 x86_64 target 还启用 `PNG_INTEL_SSE_OPT` 并编译两个 SSE2 源文
件。`shared.json` 通过 `pkg_config` 链接 zlib；静态归档的使用者还需自行链接 zlib 和
libm。`before_build` 使用上游预置配置头，并通过 C 预处理器和 AWK 生成 ELF version
script；libpng 目标不需要 CMake。

完整的生成机制、PNG 窗口应用、独立安装与卸载见[成功案例：libpng](libpng-case-study.md)。

```bash
cd demos/libpng
antel fetch-ref -f static
python3 prepare_icc_fixture.py
antel rebuild -f static
antel rebuild -f shared
ar t .antel/build/png16_static/libpng16.a | wc -l
readelf -d .antel/build/png16_shared/libpng16.so.16.60.git | grep SONAME
```

两个库 target 各包含 17 个上游对象。共享库产物是 `libpng16.so.16.60.git`，SONAME
为 `libpng16.so.16`，并生成 `libpng16.so.16` 与 `libpng16.so` 软链。首次构建需要
Git、Python 3、C 编译器、AWK、pkg-config、网络和 zlib 开发包；配置头和 ELF version
script 均由 `before_build` 自动生成，实际编译由 Antel 完成。

上游 CMake 还注册了 6 个测试程序和 2 个工具，分别对应 `pngtest.json`、
`pnggetset.json`、`pngvalid.json`、`pngstest.json`、`pngunknown.json`、
`pngimage.json`、`pngfix.json`、`png-fix-itxt.json`。每个配置独立链接上面的 shared
target：

```bash
for target in pngtest pnggetset pngvalid pngstest pngunknown pngimage pngfix png-fix-itxt; do
    antel rebuild -f "$target"
done
```

带图片输入的配置通过 `data_files` 把上游测试图片复制到自己的输出目录：pngtest、
pngunknown、pngfix、png-fix-itxt 和三个图像例程使用 `pngtest.png`；pngimage 复制
pngsuite，pngstest 复制 testpngs。`iccfrompng` 使用 `prepare_icc_fixture.py` 生成的
带 iCCP profile 测试图。新 checkout 首次构建这些配置前，先执行 `antel fetch-ref -f
static`，让 `data_files` 源路径存在。

示例运行（输入均从各自输出目录读取）：

```bash
./.antel/build/pngtest_pngtest/pngtest .antel/build/pngtest_pngtest/testdata/pngtest.png /tmp/png-roundtrip.png
./.antel/build/pnggetset_pnggetset/pnggetset
./.antel/build/pngvalid_pngvalid/pngvalid --gamma-16-to-8
./.antel/build/pngunknown_pngunknown/pngunknown --strict default=discard .antel/build/pngunknown_pngunknown/testdata/pngtest.png
./.antel/build/pngimage_pngimage/pngimage --list-combos --log .antel/build/pngimage_pngimage/testdata/pngsuite/basn0g08.png
./.antel/build/pngstest_pngstest/pngstest --log --tmpfile /tmp/ps- .antel/build/pngstest_pngstest/testdata/testpngs/gray-1.png
./.antel/build/pngfix_pngfix/pngfix --quiet .antel/build/pngfix_pngfix/testdata/pngtest.png
./.antel/build/png-fix-itxt_png-fix-itxt/png-fix-itxt < .antel/build/png-fix-itxt_png-fix-itxt/testdata/pngtest.png > /tmp/png-fixed.png
```

另有 4 个不属于上游 CMake target 的 `contrib/examples` 程序，也提供了单独配置：
`example-iccfrompng`、`example-pngpixel`、`example-pngtopng`、`example-simpleover`。
例如：

```bash
for target in example-iccfrompng example-pngpixel example-pngtopng example-simpleover; do
    antel rebuild -f "$target"
done
./.antel/build/iccfrompng_example-iccfrompng/iccfrompng .antel/build/iccfrompng_example-iccfrompng/testdata/icc-profile.png
./.antel/build/pngpixel_example-pngpixel/pngpixel 0 0 .antel/build/pngpixel_example-pngpixel/testdata/pngtest.png
./.antel/build/pngtopng_example-pngtopng/pngtopng .antel/build/pngtopng_example-pngtopng/testdata/pngtest.png /tmp/pngtopng.png
./.antel/build/simpleover_example-simpleover/simpleover .antel/build/simpleover_example-simpleover/testdata/background.png /tmp/simpleover.png
```

## yaml-cpp：C++ YAML 库（ref）

位置：`demos/yaml-cpp/`。通过 `ref` 获取 yaml-cpp `master`，用 C++11 将上游核心及
contrib 源文件编译成静态库，不添加本地 consumer。

```bash
cd demos/yaml-cpp
antel rebuild
ar t .antel/build/yaml-cpp_antel/libyaml-cpp.a | wc -l
```

首次构建需要 Git 和网络。

## json-c：库、命令行工具和测试目标（ref + Python 配置探测）

位置：`demos/json-c/`。json-c 需要平台探测生成的头文件；各 Antel 配置通过
`before_build` 自动调用 `prepare_json_c.py`，由该脚本使用 C 编译器探测平台并直接生成
配置头文件。不使用 CMake。
Antel 构建静态/共享库、上游 `json_parse` 工具，以及解析、JSON Pointer、JSON Patch
三个代表性测试目标。

```bash
cd demos/json-c
antel fetch-ref
antel rebuild
for config in shared json-parse test-parse test-json-pointer test-json-patch; do
    antel rebuild -f "$config" || exit 1
done
ar t .antel/build/json-c_antel/libjson-c.a | wc -l
printf '{"library":"json-c","built_by":"Antel"}\n' | ./.antel/build/json_parse_json-parse/json_parse
TEST_PARSE_CHUNKSIZE=7 ./.antel/build/test_parse_test-parse/test_parse
./.antel/build/test_json_pointer_test-json-pointer/test_json_pointer
./.antel/build/test_json_patch_test-json-patch/test_json_patch .antel/build/test_json_patch_test-json-patch/testdata
```

两种库均由相同的 14 个上游编译单元构建；测试程序通过相对 rpath 加载本地共享库。
JSON Patch fixtures 通过 `data_files` 部署。完整清单见
[`demos/json-c/README.md`](https://github.com/luskyle/antelope/blob/main/demos/json-c/README.md)。

## libuv：Linux 事件循环（ref）

位置：`demos/libuv/`。上游默认提供共享库 `uv` 和静态库 `uv_a`；启用测试时还会定义
共享/静态测试运行器和静态 benchmark runner。`prepare_libuv.py` 根据 ref 中的 Linux
源文件生成 Antel 配置，实际编译全部由 Antel 完成，不调用 CMake。

```bash
cd demos/libuv
antel fetch-ref
python3 prepare_libuv.py
antel rebuild
antel rebuild -f shared
antel rebuild -f tests-static
antel rebuild -f tests-shared
antel rebuild -f benchmarks
```

产物包括 `.antel/build/uv_antel/libuv.a`、版本化共享库
`.antel/build/uv_shared/libuv.so.1.0.0`、两个测试运行器和 benchmark runner。测试配置包含
185 个 Linux 上游测试源文件；consumer 链接静态库需 pthread、dl 和 rt。

## libgit2：大型 Git 库（ref + Python 配置生成）

位置：`demos/libgit2/`。`prepare_antelope.py` 直接选择 Linux 源文件、生成 feature header
和目标配置，由 Antel 构建上游静态库、版本化共享库、CLI、`lg2` 示例和两个测试运行器。
整个构建过程不调用 CMake；测试目标使用上游 Clar Python 脚本生成测试清单。

```bash
cd demos/libgit2
antel fetch-ref -f generated
python3 prepare_antelope.py

antel rebuild -f generated       # 静态库
antel rebuild -f shared          # 版本化共享库
antel rebuild -f cli             # git2 CLI
antel rebuild -f lg2             # 上游示例程序
antel rebuild -f tests-libgit2   # 离线 libgit2 测试
antel rebuild -f tests-util      # util 测试

ar t .antel/build/git2_generated/libgit2.a | wc -l
readelf -d .antel/build/git2_shared/libgit2.so.1.9.0 | grep SONAME
./.antel/build/git2_cli/git2 version
ldd .antel/build/lg2_lg2/lg2 | grep libgit2
(cd .antel/build/libgit2_tests_tests-libgit2 && ./libgit2_tests)
(cd .antel/build/util_tests_tests-util && ./util_tests -v)
```

静态库包含 196 个对象，共享库 SONAME 为 `libgit2.so.1.9`；`lg2` 通过相对 rpath
链接共享库，CLI 和测试运行器链接 Antel 构建的静态库。libgit2 测试运行器排除了
online、stress、performance 测试。构建需要 Linux、Git、Python 3 及 OpenSSL、PCRE、
zlib 开发包和 pthread。所有目标配置都声明同一个 `ref`，初始 ref 定义在
`generated.json`，不需要单独的 `refs.json`。更多目标细节见
[`demos/libgit2/README.md`](https://github.com/luskyle/antelope/blob/main/demos/libgit2/README.md)。

## antelstats：共享库与消费者

位置：`demos/antelstats/`。一个统计分析小工具：共享库 `libantelstats` 提供均值/标准差/中位数等统计函数，可执行程序调用它打印报表。**只用了两个配置文件**——库的生产形态与可执行程序的消费形态——没有其他花活；示例数据直接写死在 `main.c` 里，运行不需要任何外部文件。

```text
demos/antelstats/
├── antel.json    # 版本化共享库 libantelstats.so.1.0.0（多文件：stats/csv/version）
├── app.json      # 可执行程序：按 soname 链接库，rpath 加载运行
└── src/          # antelstats.h / stats.c / csv.c / version.c / main.c
```

**antel.json**（版本化共享库）：

```json
{
    "projectName": "antelstats",
    "target_type": "shared",
    "compiler": "gxx",
    "source": ["src/stats.c", "src/csv.c", "src/version.c"],
    "include_directories": ["src"],
    "compile_args": ["-O2", "-Wall", "-fPIC"],
    "report": false,
    "version": "1.0.0"
}
```

构建后输出目录里是：`libantelstats.so.1.0.0`（真实文件）+ `libantelstats.so.1`、`libantelstats.so` 两条软链；`readelf -d` 显示 `SONAME = libantelstats.so.1`。

**app.json**（可执行消费者，按 soname 链接与加载）：

```json
{
    "projectName": "app",
    "target_type": "exe",
    "compiler": "gxx",
    "source": ["src/main.c"],
    "compile_args": ["-O2", "-Wall", "-Isrc"],
    "link_args": ["-L.antel/build/antelstats_antel", "-lantelstats"],
    "report": false,
    "rpath": ["$ORIGIN/../antelstats_antel"]
}
```

要点：`include_directories` 里的 `.c` 会参与构建（这是设计），所以依赖库的工程**只用 `-I` 拿头文件、不要 `include_directories` 指进库源码目录**，否则库会被静态重编一遍。`rpath` 的 `$ORIGIN` 运行期展开为可执行文件目录，因此 `ldd` 显示的是按 SONAME 加载：

```text
libantelstats.so.1 => .../antelstats_antel/libantelstats.so.1
```

构建与运行（两行命令，无外部输入）：

```bash
cd demos/antelstats
antel rebuild                 # 版本化共享库 + 软链
antel rebuild -f app && ./.antel/build/app_app/app          # 内嵌数据直接出统计报表
antel analyze -f app          # 生成可视化报告 .antel/build/app_app/report.html
```

!!! note "sanitize / coverage 怎么用"
    本 demo 没有为它们做独立配置——因为它们就是 `antel.json` 里的一两行开关，测试（`tests/test_sanitize_coverage.py`）已经覆盖。需要时在任意配置里加 `"sanitize": ["address"]`（调试内存问题记得配合 `-O0 -g`，`-O1` 以上 GCC 会把未定义的越界访问优化掉、ASan 检测不到）或 `"coverage": true`（运行后 `gcov` 出报告）即可。

!!! tip "可视化分析报告"
    `antel analyze` 在输出目录生成自包含的 `report.html`——10 个分析维度：产物、增量状态、编译参数统计、资源情况、目标符号表、头文件依赖、大小分布、动态依赖、编译命令、日志清单，浏览器直接打开即可看。以 resdemo 为例的完整效果与逐区块讲解见[报告示例](report.md)，命令用法见[命令参考](commands.md)。
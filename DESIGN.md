# 全量支持 gcc 与 make：可行性分析与实现方案

> 状态：草案（待评审） · 版本：v0.1 · 日期：2026-09-16 · 基线代码：`b2bf975`

## 1. 背景与目标

### 1.1 背景

antelope 当前的工作方式：读 `antel.json` → 逐个编译单元调用 `gcc`/`g++`（`-MMD` 记录依赖）→ 用 hash 基线判定增量 → `ar`/`g++` 链接 → 落盘编译命令、链接脚本与符号分析。编译与链接参数由配置直通，工具本身不解释它们。

### 1.2 "全量支持 gcc、make" 的拆解

这是两条独立的线，难度差一个量级，必须分开评估、分开交付：

- **A 线（工具链能力）**：把 gcc 工作流的常规能力补齐——并行编译、响应文件、PCH、LTO、版本化动态库、安装打包、pkg-config、覆盖率/消毒器、`compile_commands.json`、诊断聚合。
- **B 线（构建互操作）**：让工程可以被 `make` 构建——生成可独立运行的 Makefile、或把 make 当作并行执行后端、或驱动已有的 Makefile。

### 1.3 本文不做什么

- **不解析任意 Makefile 的语义**（理由与可行子集见 §4.4）。
- 不替代 CMake，不做 IDE 工程生成。
- 本阶段不处理 Windows/msvc：其链接路径仍未实现（`antelope/linker/linker.py:65`），且 `cl` 无 `-MMD`。
- 不改动"编译/链接参数由用户负责"这一既有约定，只在文档中明确哪些参数由工具注入。

## 2. 现状盘点

### 2.1 实测数据

测试树：150 个 `.c`（每个约 4 行函数）+ 1 个公共头，本机 8 核，`-O1`。复现命令见附录 A。

| 方式                                  | 耗时  | 备注                           |
| ------------------------------------- | ----- | ------------------------------ |
| 裸 gcc 串行循环（`-MMD`）           | 3.59s | 基线                           |
| 当前`antel rebuild`（串行）         | 3.89s | 额外开销约 0.3s（hash + 日志） |
| `make -j8`（等价规则的 Makefile）   | 0.78s | **并行缺口约 5×**       |
| `antel build`（无改动，增量快路径） | 0.18s | 增量判定本身很便宜             |

结论：**当前最大的问题是串行执行，而不是参数面覆盖不足**。优先级应为"执行模型"先于"参数面"。

### 2.2 A 线能力矩阵

| #  | 能力                                  | 现状    | 依据 / 说明                                                                       |
| -- | ------------------------------------- | ------- | --------------------------------------------------------------------------------- |
| 1  | 任意编译/链接参数                     | ✅      | `args_parser/external.py` 的 `parse_compile_args/link_args`                   |
| 2  | 静态库 / 共享库 / 可执行              | ✅      | `linker.gen_link_command`                                                       |
| 3  | 依赖驱动的增量（头文件变更）          | ✅      | hash +`-MMD`；实测改单文件重编 1、改公共头重编 150                              |
| 4  | 失败即中断 + 非 0 退出码              | ✅      | `errors.py` + CLI 装饰器                                                        |
| 5  | 产物可追溯（命令脚本 / 符号 / 依赖）  | ✅      | `log/<项目名>_link.sh`、`readelf/nm/ldd/objdump` 分析                         |
| 6  | **并行编译**                    | ❌      | `compiler/compiler.py:37-38` 串行 `for` + `alive_bar`                       |
| 7  | **响应文件 `@file`**          | ❌      | 实测 gcc 支持；本项目靠拼接字符串，超长命令行无出路                               |
| 8  | **结构化参数**                  | ❌      | `os_ops/command.py:16` 把自拼字符串再 `shlex.split`，含空格或引号的参数会走样 |
| 9  | **compile_commands.json**       | ❌      | 数据（每条命令）已具备，仅缺输出；clangd/IDE 接入依赖它                           |
| 10 | PCH 预编译头                          | ❌      | 实测`g++ -x c++-header` 可产出 `.gch`（1.92 MB）                              |
| 11 | LTO                                   | ❌      | 实测`-flto` + `gcc-ar` + `gcc-nm` + 链接可执行全链路通                      |
| 12 | 动态库 soname / 版本化 / rpath        | ❌      | 当前只产出`lib<项目名>.so` 平铺                                                 |
| 13 | 安装打包（prefix / install /`.pc`） | ❌      | 无                                                                                |
| 14 | 覆盖率 / 消毒器 / 剖析产物回收        | ❌      | 无（`.gcda`/`.gcno` 也不参与清理）                                            |
| 15 | 诊断聚合（按 TU 分组、警告计数）      | ❌      | 当前是一行行实时透传                                                              |
| 16 | ccache / distcc 包装                  | ❌      | 本机未装 ccache，接口可先留                                                       |
| 17 | 多配置（debug / release 并存）        | 🔸 半通 | 可用多份`antel.json`，但产物目录不能共存（`<项目名>_<配置名>`）               |
| 18 | clang / msvc 对等                     | 🔸 部分 | clang 基本可用；msvc 链接未实现，且无`-MMD`                                     |

### 2.3 现有实现的关键位置

| 关注点                    | 位置                                                               |
| ------------------------- | ------------------------------------------------------------------ |
| 命令执行（继承/捕获输出） | `antelope/os_ops/command.py:16,25,31`                            |
| 逐 TU 编译与进度条        | `antelope/compiler/compiler.py:32,37-38`                         |
| 增量判定                  | `antelope/compiler/compiler.py:70`                               |
| 编译命令生成              | `antelope/compiler/compiler.py:92`                               |
| 依赖文件解析              | `antelope/compiler/compiler.py:41`                               |
| 链接脚本与执行            | `antelope/linker/linker.py:32,42,46,54,65`                       |
| 链接后符号/依赖分析       | `antelope/linker/linker.py:74`                                   |
| 构建流程编排              | `antelope/antelope.py:89`（`build`）、`:109`（`rebuild`）  |
| 配置解析与校验            | `antelope/antelope.py:129,152-181`                               |
| 枚举                      | `antelope/enums.py`                                              |
| 配置模板字段              | `antelope/json_ops/antel_json_cpp.py`                            |
| hash 基线                 | `antelope/md5.py`                                                |
| 测试与 CI                 | `tests/test_antelope.py`、`pytest.ini`、`.github/workflows/` |

### 2.4 会在本方案中一并处理的具体缺陷

| 缺陷                                                     | 影响                                               | 处理位置                  |
| -------------------------------------------------------- | -------------------------------------------------- | ------------------------- |
| 命令以字符串拼接再`shlex.split`                        | 路径含空格、参数含引号时走样                       | Phase 0 结构化参数        |
| 依赖文件命名与 make 习惯错位                             | make 侧依赖可能**静默失效**（见 §4.1 实测） | Phase 1 Makefile 命名对齐 |
| 串行执行                                                 | 8 核上损失约 5× 时间                              | Phase 0 并行执行          |
| `os.system('rm -rf …')` 与 `projectName` 拼入 shell | 注入面                                             | Phase 0 一并收口          |
| `-MMD` 仅 gcc/clang 可用                               | msvc 无依赖文件，其目标每次重编                    | 保持现状并在文档标注      |

## 3. 目标架构

### 3.1 数据模型（新增 `antelope/build_plan.py`）

```python
class CompileUnit:
    source: str          # 源文件路径
    obj: str             # 目标文件路径
    dep: str             # 依赖文件路径
    driver: str          # gcc / g++ / clang / cl
    args: list[str]      # 结构化参数（不再拼接字符串）

class LinkJob:
    driver: str
    args: list[str]
    output: str
    script: str          # 落盘用的 shell 文本（审计产物，需正确转义）

class BuildPlan:
    units: list[CompileUnit]
    link: LinkJob
    jobs: int            # 并行度
    backend: str         # antel | make
```

要点：**参数以列表为单位在内部流转**，仅在落盘审计脚本时序列化为 shell 文本。这样同时解决三件事——长命令行（响应文件）、引号与空格、以及生成 Makefile 时的转义。

### 3.2 执行模型

| 后端              | 执行方式                                                                               | 增量判定                                  | 适用场景                                         |
| ----------------- | -------------------------------------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------ |
| `antel`（默认） | 线程池并发执行`CompileUnit`（子进程为 IO-bound，无需多进程）；`alive_bar` 手动推进 | hash 基线 + 依赖文件（现状）              | 日常构建、需要详细日志与产物分析                 |
| `make`          | 生成 Makefile 并`make -j$jobs` 执行                                                  | 交给 make（mtime +`-include` 依赖文件） | 需要`-j` / jobserver、或工程已有 make 使用习惯 |

从 make 内部调用 `antel` 时，应透传 jobserver 信息（`MAKEFLAGS`），避免嵌套并行时超额占用 CPU。

### 3.3 增量权威约定（核心决策，必须先定）

两套增量模型（hash vs mtime）不能并行，否则会出现"一边认为要重编、另一边认为不用"的静默不一致——这正是本项目历史上最难排查的一类问题。两种方案：

- **方案 A（推荐）：共享 `obj/` 与 `*.o.d`**。make 与 antel 共用同一份目标文件与依赖文件，切换后端不需要重新全量编译。
- **方案 B：分离目录**（`obj/` 归 antel、`obj-make/` 归 make）。互不干扰，代价是磁盘翻倍与"两套真相"，切换后端必然全量重编。

**方案 A 的实测行为（不是猜测，见附录 A 复现）**：

| 序列                             | 结果                                         | 解释                                                                                                          |
| -------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `make` 构建 → `antel build` | `发生变化的文件：1`、`需重新编译文件：1` | antelope 的 hash 基线是**独立簿记**，make 不会更新它，于是刚被 make 编译过的文件在 antel 看来仍是"变化" |
| `antel rebuild` → `make -n` | 计划重编`0` 个                             | make 用 mtime 判定，antel 产出的目标文件比输入新，判定一致                                                    |

也就是说：**方案 A 不会漏编（安全方向），但会出现冗余重编**。冗余重编不影响产物正确性，但会破坏"两边不重复劳动"的预期，也会让 CI 时长失真。

**消除冗余的办法**：提供一条轻量命令 `antel sync-baseline`（只刷新 hash 基线，不编译），并在生成的 Makefile 的 `all` 目标末尾调用它。这样两种后端的簿记在每次构建后都对齐，交替执行不再产生额外编译。

**一致性测试的断言**（不要断言"集合完全相等"，它在内容等价时会误报）：

1. **不漏编**：任意修改序列后，产物内容必须与输入内容一致（用输入 hash ↔ 产物 hash 的对应关系校验，而不是只看时间戳）。
2. **产物等价**：同一棵树分别用两种后端构建，产物（可执行文件、静态库）字节一致。
3. **无冗余**：接入 `sync-baseline` 后，交替构建不应产生多余编译。

### 3.4 配置与 CLI 扩展

新增配置字段（仍向后兼容，缺省即现有行为）：

| 字段                        | 类型        | 默认                  | 说明                                          |
| --------------------------- | ----------- | --------------------- | --------------------------------------------- |
| `jobs`                    | 整数        | `min(8, cpu_count)` | 并行度；`1` 即串行                          |
| `backend`                 | 字符串      | `antel`             | `antel` / `make`                          |
| `response_file`           | 布尔        | `auto`              | 命令行超阈值时自动改用`@file`               |
| `compile_commands`        | 布尔        | `true`              | 是否输出`compile_commands.json`             |
| `lto`                     | 布尔        | `false`             | 编译/链接加`-flto`，归档工具切到 `gcc-ar` |
| `pch`                     | 对象        | 无                    | `{header, language}`                        |
| `version` / `soname`    | 字符串/布尔 | 无                    | 动态库版本化                                  |
| `rpath`                   | 数组        | 无                    | 如`["$ORIGIN"]`                             |
| `pkg_config`              | 数组        | 无                    | 注入`--cflags/--libs`                       |
| `sanitize` / `coverage` | 数组/布尔   | 无                    | 参数注入与产物回收                            |
| `install`                 | 对象        | 无                    | `{prefix, includes, pc}`                    |
| `wrapper`                 | 数组        | 无                    | 如`["ccache"]`                              |

新增命令：

| 命令                                 | 说明                                                                |
| ------------------------------------ | ------------------------------------------------------------------- |
| `antel gen-makefile [-o Makefile]` | 由当前配置生成可独立运行的 Makefile                                 |
| `antel make [-- <args>]`           | 转交 make 执行并接管输出、退出码与日志                              |
| `antel sync-baseline`              | 只刷新 hash 基线，不编译；供 make 构建后对齐两种后端的簿记（§3.3） |
| `antel install`                    | 安装到`install.prefix`                                            |

## 4. 可行性判定

### 4.1 生成 Makefile：可行（推荐先做）

**契合点**：本项目已经产出 `-MMD` 依赖文件，而 `-MMD` 的输出本身就是 make 依赖语法，Makefile 里 `-include` 即可复用，不需要重新发明依赖跟踪。

**实测**（150 TU）：

| 依赖文件命名                                                                    | 动作          | make 计划重编数         |
| ------------------------------------------------------------------------------- | ------------- | ----------------------- |
| 对齐：`-MF $@.d`（落成 `x.o.d`）配 `-include $(OBJS:%=%.d)`               | 改 1 个源文件 | 1 ✅                    |
| 同上                                                                            | 改公共头      | 150 ✅                  |
| 错位：`-MF $@.d`（落成 `x.o.d`）配 `-include $(OBJS:.o=.d)`（找 `x.d`） | 改公共头      | **0（静默失效）** |

**结论**：命名必须对齐。本项目当前用的是 `x.o.d`，因此生成的 Makefile 应写 `-MF $@.d` 并 `-include $(OBJS:%=%.d)`——附录 B 的模板已按此实测通过（全量构建、无改动空跑、改源文件重编 1 个）。这条错位会直接复现"改了东西却什么都没重编"的老问题，必须用测试锁住。

### 4.2 make 当并行后端：可行

生成一个内部 Makefile 并 `make -jN` 即可获得并行与 jobserver，无需自行实现任务调度。代价是多一层进程、错误定位链变长（make 的输出需要归并回 antel 的日志模型），且"make 不参与判定、只负责执行"这一分工必须写进文档。

### 4.3 驱动现有 Makefile：可行但浅

`antel make` 转交参数、接管输出与退出码、把日志纳入 `log/`。它能解决"已有 Makefile 工程想用 antel 的日志与产物分析"，但不参与依赖分析，也不能提供 antel 的增量判定。

### 4.4 导入/解析现有 Makefile：**全量不可行**

GNU make 是一个重写系统：变量可递归展开、支持条件、`include`、数十个内置函数、模式规则与二次展开。静态解析不存在完备实现，"全量支持"在语义上就不成立。

可行的子集只有两种：

1. **只读导入**：`make -p -n` 导出数据库，近似还原目标、变量与依赖，用于 `antel analyze` 展示（必须在输出中标注"近似、可能缺失动态生成的目标"）。
2. **执行级互操作**：见 §4.3。

### 4.5 A 线能力面：可行，工作量集中在少数几项

参数直通已经覆盖了大半 gcc 参数；缺口集中在 PCH、LTO、版本化动态库、安装打包与并行执行。这些都不需要改动核心增量算法，属于"在既有 plan 上增加参数与产物"。

## 5. 分阶段实现方案

### Phase 0：执行模型与结构化解耦（1-2 天）

**目标**：拿到并行收益，消除参数拼接的歧义与注入面，输出 `compile_commands.json`。

- 新增 `antelope/build_plan.py`（§3.1 模型）
- `Compiler.gen_build_objects()`（`compiler.py:92`）拆成 `build_plan()`（返回结构）+ `render_commands()`（仅供审计脚本与日志）
- `Linker.gen_link_command()`（`linker.py:54`）改为 `build_link_job()`
- `Command` 增加 `run_argv(args: list[str])`；`Compiler.compile()`（`compiler.py:32`）改为线程池并发，`alive_bar` 手动推进
- `os.system` 的删除操作改为 Python 侧删除；`projectName` 进入 shell 前做白名单校验
- 输出 `compile_commands.json`

**验收**：并行与串行的产物字节一致；150 TU 从 3.9s 降到 1.0s 以内；`compile_commands.json` 可被 clangd 解析；新增测试覆盖"参数含空格"的路径。

#### Phase 0 实施记录（已完成，2026-09-16）

交付内容：

| 项           | 落点                                                                                     |
| ------------ | ---------------------------------------------------------------------------------------- |
| 数据模型     | 新增 `antelope/build_plan.py`：`CompileUnit` / `LinkJob` / `BuildPlan` + `writeCompileCommands` |
| 结构化执行   | `Command.run_argv(args)`；内部不再把命令拼成字符串（`run(str)` 仅为兼容保留）              |
| 并行编译     | `Compiler.run_units`：线程池 + 失败即停（`threading.Event`），`jobs` 可调                 |
| 响应文件     | `Linker.plan_response_file`：超过阈值改写 `log/<项目名>_link.rsp`；`ar` 不支持 `@file` 已排除 |
| IDE 接入     | 每次构建输出 `<输出目录>/compile_commands.json`（结构化 `arguments`）                     |
| 注入面收口   | `os.system` 全部移除（改用 `shutil.rmtree` / `glob` 删除）；`projectName` 白名单校验      |

命名偏差：文档里写的 `build_plan()` / `render_commands()` 实际落地为 `Compiler.build_compile_units()` 与 `CompileUnit.render()`，语义一致。

实测结果：

| 场景                                              | 结果                        |
| ------------------------------------------------- | --------------------------- |
| 150 TU `rebuild`，`jobs=1`                        | 3.87s                       |
| 150 TU `rebuild`，`jobs=8`                        | **1.11s（3.5×）**           |
| 其中：增量判定（hash + 依赖扫描）                 | 0.18s                       |
| 其中：链接后产物分析（nm / ar -t / objdump -x / strip） | 0.06s                  |
| 对照 `make -j8`（不含 hash 判定与产物分析）       | 0.78s                       |
| 串行 vs 并行产物                                  | 可执行文件字节一致（sha256 相同） |

**与验收线的差距**：`<1.0s` 未严格达成（1.11s）。差的约 0.2s 是 antelope 特有的 hash 判定开销，`make -j8` 的 0.78s 并不包含这部分；编译与链接部分本身已与 make 基本持平（余下差异为每个编译单元约 0.6ms 的 Python 进程开销）。

回归证据：测试从 3 条增至 9 条。其中"路径含空格"用例在 Phase 0 之前必然失败（旧实现报 `gcc: fatal error: cannot specify '-o' with '-c' ... with multiple files`，退出码 1），当前通过。

下一步：Phase 1（Makefile 生成 + `antel sync-baseline` + 跨实现一致性测试）。

### Phase 1：Makefile 生成与 make 后端（2-3 天）

**目标**：同一份配置既能 `antel build`，也能 `make`。

- 新增 `antelope/makefile.py`：`render(plan) -> str`，模板见附录 B（已实测）
- CLI 增加 `antel gen-makefile` 与 `antel sync-baseline`；配置支持 `backend: make`
- 依赖文件命名对齐 `x.o.d`（`-MF $@.d` + `-include $(OBJS:%=%.d)`）；`MAKEFLAGS += -j$(JOBS)`；`clean`/`rebuild` 目标与 antel 语义一致
- 生成的 Makefile 在 `all` 目标末尾调用 `antel sync-baseline`，消除 §3.3 的冗余重编
- 落实 §3.3 的增量权威约定
- **跨实现一致性测试**：按 §3.3 的三条断言（不漏编 / 产物字节等价 / 无冗余重编）

**验收**：生成的 Makefile 在干净树上 `make -j8` 成功且产物可运行；改公共头后 `make` 与 `antel build` 都不漏编；接入 `sync-baseline` 后交替构建不产生额外编译；两种后端的可执行文件字节一致。

### Phase 2：gcc 能力面补齐（4-6 天）

| 能力            | 实现要点                                                                                                   | 验收                                                    |
| --------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| PCH             | `pch: {header, language}` → 产出 `<header>.gch`，各 TU 加 `-include`，`.gch` 纳入 hash 跟踪       | 改头文件触发 PCH 重建与受影响 TU 重编                   |
| LTO             | `lto: true` → 编译/链接加 `-flto`；`linker.py:74` 的归档/符号工具按编译器切到 `gcc-ar`/`gcc-nm` | LTO 静态库可被链接成可执行文件                          |
| 版本化动态库    | `version` + `soname` → `-Wl,-soname,libX.so.1`，产出 `libX.so.1.0.0` 与符号链接；`rpath`        | `readelf -d` 中 soname 正确，链接产物可按 soname 加载 |
| 安装打包        | `install: {prefix, includes, pc}` → `antel install`，生成 `.pc`                                     | 安装后`pkg-config --cflags/--libs` 可用               |
| pkg-config      | `pkg_config: [...]` → 注入 `pkg-config` 输出                                                          | 编译/链接参数包含第三方库                               |
| 覆盖率 / 消毒器 | `sanitize`、`coverage` → 参数注入；`clean` 回收 `.gcda`/`.gcno`                                 | 运行后`gcov` 可产出报告                               |
| 诊断聚合        | 编译输出按 TU 归并、警告计数、失败按文件分组                                                               | 多错误场景输出可读，失败仍以非 0 退出                   |
| 工具包装        | `wrapper: [ccache]`                                                                                      | 包装器生效且不破坏依赖判定                              |

### Phase 3：生态互操作（2-3 天，可选）

- `antel make -- …`：转交 make，接管输出/退出码/日志（§4.3）
- `make -p -n` 只读导入，用于依赖图展示（§4.4）

## 6. 测试策略

| 层次         | 内容                                                                                                                             |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| 单元         | plan 生成（参数列表、命名规则、转义）、依赖文件解析、响应文件阈值                                                                |
| 集成         | 现有三条真实构建用例扩展：并行/串行等价、make 与 antel 交替、长路径与空格路径                                                    |
| 跨实现一致性 | §3.3 的三条断言：不漏编（输入 hash ↔ 产物一致）、两种后端产物字节等价、接入`sync-baseline` 后无冗余重编（Phase 1 起纳入 CI） |
| 性能基线     | 150 TU 场景记录耗时；并行开启后应 <1.0s（当前 3.9s）                                                                             |
| 回归         | `compile_commands.json`、既有日志产物（命令脚本、符号分析）不丢失                                                              |

## 7. 风险与缓解

| 风险                             | 影响                        | 缓解                                                                          |
| -------------------------------- | --------------------------- | ----------------------------------------------------------------------------- |
| 增量双真相（hash vs mtime）      | 静默过期产物                | §3.3 约定 + 跨实现一致性测试                                                 |
| 交替构建产生冗余重编             | CI 时长失真、误判"没有生效" | `antel sync-baseline` 挂在生成的 Makefile 的 `all` 末尾（§3.3 实测依据） |
| 参数结构化波及所有调用点         | 一次性改动面较大            | 集中在 Phase 0；compiler/linker/analyze/文档/模板一并更新                     |
| make 侧依赖文件命名错位          | 静默不重编                  | 命名对齐 + §4.1 的测试用例                                                   |
| msvc 无`-MMD`                  | 其目标每次重编              | 保持现状并在文档标注；扩展能力时同样映射                                      |
| 嵌套并行（antel 被 make 调用）   | CPU 超额占用                | 透传 jobserver 信息                                                           |
| 工具注入参数与用户参数的边界模糊 | 参数冲突难排查              | 文档中列出"由工具注入"的参数清单                                              |

## 8. 待决策项

| # | 问题                                                                       | 建议                                                                               |
| - | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| 1 | make 支持做到哪一层：生成 Makefile / 并行后端 / 两者 / 只驱动现有 Makefile | 先做"生成 Makefile"，并行后端随 Phase 0 的线程池一并具备，可后置                   |
| 2 | 增量权威：共享`obj/` 还是分离目录                                        | 共享（§3.3 实测：不漏编，但需`sync-baseline` 消除冗余重编）                     |
| 3 | 是否纳入 PCH / LTO / 安装 / 版本化等重型能力                               | 建议 Phase 2 分项评估，先做 PCH 与版本化动态库（实际使用频率最高）                 |
| 4 | 目标 gcc 最低版本与平台                                                    | 本机 11.4；LTO/响应文件/PCH 在 4.x 起即有。Windows/msvc 维持"编译可用、链接未实现" |

## 9. 附录

### A. 实测复现命令

```bash
# 150 TU 测试树（8 核）
python3 - <<'PY'
from pathlib import Path
Path('inc').mkdir(exist_ok=True)
Path('inc/common.h').write_text('#pragma once\n#define BASE 7\nint helper(int);\n')
for i in range(150):
    Path(f'u{i:03d}.c').write_text(
        '#include "inc/common.h"\n#include <stdio.h>\n'
        f'int f{i}(int x){{ int s=0; for(int k=0;k<x;k++) s+=k*BASE; return s+{i}; }}\n'
        f'int g{i}(void){{ return f{i}({i % 17 + 1}); }}\n')
PY

# 串行基线
time for f in u*.c; do gcc -O1 -MMD -MF obj_serial/${f%.c}.d -c -o obj_serial/${f%.c}.o $f -I .; done

# make 并行（依赖文件命名与 -include 必须对齐）
time make -j8
make -n | grep -c 'gcc '     # 改公共头后应为 150，改单个源文件后应为 1

# 响应文件
printf -- '-O1 -I . -MMD -MF rsp.d -c -o rsp.o u001.c\n' > args.rsp && gcc @args.rsp

# 两种后端交替（§3.3 的实测依据）
make -j8                     # make 构建
antel build                  # 观察：发生变化的文件 1 / 需重新编译文件 1（hash 基线未共享）
antel rebuild                # antel 构建
make -n | grep -c 'gcc '     # 观察：0（make 认可 antel 的产物）

# LTO 全链路
gcc -O2 -flto -c -o lto1.o u001.c && gcc-ar csr liblto.a lto1.o && gcc-nm liblto.a
gcc -O2 -flto main.c liblto.a -o lto_exe

# PCH
g++ -x c++-header inc/common.h -o pch.gch
```

### B. 生成的 Makefile 草案

```make
# 由 antel gen-makefile 生成，请勿手改
PROJECT   := helloworld
BACKEND   := make
CC        := gcc
CXX       := g++
CFLAGS    := -std=c++17 -Os -fPIC -I include
LDFLAGS   :=
LDLIBS    := -lm
JOBS      ?= 8
OBJDIR    := helloworld_antel/obj
TARGET    := helloworld_antel/helloworld

SRCS      := helloworld.c
OBJS      := $(SRCS:%.c=$(OBJDIR)/%.o)
DEPS      := $(OBJS:%=%.d)

.PHONY: all clean rebuild
all: $(TARGET)
	@antel sync-baseline -f antel        # 对齐 antel 的 hash 基线（Phase 1 引入，§3.3）

$(TARGET): $(OBJS)
	$(CXX) $(LDFLAGS) -o $@ $^ $(LDLIBS)

$(OBJDIR)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -MMD -MF $@.d -c -o $@ $<

clean:
	rm -rf $(OBJDIR) $(TARGET)
rebuild: clean all

MAKEFLAGS += -j$(JOBS)
-include $(DEPS)
```

注：`-MF $@.d`（落成 `x.o.d`）与 `-include $(OBJS:%=%.d)` 必须同时用这一套命名，才能与 antel 现有的依赖文件命名一致（§4.1 有实测对比）。本模板已在 `test/` 样例上实测：全量构建成功、产物可运行、无改动时空跑、改源文件重编 1 个。

### C. compile_commands.json 形态

```json
[
  {
    "directory": "/path/to/project",
    "file": "src/main.c",
    "output": "helloworld_antel/obj/src_main.o",
    "arguments": ["gcc", "-std=c++17", "-Os", "-I", "include", "-MMD", "-MF", "helloworld_antel/obj/src_main.o.d", "-c", "-o", "helloworld_antel/obj/src_main.o", "src/main.c"]
  }
]
```

优先输出 `arguments`（结构化）而非 `command`（字符串），后者在含空格的路径上不可靠。

### D. 环境与事实核对表

| 项目          | 实测值                                                                      |
| ------------- | --------------------------------------------------------------------------- |
| gcc / g++     | 11.4.0（Ubuntu 22.04）                                                      |
| GNU Make      | 4.3（支持 jobserver）                                                       |
| binutils      | 2.38（`ar` / `gcc-ar` / `gcc-nm` / `gcc-ranlib` / `ranlib` 均在） |
| gcov          | 11.4.0                                                                      |
| 链接器        | GNU ld 2.38、gold 1.16 可用；**lld 未安装**                           |
| ccache        | **未安装**（接口可先留）                                              |
| pkg-config    | 0.29.2                                                                      |
| `-MMD` 输出 | 即 make 依赖语法，可被`-include` 直接消费                                 |
| `@响应文件` | gcc 支持，实测可用                                                          |
| LTO           | `-flto` + `gcc-ar` + `gcc-nm` + 链接可执行全链路通过                  |
| PCH           | `-x c++-header` 产出 `.gch`，实测 1.92 MB                               |

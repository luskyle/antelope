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
| 6  | **并行编译**                    | ✅      | `Compiler.run_units` 线程池 + `jobs`；150 TU：3.87s → 1.11s（Phase 0）        |
| 7  | **响应文件 `@file`**          | ✅      | `Linker.plan_response_file` 超阈值改写；`ar` 不支持 `@file` 已排除（Phase 0） |
| 8  | **结构化参数**                  | ✅      | `Command.run_argv`；含空格路径实测通过（旧实现报 `-o` 与 `-c` 冲突）（Phase 0） |
| 9  | **compile_commands.json**       | ✅      | 每次构建输出 `<输出目录>/compile_commands.json`，结构化 `arguments`（Phase 0） |
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

**分工固定为：antel 决定"编什么"，make 负责"怎么并行编完"。**

| 后端            | 执行方式                                                                          | 增量判定                      | 适用场景                            |
| --------------- | --------------------------------------------------------------------------------- | ----------------------------- | ----------------------------------- |
| `make`（默认）  | antel 生成内部规则文件，按"本轮过期目标"显式调用 `make -f <规则> -j$jobs <目标>` | hash 基线 + 依赖文件（antel） | 默认路径；拿 make 的并行与 jobserver |
| `antel`（回退） | 线程池并发执行 `CompileUnit`（子进程为 IO-bound）；`alive_bar` 手动推进           | 同上                          | 机器上没有 make 时自动回退          |

三条实现约定（均已实测，依据见 §4.2）：

1. 内部规则文件由 antel 每次构建重新生成，位置是 `<输出目录>/log/antel.mk`，头部带"生成物勿改"标记。**它不是交付物**，项目根不会出现 Makefile。放 `log/` 而不是输出目录根，是为了与本项目既有惯例同构——真正被执行的东西一律落盘留档，`log/<项目名>_link.sh` 就是链接时执行的脚本本体。
2. 把过期目标交给 make 之前**先删掉这些目标文件**：make 按 mtime 判定，实测"把已是最新的目标交给 make"会被跳过（输出 `已是最新`）；而按 hash 判定它们确实过期，删掉才能确保重建，也避免"头文件时间戳早于目标文件"导致的漏编。
3. make 的失败退出码（实测失败为 2）由 antel 转成自己的非 0 退出并保留输出到 `log/`；从 make 内部调用 antel 时透传 jobserver 信息。

### 3.3 增量权威归属

结论：**增量判定只归 antel，make 不参与判定**。make 只收到显式目标，且这些目标在调用前已被删除，因此不存在"一方认为要重编、另一方认为不用"的分歧——这正是选择"显式目标 + 先删目标"而不是"整包交给 make"的原因。

以下实测事实说明为什么不能让 make 参与判定：

| 序列                                | 结果                                     | 解释                                                    |
| ----------------------------------- | ---------------------------------------- | ------------------------------------------------------- |
| 把已是最新的目标交给 make            | make 输出"已是最新"并跳过                 | make 按 mtime 判定，与 hash 判定不等价                   |
| `make`（整包）构建 → `antel build` | `发生变化的文件：1`、`需重新编译文件：1` | antel 的 hash 基线是独立簿记，make 不会更新它 → 冗余重编 |
| `antel rebuild` → `make -n`        | 计划重编 `0` 个                          | antel 产出的目标文件比输入新，此时两者一致               |

`antel sync-baseline` 因此降级为**边角工具**：只在有人手工跑过内部规则文件（绕过 antel 的簿记）之后，用它把 hash 基线对齐。

**一致性测试的断言**（不要断言"集合完全相等"，它在内容等价时会误报）：

1. **不漏编**：任意修改序列后，产物内容必须与输入内容一致（用输入 hash ↔ 产物 hash 的对应关系校验，而不是只看时间戳）。
2. **产物等价**：同一轮判定下，两种后端的产物（可执行文件、静态库）字节一致。
3. **不被 make 跳过**：交给 make 的过期目标必须真的重编（对应 §3.2 的约定 2）。

### 3.4 配置与 CLI 扩展

新增配置字段（仍向后兼容，缺省即现有行为）：

| 字段                        | 类型        | 默认                  | 说明                                          |
| --------------------------- | ----------- | --------------------- | --------------------------------------------- |
| `jobs`                    | 整数        | `min(8, cpu_count)` | 并行度；`1` 即串行                          |
| `backend`                 | 字符串      | `auto`              | `auto`（默认：优先用 make，缺失时回退到内置执行器并提示）/ `make` / `antel` |
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

| 命令                      | 说明                                                                     |
| ------------------------- | ------------------------------------------------------------------------ |
| `antel sync-baseline`     | 只刷新 hash 基线，不编译；手工跑过内部规则文件之后用它对齐簿记（§3.3） |
| `antel install`           | 安装到 `install.prefix`（Phase 2）                                      |
| `antel make [-- <args>]`  | 转交既有 Makefile 执行并接管输出、退出码与日志（Phase 3）               |

## 4. 可行性判定

### 4.1 复用 `-MMD` 依赖文件（与 make 的契合点）

**契合点**：本项目已经产出 `-MMD` 依赖文件，而 `-MMD` 的输出本身就是 make 依赖语法，规则文件里 `-include` 即可复用，不需要重新发明依赖跟踪。

**实测**（150 TU）：

| 依赖文件命名                                                                    | 动作          | make 计划重编数         |
| ------------------------------------------------------------------------------- | ------------- | ----------------------- |
| 对齐：`-MF $@.d`（落成 `x.o.d`）配 `-include $(OBJS:%=%.d)`               | 改 1 个源文件 | 1 ✅                    |
| 同上                                                                            | 改公共头      | 150 ✅                  |
| 错位：`-MF $@.d`（落成 `x.o.d`）配 `-include $(OBJS:.o=.d)`（找 `x.d`） | 改公共头      | **0（静默失效）** |

**结论**：命名必须对齐。本项目当前用的是 `x.o.d`，因此内部规则文件应写 `-MF $@.d` 并 `-include $(OBJS:%=%.d)`——附录 B 的规则文件草案已按此实测通过（全量构建、无改动空跑、改源文件重编 1 个）。这条错位会直接复现"改了东西却什么都没重编"的老问题，必须用测试锁住。需要说明的是：默认路径（antel 显式目标 + 先删目标）下正确性不依赖 make 的依赖检查，命名对齐主要保障"有人手工跑规则文件"的场景。

### 4.2 用 make 执行编译（默认路径）：可行，机制已验证

make 必须有规则来源，因此"直接调用 make"落地为：antel 生成**内部规则文件**（输出目录内、每次重建、标为生成物）并以**显式目标**调用它。实测（命令见附录 A）：

| 调用形态                              | 结果                                        |
| ------------------------------------- | ------------------------------------------- |
| `make -f -`（从 stdin 读规则）        | 可用，但**不采用**：实测 make 会把 stdin 落成临时文件，报错只给 `/tmp/随机名:行号`，事后也无法复现同一次调用；落 `log/antel.mk` 则报错带可读行号且可手工重跑 |
| 内部规则文件 + 显式目标 + `-j4`       | 只编点名的目标 ✓                            |
| 把已是最新的目标交给 make             | 输出"已是最新"并跳过 → **因此必须先删目标** |
| make 失败退出码                       | 2（"非 0 即失败"成立）                      |

性能上这也是更优选择：同一棵 150 TU 的树，`make -j8` 为 0.78s，Phase 0 的内置线程池为 1.11s（make 的每单元开销更低）。

代价与约束：

- 多一层进程，错误信息需要转译（make 的输出归并进 `log/`）
- 规则必须按**显式目标**逐单元生成：antelope 的目标文件名是扁平化的（`src/main.c` → `obj/src_main.o`），无法用模式规则表达这种对应关系
- 机器上没有 make 时回退到内置线程池，并在输出中提示

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

下一步：Phase 1（make 作为执行后端：内部规则文件 + `backend` 回退 + 跨实现一致性测试）。

### Phase 1：make 作为执行后端（2-3 天）

**目标**：默认用 make 执行编译，同时保持 antel 的增量判定精度。

- 新增 `antelope/makefile.py`：把 `BuildPlan` 渲染成**内部规则文件**（逐单元显式规则 + 链接目标 + `-include` 依赖文件 + "生成物勿改"标记），写入 `<输出目录>/log/antel.mk`，每次构建重建
- 新增 make 执行器：`make -f <输出目录>/log/antel.mk -j$jobs <本轮过期目标>`，**执行前先删除这些目标文件**（§3.2 约定 2）
- 配置字段 `backend`：`auto`（默认，优先 make，缺失时回退内置线程池并提示）/ `make` / `antel`
- 从 make 内部调用 antel 时透传 jobserver（`MAKEFLAGS`）
- `antel sync-baseline`：保留为边角工具（手工跑过内部规则文件后对齐 hash 基线）
- **跨实现一致性测试**：按 §3.3 的三条断言（不漏编 / 两种后端产物字节等价 / 不被 make 跳过）

**验收**：150 TU 在默认配置下走 make 且总耗时不高于内置线程池后端；改公共头后两种后端的重编集合一致；无 make 的环境自动回退，产物与走 make 时字节一致。

#### P1-2 实施记录（已完成，2026-09-17）

交付内容：

| 项 | 落点 |
| --- | --- |
| 规则文件渲染 | 新增 `antelope/makefile.py`：`ruleFilePath`（`<输出目录>/log/antel.mk`）、`escapePath`、`escapeRecipe`、`renderRuleText` |
| make 执行器 | `MakeRunner`：写规则文件 → 删掉本轮过期目标 → `make -f <规则> -j<jobs> <过期目标>`，输出记入 `log/<项目名>.make` |
| 两条路径的公共部分 | `Compiler.log_compile_units`（审计日志）抽出，内置执行器与 make 执行器共用 |
| 配置与编排 | 配置字段 `backend`（`antel` 默认 / `make`）；`Antelope.compileSources` 选择执行器，`Antelope.buildMakePlan` 组装 `BuildPlan` |

实现约定与依据：

- 逐单元显式规则（目标名扁平化，模式规则表达不了 `src/main.c → obj/src_main.o`）
- 调用前先删过期目标；规则文件带 `.DELETE_ON_ERROR:`，避免失败时留下半成品被当成"已构建"
- `$` 在 recipe 里翻倍：实测 `-Wl,-rpath,$ORIGIN` 不翻倍会被 make 吃成 `RIGIN`
- 目标名与依赖名转义空格、制表符、`#`、`$`

实测结果：

| 场景 | 结果 |
| --- | --- |
| 新增测试 | 5 条（规则文件内容与生成标记、改头文件后重编、**mtime 陷阱**、含空格路径、make 失败退出码），总数 14 条全绿 |
| mtime 陷阱 | 把 `.o` 的时间戳改成比头文件新之后，`build` 仍重编并把产物更新到新值（依赖"先删目标"，不依赖 mtime 判定） |
| 含空格路径 | 可用：规则里转义、gcc 的 `.d` 自身也转义空格、make 能解析（此前预期需要加限制，实测推翻） |
| 失败路径 | make 退出码 2 → antel 退出码 1，错误信息指出规则文件路径 |
| 150 TU 端到端，`jobs=8` | 内置执行器 1.10–1.33s，make 1.16–1.25s → **基本持平** |

**预期修正**：此前把 `make -j8` 跑现成 Makefile 的 0.78s 与 antel 端到端 1.11s 相比，口径不同（前者不含 hash 判定、日志与产物分析）。端到端实测两者持平，因此**用 make 的收益不在速度**，而在与 make 工具链的一致性（jobserver、可手工 `make -f log/antel.mk` 复现同一次编译）。

**本批未做（留待 P1-3）**：`backend` 的 `auto` 默认值、make 缺失时的自动回退与提示、从 make 内部调用 antel 时的 jobserver 透传。

#### P1-3 实施记录（已完成，2026-09-17）

交付内容：

| 项 | 落点 |
| --- | --- |
| `auto` 默认与回退 | `backend` 默认改为 `auto`；`Antelope.resolveBackend` 缺 make 时回退内置执行器并提示 |
| 摘要可读性 | `describeBackend`：摘要里直接标出实际执行器（`auto → make` / `auto → antel（未找到 make）`） |
| 被 make 调用 | `MakeRunner.buildArgv` 在有 `MAKEFLAGS` 时**不传 `-j`**；内置执行器由 `Antelope.executorJobs` 退回 `jobs=1` |

实测结果：

| 场景 | 结果 |
| --- | --- |
| 缺 make（PATH 里没有 make，其余工具齐全） | 回退成功，摘要显示 `auto → antel（未找到 make）`，产物与走 make 时**字节一致** |
| 三种取值 `auto` / `make` / `antel` | 均按预期选择执行器；`antel` 时不生成规则文件 |
| `MAKEFLAGS` 存在时 | 内置执行器返回 `jobs=1`（单测断言）；make 执行器的 argv 不含 `-j`（单测断言） |
| 测试总数 | 14 → **18** 条 |

**已知限制（本批不做，留待专门批次）**：make 的 jobserver 管道不会穿透 antel 传给子 make —— Python 启动子进程时默认关闭继承的 fd，因此嵌套 make 会打印 `jobserver 不可用: 正使用 -j1` 并串行执行（实测：父规则带 `+` 也一样）。这是**安全方向**的降级（绝不超额并行），代价是该层失去并行。后续做法：把 `--jobserver-auth=3,4` 里的 fd 透传给子进程（需先 dup 并用 FIFO 校验以防误传，否则子 make 可能阻塞在错误的管道上），或依赖 make ≥ 4.4 的 fifo 风格（无需 fd）。本机 make 为 4.3（pipe 风格），fifo 路径无法在本机验证，故本批不动。

#### M1 收尾（P1-1 与 P1-4，2026-09-17）

- **P1-1 `antel sync-baseline`**：CLI 命令（click 会把函数名 `sync_baseline` 规范成 `sync-baseline`），复用 `Antelope.save_baseline()`。
- **P1-4 跨实现一致性测试**：新增 `tests/test_make_backend.py`，把 §3.3 的三条断言固化为常驻测试；测试脚手架抽到 `tests/conftest.py` 供两个测试模块共用。
- 实测：22 条测试全绿。三条断言逐一验证：改源文件/改两种头文件后产物始终跟上输入（不漏编）；同一棵树两种后端产物字节一致；目标文件时间戳比头文件新时仍必须重编；`sync-baseline` 后 `build` 不再重编（对照组未 sync 时确实会重编，同时验证了该命令的作用）。
- 至此 **M1 收口**：`backend: auto` 走 make、缺 make 回退、`antel sync-baseline`、跨实现一致性测试全部就位。

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

#### P2-2 实施记录（已完成，2026-09-17）

交付内容：

- 配置字段 `pkg_config: [...]`：构建时对每个包运行 `pkg-config --cflags/--libs`，输出用 `shlex.split` 解析成结构化参数后注入——`--cflags` 追加进每个编译单元（排在用户 `compile_args` 之后，用户 `-I` 优先级更高），`--libs` 追加到链接命令末尾（`ar` 归档天然跳过）
- `Compiler` / `Linker` 各新增 `pkg_cflags` / `pkg_libs` 参数；`Command.run_argv` 增加 `capture=True` 模式（只取输出、不打印不落盘）
- 解析只在 `flushSetting` 做一次：包不存在（`pkg-config` 退出码 1）或命令缺失时直接 `ConfigError` 报错

实测：

- 新增 3 条测试（端到端假外部库、包不存在、命令缺失），总数 22 → **25** 条全绿。端到端用例真实编译出 `libfoo.a`，证明"没有 `pkg_config` 就编不过、加上后编译与链接都注入正确参数"
- 用真实包 fontconfig 手工验证：`-I/usr/include/uuid -I/usr/include/freetype2 -I/usr/include/libpng16` 进入编译命令、`-lfontconfig` 进入链接脚本，构建退出码 0

实现过程中发现并修复的坑：pkg-config 的输出一开始用 `Command.run_argv` 的默认（透传）模式拿不回来——该模式输出直接进终端、返回空串，导致 `-I` 静默丢失。给 `run_argv` 增加 `capture` 参数后解决。

### Phase 3：生态互操作（2-3 天，可选）

- `antel make -- …`：转交 make，接管输出/退出码/日志（§4.3）
- `make -p -n` 只读导入，用于依赖图展示（§4.4）

## 6. 测试策略

| 层次         | 内容                                                                                                                             |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| 单元         | plan 生成（参数列表、命名规则、转义）、依赖文件解析、响应文件阈值                                                                |
| 集成         | 现有三条真实构建用例扩展：并行/串行等价、make 与 antel 交替、长路径与空格路径                                                    |
| 跨实现一致性 | §3.3 的三条断言：不漏编（输入 hash ↔ 产物一致）、两种后端产物字节等价、交给 make 的过期目标必须真的重编（Phase 1 起纳入 CI） |
| 性能基线     | 150 TU 场景记录耗时；Phase 0 实测内置线程池 1.11s，走 make 后应不高于它（对照：`make -j8` 0.78s，不含 hash 判定与产物分析） |
| 回归         | `compile_commands.json`、既有日志产物（命令脚本、符号分析）不丢失                                                              |

## 7. 风险与缓解

| 风险                             | 影响                        | 缓解                                                                          |
| -------------------------------- | --------------------------- | ----------------------------------------------------------------------------- |
| 增量判定被 make 的 mtime 语义干扰 | 静默过期产物或冗余重编      | make 只收显式目标、且这些目标在调用前已被删除（§3.2/§3.3）；跨实现一致性测试兜住 |
| 机器上没有 make                  | 构建无法进行                | `backend: auto` 回退到内置线程池并提示；两种后端产物字节等价由测试保证        |
| 参数结构化波及所有调用点         | 一次性改动面较大            | 集中在 Phase 0；compiler/linker/analyze/文档/模板一并更新                     |
| 手工跑内部规则文件后与基线错位   | 下次 antel 构建冗余重编     | 规则文件标注"生成物勿改"；必要时用 `antel sync-baseline` 对齐                |
| 内部规则文件被误当交付物或被手改 | 行为与预期不符              | 每次构建重建、头部带生成标记、文档明确它不是交付物                            |
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

# make 的调用形态（§4.2 的实测依据）
printf 'all:\n\t@echo ok\n' | make -f -        # 从 stdin 读规则（实测可用，本方案不采用，理由见 §4.2）
make -f log/antel.mk -j4 obj/a.o obj/b.o       # 显式目标 + 并行
make -f log/antel.mk obj/a.o                   # 观察："已是最新"并跳过 → 所以要先删目标
make -f log/antel.mk obj/bad.o ; echo $?       # 观察：失败退出码 2

# 为什么不让 make 参与判定（§3.3 的实测依据）
make -j8                     # make 整包构建
antel build                  # 观察：发生变化的文件 1 / 需重新编译文件 1（hash 基线未共享）
antel rebuild                # antel 构建
make -n | grep -c 'gcc '     # 观察：0（make 认可 antel 的产物）

# LTO 全链路
gcc -O2 -flto -c -o lto1.o u001.c && gcc-ar csr liblto.a lto1.o && gcc-nm liblto.a
gcc -O2 -flto main.c liblto.a -o lto_exe

# PCH
g++ -x c++-header inc/common.h -o pch.gch
```

### B. 内部规则文件（`<输出目录>/log/antel.mk`）草案

```make
# 由 antel 生成，请勿手改（每次构建重建；它不是交付物，只是 make 的输入）
OBJDIR  := helloworld_antel/obj
TARGET  := helloworld_antel/helloworld
CC      := gcc
CXX     := g++
CFLAGS  := -std=c++17 -Os -fPIC -I include
LDLIBS  := -lm

.PHONY: all
all: $(TARGET)

# 逐单元显式规则：目标文件名是扁平化的（src/main.c → obj/src_main.o），
# 无法用模式规则表达这种对应关系，所以由 antel 逐个生成
$(OBJDIR)/src_main.o: src/main.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -MMD -MF $@.d -c -o $@ $<

$(OBJDIR)/src_util.o: src/util.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -MMD -MF $@.d -c -o $@ $<

$(TARGET): $(OBJDIR)/src_main.o $(OBJDIR)/src_util.o
	$(CXX) -s -o $@ $^ -Wl,--add-needed -lc -lm $(LDLIBS)

# 只为"有人手工跑这个文件"保留依赖语义；antel 调用时会先删目标，不依赖它
-include $(OBJDIR)/src_main.o.d $(OBJDIR)/src_util.o.d
```

注：`-MF $@.d`（落成 `x.o.d`）与 `-include` 的命名必须一致（§4.1 有实测对比）。antel 调用时只用**显式目标**（且调用前先删掉这些目标），因此默认路径的正确性不依赖 make 的依赖检查；`-include` 是为了有人手工 `make -f <输出目录>/log/antel.mk` 时行为仍然正确。

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

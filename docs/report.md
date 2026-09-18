# 可视化报告示例

`antel analyze`（或配置 `report: true`）会为项目生成一份**自包含**的 `report.html`——所有样式内联、无外部依赖，浏览器直接打开即可看。下面以 `demos/resdemo` 为例展示报告的全部内容，并逐区块说明每个数字怎么看。

!!! tip "在线看 vs 本地生成"
    下面的嵌入窗口就是 resdemo 的真实报告（构建后复制而来）。你也可以在自己项目里生成一份一模一样的：

    ```bash
    cd demos/resdemo
    antel rebuild
    antel analyze               # 生成 resdemo_antel/report.html
    ```

## 报告全貌（resdemo 实例）

<iframe src="resdemo-report.html" width="100%" height="800" style="border:1px solid #334155;border-radius:10px;background:#0f172a;"></iframe>

> 嵌入窗口若显示不全，可打开原始文件查看：[resdemo-report.html](resdemo-report.html)。

## 十个区块逐个说

resdemo 是 GTK4/libadwaita 可执行程序，配置了 `pkg_config`、`data_files`、`gresource`、`embed` 四种能力，正好把报告的功能都激活了。各区块按页面顺序：

| # | 区块 | resdemo 里能看到什么 | 怎么用 |
| --- | --- | --- | --- |
| 1 | **产物** | 目标文件 `resdemo_antel/resdemo`，50.3 KB，`file` 探测为 ELF 可执行文件 | 一眼确认产物是否已生成、体积是否正常 |
| 2 | **增量状态** | hash 基线存在（✓），本次变化文件、待重编清单 | 排查「改了却没重编」：先看 `log/hashes_diff` 与 `log/stale_files` |
| 3 | **编译参数统计** | `-O2×2`、`-Wall×2`，配合一长串 `-I/usr/include/libadwaita-1 ...` | 确认优化级别、宏定义与警告开关是否符合预期 |
| 4 | **资源情况** | 10 个资源文件展开到文件级：`data_files` 3 项（banner.txt/logo.png/payload.bin）、`gresource` 6 项（XML + 4 个引用文件 + 生成的 `gresource.c` 142.3 KB）、`embed` 1 项（payload.bin + `_binary_assets_payload_bin` 符号），每项带 ✓ 复制/编入/嵌入状态 | 核对资源是否如期打包；`gresource.c` 体积即单文件分发的真实成本 |
| 5 | **目标符号表** | 98 个符号按 nm 类型分类（函数/数据/BSS/未定义引用），每个符号独立 chip | 看一个源文件暴露了哪些符号，快速定位未定义引用 |
| 6 | **头文件依赖** | 从 `obj/main.o.d` 反推 `src/main.c` 依赖的头文件 | 理解「改哪个头会触发谁重编」 |
| 7 | **目标文件大小分布** | `gresource.o` 34.5 KB、`main.o` 12.1 KB，条形图带单位 | 找体积异常的编译单元 |
| 8 | **动态依赖** | NEEDED：`libadwaita-1.so.0 libgtk-4.so.1 libgio-2.0.so.0 ...`；ldd 完整解析（每条含地址与路径） | 检查可执行程序到底链了哪些库、是否有 not found |
| 9 | **编译命令** | `compile_commands.json` 里的原样命令（含全部 `-I`/`-D`） | 复现同一次编译、核对参数注入 |
| 10 | **日志产物** | `log/` 下 7 个文件与大小清单 | 每个日志文件去哪找、多大 |

## 数据的真实性

报告里**没有任何虚构数字**——每个数据都来自真实工具的输出，可直接复核：

| 报告数据 | 来源 |
| --- | --- |
| 产物大小/类型 | `file` / `stat` |
| 符号分类与名称 | `nm` |
| 动态依赖 | `readelf -d` / `ldd` |
| 头文件依赖 | 编译生成的 `obj/*.o.d`（`-MMD`） |
| 编译参数词频 | `compile_commands.json`（由 antel 自己生成） |
| 资源类型/大小 | `file` / `os.path.getsize` |
| 增量状态 | `log/hashes`、`log/hashes_diff`、`log/stale_files`（均由 antel 维护） |
| 日志产物 | `log/` 目录扫描 |

配置了资源才有「资源情况」区块；纯代码工程不会出现它。其余区块对任意项目都生成。

## 更多

- 如何触发：配置字段 [`report`](configuration.md)（构建后自动生成）或命令 [`antel analyze`](commands.md)
- 报告字段与构建目录的关系：[构建目录布局](configuration.md)
- 其他示例：`demos/antelstats` 也带 `app_app/report.html`（版本化共享库的消费端报告）
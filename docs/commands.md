# 命令参考

```text
用法：antel [OPTIONS] COMMAND [ARGS]...
```

| 命令      | 作用                                     | 支持 `-f` |
| --------- | ---------------------------------------- | --------- |
| `init`    | 交互式生成 `antel.json`                  | 否        |
| `fetch-ref` | 只下载配置中声明的 Git 项目引用，不编译 | 是        |
| `build`   | 构建项目差异部分                         | 是        |
| `sync-baseline` | 只刷新 hash 基线，不编译（手工跑过内部规则文件后对齐簿记） | 是 |
| `rebuild` | 重新构建项目，不管项目有否被构建过       | 是        |
| `clean`   | 清除构建生成，包括所有中间文件与生成目标 | 是        |
| `link`    | 只链接而不编译                           | 是        |
| `analyze` | 生成可视化分析报告 `report.html`         | 是        |
| `run`     | 执行编译后的结果                         | 是        |
| `install` | 按当前目录的 `install.json` 安装已构建目标 | 否        |
| `uninstall` | 按 `install.json` 和安装清单卸载目标 | 否        |

除 `init`、`install`、`uninstall` 外的命令都接受 `--file` / `-f` 指定配置文件名，默认 `antel`，对应 `antel.json`：

```bash
antel rebuild -f gcc
antel build --file release
```

输出目录会带上配置文件名（`<项目名>_<配置文件名>`），因此同一份源码可以用多套配置产出不同目标，互不干扰。

## fetch-ref

只准备配置中的 `ref` 仓库，不编译或链接：

```bash
antel fetch-ref
antel fetch-ref -f release
```

引用仓库默认下载到 `.antel/refs/`，后续 `build` / `rebuild` 会复用这些缓存。首次下载需要 Git 和网络连接。

## build 与 rebuild

```bash
antel build      # 只编变化的部分，没有变化就什么都不做
antel rebuild    # 清空 obj/ 与 log/，全部重编
```

`build` 的判断依据见[增量构建](incremental-build.md)：源文件或其依赖发生变化、目标文件或依赖文件缺失，才会重新编译；没有差异时只提示「项目没有改动」，不做任何事。

首次构建、`clean` 之后、或者怀疑增量状态不对时，用 `rebuild`。

## install

读取当前目录的 `install.json`，扫描该目录的构建 JSON 配置，将已经生成的目标安装到
指定前缀；不编译、不下载引用、不执行构建钩子，也不需要编译依赖已安装。

```json
{
	"install_path": "/usr/local",
	"projectName": "libpng"
}
```

`install_path` 必填，可以是绝对路径或相对当前目录的路径，支持 `~`。
`projectName` 必填，表示新建的独立安装目录名。上例的完整安装目录是
`/usr/local/libpng/`，所有文件都留在其中，不写入系统的 `bin/lib/share`。
可选 `projects` 接受构建项目名字符串或非空数组，例如 `["png16", "pngviewer"]`；
省略时安装当前目录所有已构建项目。选中的项目必须有构建产物，否则报错。

```bash
antel install
```

- 可执行程序安装到 `<install_path>/<projectName>/bin/`，静态库和共享库安装到该独立目录的 `lib/`。
- 保留文件权限与共享库版本符号链接；重复安装更新同名文件。不同配置的产物若会覆盖
	同一安装路径，命令会在复制前报错，而不是任意选一份。
- 已部署的 `data_files` 安装到 `share/<项目名>_<配置名>/`，保留相对目录结构。
	应用需要支持此资源布局；安装器不会自动修改二进制里的资源路径或 RPATH。
- 不复制源码、头文件、对象文件、日志或报告。配置错误、缺失资源和权限不足均以非零退出。

独立目录带有 `.antel-install` 安装清单，记录安装文件与所属项目，支持重复安装；已存在的非 Antel 目录及越界符号链接
会被拒绝。若父目录需要管理员权限，可自行执行 `sudo antel install`。不自动注册系统
PATH 或动态库缓存；应用可使用 `$ORIGIN/../lib` RPATH，也可单次启动时指定 `LD_LIBRARY_PATH`。

## uninstall

读取当前目录的同一份 `install.json`，根据独立安装目录中的 `.antel-install` 清单卸载：

```bash
antel uninstall
```

`install_path` 和 `projectName` 确定要卸载的目录；可选 `projects` 只卸载清单中属于这些
构建项目的文件，省略则卸载全部记录。不需要构建配置或原始构建产物仍然存在。

只删除记录的文件及符号链接，并清理由这些文件留下的空目录；手动添加的文件保留。
全部移除且目录为空时才删除独立安装目录，不删除其父目录。目标目录不存在时直接成功。
清单非法、路径越界或权限不足时以非零退出；失败后可重新执行。

旧版本的空 `.antel-install` 标记没有文件清单，必须先重新执行 `antel install` 补齐记录，
再卸载。卸载不会清理旧版散装到系统 `bin/lib/share` 的文件，也不会运行 `ldconfig`。
系统目录需要权限时，自行执行 `sudo antel uninstall`。

### 临时清理旧版系统布局

此前直接散装到 `<install_path>/bin`、`lib`、`share` 的文件没有安装清单，可显式使用：

```bash
antel uninstall --legacy-system --dry-run
sudo antel uninstall --legacy-system
```

此选项不卸载 `<install_path>/<projectName>` 独立目录。它根据当前目录的构建配置和
尚存的构建产物推导旧路径，并逐个核对文件内容和符号链接目标；有任何不一致时，整批
拒绝删除。`projects` 筛选仍有效，未找到的旧文件跳过。先预览再执行，不要先 clean 或重编。
只移除核对匹配的文件和空的项目资源目录，不删除系统 `bin/lib/share` 或其中的无关文件。
若此前运行过 `ldconfig`，清理旧共享库后自行运行 `sudo ldconfig` 刷新系统缓存。

## clean

删除整个输出目录（`<项目名>_<配置文件名>/`），包括生成目标、目标文件、日志与 hash 基线。基线也一并删除，所以 `clean` 之后直接 `antel build` 就会做一次全量构建，不必先 `rebuild`。

## link

只做链接，不编译。用于确认链接参数与库依赖是否正确，或手工往 `obj/` 里补了目标文件之后重新生成目标。

## analyze

生成**可视化分析报告**：在输出目录产出 `report.html`（自包含的单文件 HTML，内联 CSS、无外部依赖，浏览器直接打开即可看）。报告包含 10 个分析维度：

| 区块 | 内容 |
| --- | --- |
| **产物** | 生成目标路径、大小与文件类型（`file` 探测），未构建会标出来 |
| **增量状态** | hash 基线是否存在、本次相对基线的变化文件、待重编文件 |
| **编译参数统计** | `-O` / `-std` / `-D` / `-W` / `-f` 各参数词频，一眼看出优化与宏定义 |
| **资源情况** | 配置了资源才有：data_files 逐一展开到文件级（类型/大小/是否已复制），gresource 的 XML 与每个引用文件（前缀、是否已编入、生成 `gresource.c` 大小），embed 每个文件（`_binary_` 符号、是否已嵌入） |
| **目标符号表** | 逐源文件列出符号总数与分类（函数 / 数据 / BSS / 未定义引用），每个符号一个独立 chip，边界清晰 |
| **头文件依赖** | 从 `.d` 文件反推每个源文件依赖了哪些头文件 |
| **目标文件大小分布** | 纯 CSS 条形图，右侧标注带单位的大小 |
| **动态依赖** | exe/shared 的 NEEDED（readelf）与 ldd 解析结果 |
| **编译命令** | `compile_commands.json` 里的原样命令 |
| **日志产物** | `log/` 目录的文件与大小（B/KB/MB）清单 |

```bash
antel analyze
```

报告自动覆盖配置里的全部源文件，无需任何配置字段。构建成功后自动生成则是打开 `report: true`（见[配置参考](configuration.md)），两者产物一致。

## run

只对 `target_type` 为 `exe` 的项目有效，直接执行生成的可执行程序：

```bash
antel run
```

目标类型不是 `exe`、或可执行文件还不存在时，会明确报错并以非 0 退出码结束。

## 退出码

| 情况 | 退出码 |
| --- | --- |
| 命令成功 | 0 |
| 配置文件不存在、字段类型错误、取值非法 | 1 |
| 编译、链接、分析、运行任一环节失败 | 1，失败命令自身的退出码记录在错误信息里 |

约定只有一条：**退出码为 0 就说明这一步真的成功了**。编译或链接失败不会继续往下走，也不会打印「链接完毕」这类成功文案，因此可以直接用在 `&&` 串联或 CI 里。

```bash
antel rebuild && antel run
```

## 常见组合

```bash
# 全量构建后立即运行
antel rebuild && antel run

# 用另一套配置生成共享库
antel rebuild -f shared

# 排查链接问题：只重新链接，再看链接脚本与链接输出
antel link -f release
cat release_release/log/*_link.sh
cat release_release/log/linkInfor
```

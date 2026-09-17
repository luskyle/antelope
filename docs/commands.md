# 命令参考

```text
用法：antel [OPTIONS] COMMAND [ARGS]...
```

| 命令      | 作用                                     | 支持 `-f` |
| --------- | ---------------------------------------- | --------- |
| `init`    | 交互式生成 `antel.json`                  | 否        |
| `build`   | 构建项目差异部分                         | 是        |
| `sync-baseline` | 只刷新 hash 基线，不编译（手工跑过内部规则文件后对齐簿记） | 是 |
| `rebuild` | 重新构建项目，不管项目有否被构建过       | 是        |
| `clean`   | 清除构建生成，包括所有中间文件与生成目标 | 是        |
| `link`    | 只链接而不编译                           | 是        |
| `analyze` | 自动分析指定的 c/c++ 源文件              | 是        |
| `run`     | 执行编译后的结果                         | 是        |

除 `init` 外的命令都接受 `--file` / `-f` 指定配置文件名，默认 `antel`，对应 `antel.json`：

```bash
antel rebuild -f gcc
antel build --file release
```

输出目录会带上配置文件名（`<项目名>_<配置文件名>`），因此同一份源码可以用多套配置产出不同目标，互不干扰。

## build 与 rebuild

```bash
antel build      # 只编变化的部分，没有变化就什么都不做
antel rebuild    # 清空 obj/ 与 log/，全部重编
```

`build` 的判断依据见[增量构建](incremental-build.md)：源文件或其依赖发生变化、目标文件或依赖文件缺失，才会重新编译；没有差异时只提示「项目没有改动」，不做任何事。

首次构建、`clean` 之后、或者怀疑增量状态不对时，用 `rebuild`。

## clean

删除整个输出目录（`<项目名>_<配置文件名>/`），包括生成目标、目标文件、日志与 hash 基线。基线也一并删除，所以 `clean` 之后直接 `antel build` 就会做一次全量构建，不必先 `rebuild`。

## link

只做链接，不编译。用于确认链接参数与库依赖是否正确，或手工往 `obj/` 里补了目标文件之后重新生成目标。

## analyze

对 `analyze_files` 里列出的源文件，用 `objdump -x` 分析它们对应的目标文件，结果写到 `log/<obj>/objdump-x`。目标文件必须已经存在，否则以非 0 退出码结束。

```bash
antel analyze
```

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

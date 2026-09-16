# 配置参考

`antel.json` 由 `antel init` 生成，也可以手写。全部字段如下：

| 字段                | 类型       | 必填 | 含义                                                                 |
| ------------------- | ---------- | ---- | -------------------------------------------------------------------- |
| projectName         | 字符串     | 是   | 项目名，同时决定输出目录名与生成目标名，不能为空                     |
| source              | 字符串数组 | 是   | 参与编译的 c/c++ 源文件路径，相对配置文件所在目录，不能为空          |
| include_directories | 字符串数组 | 否   | 头文件搜索路径，作为 `-I` 传给编译器，其中的文件参与变更检测         |
| target_type         | 字符串     | 是   | `static`、`shared`、`exe`，不区分大小写                              |
| compiler            | 字符串     | 是   | `msvc`、`gxx`、`llvm`，不区分大小写                                  |
| compile_args        | 字符串数组 | 否   | 传给编译器的编译参数                                                 |
| link_args           | 字符串数组 | 否   | 传给链接器的链接参数，如 `["-ldl"]`，只能是字符串数组                |
| analyze_files       | 字符串数组 | 否   | `antel analyze` 要分析的目标文件所对应的源文件                       |
| exclude_source      | 字符串数组 | 否   | 保留字段，当前不参与构建                                             |

!!! warning "取值非法的字段会直接报错退出"
    `target_type` 与 `compiler` 只接受上表列出的取值，写错会以非 0 退出码结束并提示可选值；`source` 为空、`projectName` 为空、`link_args` 不是数组同样会报错。不存在「静默退回默认值」这种行为。

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

## 构建目录

输出目录是 `./<projectName>_<配置文件名>/`：配置文件名 `antel.json`、项目名 `helloworld`，输出目录就是 `helloworld_antel/`。

| 路径 | 内容 |
| --- | --- |
| `<输出目录>/<项目名>` | 可执行目标（`exe`） |
| `<输出目录>/lib<项目名>.a`、`lib<项目名>.so` | 静态库、共享库目标 |
| `<输出目录>/obj/*.o` | 目标文件 |
| `<输出目录>/obj/*.o.d` | 每个编译单元的依赖文件，由 `-MMD -MF` 生成 |
| `<输出目录>/log/hashes` | hash 基线，记录上次成功构建的全部输入文件 |
| `<输出目录>/log/hashes_diff` | 本次相对基线发生变化的文件及前后 hash |
| `<输出目录>/log/stale_files` | 本次实际需要重新编译的源文件清单 |
| `<输出目录>/log/<项目名>.<compiler>` | 本次执行的完整编译命令 |
| `<输出目录>/log/<项目名>_link.sh` | 本次执行的链接脚本，链接就是执行这个脚本 |
| `<输出目录>/log/linkInfor` | 链接过程的完整输出 |
| `<输出目录>/log/readelf_*`、`ldd_*`、`nm_*`、`symbol_*`、`archive_*`、`objdump_*` | 生成目标的符号表、动态依赖、归档内容等分析结果 |
| `<输出目录>/log/<obj>/objdump-x` | `antel analyze` 对单个目标文件的分析结果 |

`antel clean` 会删除整个输出目录，包括生成目标与上表全部内容。
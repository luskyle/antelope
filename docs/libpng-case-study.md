# 成功案例：用 Antelope 构建 libpng

libpng 是用于读取和写入 PNG 图像的 C 库。这个案例把真实上游项目接入 Antelope：
获取源码、准备生成文件、编译静态库与共享库，再用生成的共享库运行一个 PNG 窗口应用，
最后安装到独立目录并按清单卸载。

示例位于仓库的 [demos/libpng](https://github.com/luskyle/antelope/tree/main/demos/libpng)。
这里记录的是 Linux/x86_64、libpng `1.6.60.git` 的验证结果，不是全部平台的移植保证。

## 已经跑通的目标

| 目标 | Antel 配置 | 验证结果 |
| --- | --- | --- |
| 静态库 | `static.json` | `libpng16.a`，包含 17 个实现对象 |
| 共享库 | `shared.json` | 版本化 so、SONAME 和版本链接 |
| 上游测试程序 | `pngtest`、`pnggetset`、`pngvalid` 等 6 个配置 | 构建成功，运行代表性测试 |
| 上游工具 | `pngfix`、`png-fix-itxt` | 构建并运行示例输入 |
| contrib 示例 | `example-iccfrompng` 等 4 个配置 | 独立链接共享库并运行 |
| PNG 窗口应用 | `pngviewer.json` | 解码并显示 Antelope logo，支持打开文件和缩放 |
| 安装与卸载 | `install.json` | 独立目录安装、清单卸载、保留用户文件 |

这些执行结果不代表完整上游 CTest 矩阵已通过，也不表示 Antelope 可以自动转换任意
CMake 项目。示例明确列出了源文件、编译参数和生成步骤。

## 从源码到静态库和共享库

先按[快速开始](quick-start.md)安装 Antelope。示例需要 Git、Python 3、C/C++ 工具链、
AWK、pkg-config 和 zlib 开发包；查看器还需要 GTK 3 开发包与图形桌面会话。

Debian/Ubuntu 可准备以下依赖：

```bash
sudo apt install build-essential git gawk pkg-config zlib1g-dev libgtk-3-dev
```

从仓库根目录开始：

```bash
cd demos/libpng
antel fetch-ref -f static
antel rebuild -f static
antel rebuild -f shared
ar t .antel/build/png16_static/libpng16.a | wc -l
readelf -d .antel/build/png16_shared/libpng16.so.16.60.git | grep SONAME
```

`ref` 将上游 `libpng16` 分支浅克隆到 `.antel/refs/libpng/`。静态库和共享库都编译
15 个核心实现源文件及 2 个 Intel SSE2 源文件，启用 `PNG_INTEL_SSE_OPT=1`。
共享库额外使用 `-fPIC`，并通过 `pkg_config: ["zlib"]` 获取 zlib 链接参数。
静态库的使用者仍需自行链接 zlib 和 libm。

!!! note "上游分支会变化"
    `ref` 指向的分支不是固定提交；已有 checkout 不会自动更新。
    如果获取了更新的上游版本，需要核对源文件清单和 `shared.json` 的 `version`，
    不应假定本文的版本号和对象数量永久不变。

## 不再用 CMake 准备生成文件

libpng 编译需要配置头，版本化共享库还需要 ELF version script。示例通过
`before_build` 在引用仓库准备后、增量扫描和编译之前运行 `prepare_libpng.py`：

```json
{
  "before_build": [
    {
      "command": ["python3", "prepare_libpng.py"],
      "outputs": [
        ".antel/build/libpng-generated/pnglibconf.h",
        ".antel/build/libpng-generated/libpng.vers"
      ]
    }
  ]
}
```

脚本复用上游 `scripts/pnglibconf.h.prebuilt`，不是自行猜测配置宏；再用 C 预处理器
处理上游 `scripts/vers.c`，交给上游 `scripts/dfn.awk` 生成符号版本脚本。
在本次对照中，生成的 `libpng.vers` 与 CMake 产物逐字节一致。
预置配置头并不等于支持所有可选 CMake 配置，按需定制时仍需调整准备逻辑。

`outputs` 参与增量检测：相关头文件变化会使受影响源码重编，链接脚本变化会触发重链接。
命令失败或声明输出缺失时，Antel 报错退出。这个库的构建流程不需要执行 CMake。
字段细节见[配置参考](configuration.md#before_build)。

## 版本化共享库

本次共享库构建生成：

```text
.antel/build/png16_shared/
  libpng16.so.16.60.git
  libpng16.so.16 -> libpng16.so.16.60.git
  libpng16.so -> libpng16.so.16.60.git
```

实际 so 的 SONAME 为 `libpng16.so.16`。配置使用 `version: "16.60.git"`，
并把 `-Wl,--version-script=.antel/build/libpng-generated/libpng.vers` 传给链接器。
库文件名、运行时名称和导出符号版本由配置及上游生成脚本共同控制。

## 用自己的 so 打开 PNG 窗口

![使用自建 libpng 解码 Antelope logo 的 GTK 查看器](images/libpng-viewer.png)

实际窗口截图：透明区域显示棋盘格，底部显示图像尺寸、缩放比例和 libpng 版本。

```bash
antel rebuild -f pngviewer
./.antel/build/pngviewer_pngviewer/pngviewer
./.antel/build/pngviewer_pngviewer/pngviewer /path/to/image.png
```

GTK 3 负责窗口、文件选择器和绘制表面；PNG 解码直接调用我们生成的 libpng 的
`png_image_begin_read_from_file` 和 `png_image_finish_read`，不是交给 GTK 图像加载器。
无参数启动时显示项目自己的透明 PNG logo，由 `data_files` 复制进输出目录。

窗口支持打开 PNG、放大、缩小、适应窗口与透明棋盘背景。错误文件不会替换已显示图像。
图片限制为每边最多 16384 像素、解码后的 RGBA 数据最多 256 MiB。

可检查实际运行路径：

```bash
ldd .antel/build/pngviewer_pngviewer/pngviewer | grep libpng
./.antel/build/pngviewer_pngviewer/pngviewer --smoke-test
```

验证时 `ldd` 指向 `.antel/build/png16_shared/libpng16.so.16`，logo 解码尺寸为 `512 x 512`。
窗口 smoke test 绘制后退出，并将窗口截图保存到 `/tmp/antel-pngviewer.png`。

## 独立目录安装与卸载

示例中的 `install.json`：

```json
{
  "projectName": "libpng",
  "install_path": "/usr/local"
}
```

执行 `antel install` 会新建 `/usr/local/libpng/`，而不是把文件散落到系统目录。
默认安装当前目录全部已构建目标；只安装库和查看器时，添加
`"projects": ["png16", "pngviewer"]`。

```text
/usr/local/libpng/
  .antel-install
  bin/
  lib/
  share/
```

`bin/` 放可执行程序，`lib/` 放静态库、共享库及链接，`share/` 放已部署资源。
`.antel-install` 是逐文件安装清单，记录相对路径和所属构建项目，供重复安装和卸载使用。
不要手动删除或修改它；它不参与程序运行，但影响后续管理。

```bash
# 在 demos/libpng 中执行；/usr/local 通常需要管理员权限
sudo antel install
/usr/local/libpng/bin/pngviewer
sudo antel uninstall
```

查看器用 `$ORIGIN/../lib` 查找包内共享库，并按相对路径找安装后的 logo。
临时安装验证中，整个目录移动后依然能够加载包内 so 并显示图像。
其他上游程序如未设置安装 RPATH，可在单次启动时指定包内 `LD_LIBRARY_PATH`，不要将
独立包注册进全局动态库缓存。

卸载只删除清单里的文件及软链，清理空目录并保留用户额外添加的文件。
它不依赖原来的构建目录；旧版空标记需要先重新安装以补齐清单。
此前散装到系统路径的残留只能显式使用 `uninstall --legacy-system` 清理，先运行
`--dry-run` 核对候选。详见[命令参考](commands.md#uninstall)。

## 复现更多上游程序

源仓库准备好后，构建测试工具与 contrib 示例：

```bash
python3 prepare_icc_fixture.py
for target in pngtest pnggetset pngvalid pngstest pngunknown pngimage pngfix png-fix-itxt; do
    antel rebuild -f "$target"
done
for target in example-iccfrompng example-pngpixel example-pngtopng example-simpleover; do
    antel rebuild -f "$target"
done
./.antel/build/pngtest_pngtest/pngtest .antel/build/pngtest_pngtest/testdata/pngtest.png /tmp/png-roundtrip.png
./.antel/build/pngvalid_pngvalid/pngvalid --gamma-16-to-8
```

图片、ICC fixture 和各个程序的输入要求见[示例说明](examples.md#case-libpng)
及仓库中的 demo README。这个案例展示的是 Antelope 对真实库的构建、生成文件、依赖、
应用和分发流程的组织能力，而不是用一个最小 hello world 替代完整库项目。
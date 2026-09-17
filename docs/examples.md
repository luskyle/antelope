# 示例与效果图

仓库自带的示例工程都在 `test/` 下，都是真实可构建、可运行的项目。下面的效果图与配置一一对应，照抄即可复现。

## gtkcalc：GTK 计算器（`pkg_config` 集成）

位置：`test/gtkcalc/`。一个用 libadwaita（GTK 4）写的计算器，演示最常见的图形项目形态：**GUI + 外部库**。它不手写任何 `-I`/`-l`，全靠 `pkg_config` 注入。

![gtkcalc 界面](images/demo_gtkcalc.png)

**antel.json**（`test/gtkcalc/antel.json`）：

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
    "analyze_files": [],
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
  cd test/gtkcalc
  antel rebuild
  ./gtkcalc_antel/gtkcalc
  ```

- 程序还带了 `--auto-close N`（秒）参数用于无人值守验证，例如 CI 里 `./gtkcalc_antel/gtkcalc --auto-close 3` 会打开窗口 3 秒后自行退出

!!! note "libadwaita 1.1 的几个 API 约束（代码已适配）"
    这套 demo 按 Ubuntu 22.04 自带的 libadwaita 1.1 / GTK 4.6 编写，有三个新手容易踩的点，源码里都有注释：

    1. `AdwApplicationWindow` **没有标题栏区域**——窗口按钮（关闭/最小化/最大化）来自内容顶部的 `AdwHeaderBar`，调 `gtk_window_set_titlebar` 会被 libadwaita 拒绝并崩溃；
    2. 内容必须用 `adw_application_window_set_content` 设置，`gtk_window_set_child` 同样被拒绝；
    3. `g_application_run` 会解析并拒绝未知命令行选项，自定义参数（如 `--auto-close`）要先从 argv 里剥掉。

## resdemo：运行资源打包（`data_files` / `gresource` / `embed`）

位置：`test/resdemo/`。一个程序同时用三种形态携带资源，界面本身也由资源驱动，用来演示完整的资源分发方案：

- **data_files —— 目录分发**：`assets/` 复制进输出目录，可替换；程序按 `/proc/self/exe` 定位（与当前工作目录无关）
- **gresource —— 单文件分发**：整个界面（`main.ui`）、样式（`style.css`）、图标（`logo.png`）、文本（`notes.txt`）全部编译进可执行文件，GtkBuilder / CSS provider 直接按资源路径加载
- **embed —— 单文件分发**：`assets/payload.bin` 经 `ld -r -b binary` 嵌入 ELF，程序用 `_binary_` 符号访问

![resdemo 界面](images/demo_resdemo.png)

**antel.json**（`test/resdemo/antel.json`）：

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
    "analyze_files": [],
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
test/resdemo/
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
cd test/resdemo
antel rebuild
./resdemo_antel/resdemo
```

窗口内左下角的开关切换深色/浅色主题（颜色来自 gresource 编进去的 `style.css`），右侧按钮重新从磁盘读取 `data_files` 的 banner——两个交互都演示「改资源 → build → 界面跟着变」。

!!! note "为什么能放心走增量"
    `glib-compile-resources` 对同样的输入生成**逐字节相同**的输出（已实测），因此 gresource 源可以安全进入 antel 的 hash 基线；`ld -r -b binary` 的符号命名是确定的规则：`assets/payload.bin` → `_binary_assets_payload_bin_start/_end/_size`（路径里非字母数字字符全部换成下划线）。这两条是设计文档（DESIGN.md）与测试里明确的契约。
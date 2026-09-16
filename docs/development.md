# 开发与发布

## 环境准备

```bash
git clone https://github.com/luskyle/antelope
cd antelope
python3 -m pip install -e '.[test]'
```

## 测试

```bash
python3 -m pytest
```

`tests/test_antelope.py` 里的用例都是真实构建：在临时目录里生成一个最小 C 项目，实际调用 gcc/g++ 编译、链接、运行。覆盖三件事：

- 改头文件后 `build` 必须重编受影响的源文件，并更新生成目标
- 编译失败必须以非 0 退出码结束，且不产出目标、不打印链接成功
- `link_args` 只能是普通字符串数组，其中的内容不会被当成代码执行

!!! tip "pytest 起不来时"
    若环境里装了会干扰 pytest 启动的第三方插件（例如 ROS 2 提供的 launch_testing），改用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest`。

## 打包

```bash
python3 -m pip install build
python3 -m build
```

产出 `dist/antelope-<版本>-py3-none-any.whl` 与 `dist/antelope-<版本>.tar.gz`。

## 发布

1. 修改 `setup.py` 中的 `version`
2. 提交、打 tag 并推送：

    ```bash
    git tag v1.0 && git push origin v1.0
    ```

3. `Release` 工作流会校验 tag 与 `setup.py` 的版本是否一致（`v1.0` 只能对应 `version='1.0'`，不一致直接失败），然后构建 sdist 与 wheel，创建同名 GitHub Release 并把两个包作为附件

## 工作流

| 工作流       | 触发                              | 内容                                                                    |
| ------------ | --------------------------------- | ----------------------------------------------------------------------- |
| `ci.yml`     | push main、PR                     | 在 Python 3.9 / 3.11 / 3.13 上跑测试与打包校验，并执行一次真实编译链接冒烟 |
| `pages.yml`  | `docs/**`、`mkdocs.yml` 变更、手动触发 | 用 Zensical 构建本站并部署到 GitHub Pages                               |
| `release.yml` | 推送 `v*` tag                    | 校验版本一致性、构建 sdist 与 wheel、创建 Release                       |

## 文档站

本站源码在 `docs/`，配置在 `mkdocs.yml`，由 **Zensical** 构建——Material for MkDocs 作者的官方后继项目，直接读 MkDocs 1.x 的配置。本地预览：

```bash
python3 -m pip install -r docs/requirements.txt
zensical serve
```

提交前建议按 CI 的方式构建一遍，链接写错、页面没进导航都会让构建失败：

```bash
zensical build --strict
```

!!! note "为什么用 Zensical，以及怎么退回去"
    MkDocs 1.x 已长期无人维护，MkDocs 2.0 会移除插件系统并重写主题，官方声明 Material for MkDocs 无法迁移到 MkDocs 2.0，并建议迁移到 Zensical。本站是新建的，因此直接落在后继项目上；`docs/requirements.txt` 里把版本钉死以避免 0.x 的接口变动影响构建。`mkdocs.yml` 对两个生成器通用，若要退回 Material，把 `docs/requirements.txt` 换成 `mkdocs-material>=9.7,<10`（构建命令相应换成 `mkdocs build --strict`）即可。

Pages 未启用时工作流会自行启用，也可以在仓库的 Settings → Pages 里手动把 Source 选为 GitHub Actions。

## 目录结构

```text
antelope/            包源码
├── antelope.py      CLI 入口与构建流程编排
├── build_plan.py    编译单元与链接作业的数据模型
├── md5.py           hash 基线与变更检测
├── enums.py         枚举
├── errors.py        构建错误类型
├── compiler/        编译命令生成与增量判定
├── linker/          链接命令生成与产物分析
├── analyze/         目标文件分析
├── args_parser/     antel.json 解析与参数拼装
├── cli/             init 交互与终端提示
├── json_ops/        antel.json 模板生成
├── os_ops/          命令执行、目录、日志
└── runner/          运行生成的目标
docs/                文档站源码
tests/               pytest 用例
test/                示例工程
```
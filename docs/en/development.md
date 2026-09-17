# Development and Release

## Environment Setup

```bash
git clone https://github.com/luskyle/antelope
cd antelope
python3 -m pip install -e '.[test]'
```

## Testing

```bash
python3 -m pytest
```

The cases in `tests/test_antelope.py` are real builds: they generate a minimal C project in a temporary directory and actually invoke gcc/g++ to compile, link, and run it. They cover three things:

- After a header change, `build` must recompile the affected source files and update the generated targets
- A failed compilation must exit with a non-zero code, produce no targets, and not print that linking succeeded
- `link_args` can only be a plain array of strings; its contents are never executed as code

!!! tip "When pytest won't start"
    If third-party plugins that interfere with pytest startup are installed in the environment (such as ROS 2's launch_testing), use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest` instead.

## Packaging

```bash
python3 -m pip install build
python3 -m build
```

This produces `dist/antelope-<version>-py3-none-any.whl` and `dist/antelope-<version>.tar.gz`.

## Releasing

1. Update `version` in `setup.py`
2. Commit, tag, and push:

    ```bash
    git tag v1.0 && git push origin v1.0
    ```

3. The `Release` workflow verifies that the tag and the version in `setup.py` match (`v1.0` must correspond to `version='1.0'`; any mismatch fails immediately), then builds the sdist and wheel, creates a GitHub Release with the same name, and attaches both packages to it.

## Workflows

| Workflow      | Trigger                               | Contents                                                                                |
| ------------- | ------------------------------------- | --------------------------------------------------------------------------------------- |
| `ci.yml`      | push main, PR                         | Runs tests and packaging checks on Python 3.9 / 3.11 / 3.13, plus one real compile-and-link smoke test |
| `pages.yml`   | `docs/**`, `mkdocs.yml` changes, manual trigger | Builds this site with Zensical and deploys it to GitHub Pages                    |
| `release.yml` | push of a `v*` tag                    | Verifies version consistency, builds the sdist and wheel, and creates the Release        |

## Documentation Site

The site source lives in `docs/`, its config in `mkdocs.yml`, and it is built by **Zensical** — the official successor to Material for MkDocs, which reads MkDocs 1.x configuration directly. Local preview:

```bash
python3 -m pip install -r docs/requirements.txt
zensical serve
```

Before committing, it's a good idea to build once the way CI does — a broken link or a page left out of the navigation fails the build:

```bash
zensical build --strict
```

!!! note "Why Zensical, and how to switch back"
    MkDocs 1.x has been unmaintained for a long time; MkDocs 2.0 removes the plugin system and rewrites themes, and the official word is that Material for MkDocs cannot be migrated to MkDocs 2.0 — the recommendation is to move to Zensical. This site is new, so it lands directly on the successor project; `docs/requirements.txt` pins the version to keep 0.x API churn from breaking the build. `mkdocs.yml` works with both generators, so to switch back to Material, replace `docs/requirements.txt` with `mkdocs-material>=9.7,<10` (and switch the build command to `mkdocs build --strict`).

If Pages is not enabled, the workflow enables it on its own; you can also manually select GitHub Actions as the Source in the repository's Settings → Pages.

## Directory Structure

```text
antelope/            package source
├── antelope.py      CLI entry point and build pipeline orchestration
├── build_plan.py    data model for compile units and link jobs
├── md5.py           hash baselines and change detection
├── enums.py         enums
├── errors.py        build error types
├── compiler/        compile command generation and incremental decisions
├── linker/          link command generation and artifact analysis
├── analyze/         object file analysis
├── args_parser/     antel.json parsing and argument assembly
├── cli/             init interaction and terminal prompts
├── json_ops/        antel.json template generation
├── os_ops/          command execution, directories, logging
└── runner/          running generated targets
docs/                documentation site source
tests/               pytest cases
demos/               example projects (helloworld single file, cdemo multiple files, gtkcalc GTK calculator, resdemo resource packaging demo, antelstats versioned library with sanitizers/coverage)
```
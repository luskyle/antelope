"""测试共享的工具函数与 fixture（被 test_antelope.py 与 test_make_backend.py 共用）"""

import json
import subprocess

import pytest


def write_config(project_dir, **overrides):
    config = {
        'projectName': 'demo',
        'target_type': 'exe',
        'compiler': 'gxx',
        'source': ['src/main.c'],
        'exclude_source': [],
        'include_directories': ['inc'],
        'compile_args': ['-w'],
        'link_args': [],
    }
    config.update(overrides)

    with open(project_dir / 'antel.json', 'w') as file:
        json.dump(config, file, indent=4)


def write_sources(project_dir):
    (project_dir / 'src').mkdir(exist_ok=True)
    (project_dir / 'inc').mkdir(exist_ok=True)
    (project_dir / 'src' / 'main.c').write_text(
        '#include <stdio.h>\n'
        '#include "foo.h"\n'
        '#include "bar.h"\n'
        'int main(){ printf("%s %s\\n", FOO_MSG, BAR_MSG); }\n')
    (project_dir / 'src' / 'foo.h').write_text('#define FOO_MSG "foo1"\n')
    (project_dir / 'inc' / 'bar.h').write_text('#define BAR_MSG "bar1"\n')


def run_program(project_dir):
    program = project_dir / 'demo_antel' / 'demo'
    assert program.exists(), '未生成可执行程序'
    return subprocess.run([str(program)], capture_output=True, text=True).stdout.strip()


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_sources(tmp_path)
    write_config(tmp_path)
    return tmp_path
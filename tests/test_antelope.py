import json
import shutil
import subprocess

import pytest
from click.testing import CliRunner

from antelope.antelope import main

pytestmark = pytest.mark.skipif(shutil.which('gcc') is None or shutil.which('g++') is None,
                                reason='需要 gcc/g++ 才能执行真实构建')


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
        'analyze_files': [],
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


def test_header_change_is_rebuilt(project):
    """头文件变化后 build 必须重编受影响的源文件，不能留下过期目标"""
    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0
    assert run_program(project) == 'foo1 bar1'

    # 与源文件同目录的头文件，只能靠 -MMD 记录的依赖发现
    (project / 'src' / 'foo.h').write_text('#define FOO_MSG "foo2"\n')
    assert CliRunner().invoke(main, ['build']).exit_code == 0
    assert run_program(project) == 'foo2 bar1'

    # include_directories 中的头文件
    (project / 'inc' / 'bar.h').write_text('#define BAR_MSG "bar2"\n')
    assert CliRunner().invoke(main, ['build']).exit_code == 0
    assert run_program(project) == 'foo2 bar2'

    # 没有改动时不重编
    obj_file = project / 'demo_antel' / 'obj' / 'src_main.o'
    before = obj_file.stat().st_mtime_ns
    assert CliRunner().invoke(main, ['build']).exit_code == 0
    assert obj_file.stat().st_mtime_ns == before


def test_compile_error_exits_nonzero(project):
    """编译失败必须以非 0 退出码结束，且不产出目标"""
    (project / 'src' / 'main.c').write_text('int main(){ this is not c }\n')

    result = CliRunner().invoke(main, ['rebuild'])

    assert result.exit_code != 0
    assert '命令执行失败' in result.output
    assert '链接完毕' not in result.output
    assert not (project / 'demo_antel' / 'demo').exists()


def test_link_args_are_not_evaluated(project):
    """link_args 只能是不含代码的字符串数组，其中的内容不得被执行"""
    marker = project / 'executed.txt'
    write_config(project, link_args=f"[__import__('os').system('touch {marker}')]")

    result = CliRunner().invoke(main, ['rebuild'])

    assert result.exit_code != 0
    assert 'link_args' in result.output
    assert not marker.exists()

    write_config(project, link_args=['-lm'])
    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0
import json
import os
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


def test_parallel_and_serial_artifacts_match(project):
    """jobs 只影响并行度：串行与并行必须产出完全一致的目标"""
    extra_sources = []
    for index in (1, 2, 3):
        name = f'src/aux{index}.c'
        (project / name).write_text(f'int aux{index}(void){{ return {index}; }}\n')
        extra_sources.append(name)

    source = ['src/main.c'] + extra_sources

    write_config(project, source=source, jobs=1)
    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0
    serial_bytes = (project / 'demo_antel' / 'demo').read_bytes()

    write_config(project, source=source, jobs=4)
    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0
    parallel_bytes = (project / 'demo_antel' / 'demo').read_bytes()

    assert serial_bytes == parallel_bytes


def test_compile_commands_json_is_written(project):
    """构建后应产出 clangd 可用的 compile_commands.json"""
    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0

    entries = json.loads((project / 'demo_antel' / 'compile_commands.json').read_text())

    assert len(entries) == 1
    assert entries[0]['file'] == 'src/main.c'
    assert entries[0]['directory'] == str(project)
    assert entries[0]['arguments'][0] in ('gcc', 'g++')
    assert '-c' in entries[0]['arguments']
    assert entries[0]['output'] == 'demo_antel/obj/src_main.o'


def test_compile_commands_can_be_disabled(project):
    write_config(project, compile_commands=False)
    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0

    assert not (project / 'demo_antel' / 'compile_commands.json').exists()


def test_source_path_with_spaces(project):
    """路径含空格时参数不得被切碎（结构化 argv 的直接收益）"""
    spaced = project / 'src dir'
    spaced.mkdir()
    (spaced / 'main.c').write_text('#include <stdio.h>\nint main(){ printf("spaced\\n"); }\n')
    write_config(project, source=['src dir/main.c'], include_directories=[])

    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0
    assert run_program(project) == 'spaced'


def test_project_name_rejects_shell_characters(project):
    """项目名会写进链接脚本，shell 元字符必须被拒绝"""
    write_config(project, projectName='demo;rm -rf /')
    result = CliRunner().invoke(main, ['rebuild'])

    assert result.exit_code != 0
    assert 'projectName' in result.output


def test_invalid_jobs_is_rejected(project):
    write_config(project, jobs=0)
    result = CliRunner().invoke(main, ['rebuild'])

    assert result.exit_code != 0
    assert 'jobs' in result.output


def test_make_backend_builds_with_rule_file(project):
    """backend: make 时由 make 执行编译，并落一份内部规则文件（不是交付物）"""
    write_config(project, backend='make', jobs=2)
    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0
    assert run_program(project) == 'foo1 bar1'

    text = (project / 'demo_antel' / 'log' / 'antel.mk').read_text()
    assert '请勿手改' in text
    assert 'demo_antel/obj/src_main.o: src/main.c' in text
    assert '-include demo_antel/obj/src_main.o.d' in text

    # 项目根不应多出 Makefile
    assert not (project / 'Makefile').exists()


def test_make_backend_rebuilds_changed_header(project):
    """make 后端下改头文件必须重编受影响的编译单元"""
    write_config(project, backend='make')
    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0
    assert run_program(project) == 'foo1 bar1'

    (project / 'inc' / 'bar.h').write_text('#define BAR_MSG "bar2"\n')
    assert CliRunner().invoke(main, ['build']).exit_code == 0

    assert run_program(project) == 'foo1 bar2'


def test_make_backend_is_not_fooled_by_mtime(project):
    """
    把目标文件的时间戳改成比头文件还新之后，make 仍必须重建：
    antel 按 hash 判定它过期，并在交给 make 之前先删掉它（DESIGN §3.2 约定 2）
    """
    write_config(project, backend='make')
    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0

    (project / 'inc' / 'bar.h').write_text('#define BAR_MSG "bar3"\n')
    os.utime(project / 'demo_antel' / 'obj' / 'src_main.o')

    assert CliRunner().invoke(main, ['build']).exit_code == 0

    assert run_program(project) == 'foo1 bar3'


def test_make_backend_supports_paths_with_spaces(project):
    """含空格路径在 make 后端下同样可用（规则里做了转义，gcc 的 .d 也会转义）"""
    spaced = project / 'src dir'
    spaced.mkdir()
    (spaced / 'main.c').write_text('#include <stdio.h>\nint main(){ printf("spaced\\n"); }\n')
    write_config(project, source=['src dir/main.c'], include_directories=[], backend='make')

    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0

    assert run_program(project) == 'spaced'


def test_make_backend_failure_exits_nonzero(project):
    """make 失败（退出码 2）时 antel 以非 0 退出，并指出规则文件"""
    write_config(project, backend='make')
    (project / 'src' / 'main.c').write_text('int main(){ this is not c }\n')

    result = CliRunner().invoke(main, ['rebuild'])

    assert result.exit_code != 0
    assert '规则文件' in result.output
    assert '链接完毕' not in result.output
    assert not (project / 'demo_antel' / 'demo').exists()
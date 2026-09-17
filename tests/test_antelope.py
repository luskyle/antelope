import json
import os
import shutil

import pytest
from click.testing import CliRunner

from antelope.antelope import main
from antelope.antelope import Antelope, describeBackend
from antelope.makefile import MakeRunner
from conftest import write_config, write_sources, run_program

pytestmark = pytest.mark.skipif(shutil.which('gcc') is None or shutil.which('g++') is None,
                                reason='需要 gcc/g++ 才能执行真实构建')


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


def test_auto_backend_uses_make(project):
    """backend 默认 auto：机器上有 make 就走 make"""
    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0

    assert (project / 'demo_antel' / 'log' / 'antel.mk').exists()
    assert run_program(project) == 'foo1 bar1'


def test_auto_backend_falls_back_without_make(project, monkeypatch):
    """
    没有 make 时 auto 回退到内置执行器，且产物与走 make 时一致。
    注意 Console.WriteNotice 走 prompt_toolkit，不进入 CliRunner 的捕获，
    因此这里断言行为（规则文件是否生成、产物是否一致），不断言提示文本
    """
    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0
    with_make = (project / 'demo_antel' / 'demo').read_bytes()
    assert (project / 'demo_antel' / 'log' / 'antel.mk').exists()

    monkeypatch.setattr('antelope.antelope.makeAvailable', lambda: False)
    assert CliRunner().invoke(main, ['rebuild']).exit_code == 0

    # rebuild 会重建 log/，规则文件不再出现即说明没有走 make
    assert not (project / 'demo_antel' / 'log' / 'antel.mk').exists()
    assert (project / 'demo_antel' / 'demo').read_bytes() == with_make
    assert describeBackend('auto') == 'auto → antel（未找到 make）'


def test_builtin_executor_serializes_under_make(monkeypatch):
    """被 make 调用时内置执行器退回串行；make 执行器交给 MAKEFLAGS 自己处理"""
    antel = Antelope()
    antel.jobs = 8

    monkeypatch.setattr('antelope.antelope.parentMakeFlags', lambda: '-j4 --jobserver-auth=3,4')
    assert antel.executorJobs('antel') == 1
    assert antel.executorJobs('make') == 8

    monkeypatch.setattr('antelope.antelope.parentMakeFlags', lambda: '')
    assert antel.executorJobs('antel') == 8


def test_make_argv_respects_parent_makeflags(monkeypatch):
    """被 make 调用时不传 -j，把并行度交给 MAKEFLAGS 与 jobserver"""
    runner = MakeRunner('out', 'demo', jobs=8)

    monkeypatch.setattr('antelope.makefile.parentMakeFlags', lambda: '')
    assert '-j8' in runner.buildArgv('out/log/antel.mk', ['out/obj/a.o'])

    monkeypatch.setattr('antelope.makefile.parentMakeFlags', lambda: '-j4 --jobserver-auth=3,4')
    argv = runner.buildArgv('out/log/antel.mk', ['out/obj/a.o'])

    assert not any(item.startswith('-j') for item in argv)
    assert argv == ['make', '-f', 'out/log/antel.mk', 'out/obj/a.o']
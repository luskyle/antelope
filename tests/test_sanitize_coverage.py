"""P2-3：覆盖率与消毒器测试。

coverage: true → 编译带 -fprofile-arcs -ftest-coverage（产出 .gcno），
链接带 --coverage；运行后产生 .gcda，gcov 能产出报告，clean 全部回收。

sanitize: [...] → 编译与链接都带 -fsanitize=<item>，含地址消毒器时可运行。
"""

import os
import shutil
import subprocess

import pytest
from click.testing import CliRunner

from antelope.antelope import main
from conftest import write_config, run_program

pytestmark = pytest.mark.skipif(shutil.which('gcc') is None or shutil.which('g++') is None,
                                reason='需要 gcc/g++ 才能执行真实构建')


def antel(*args):
    return CliRunner().invoke(main, list(args))


@pytest.fixture
def simple_project(project):
    write_config(project, backend='antel', coverage=True)
    return project


def test_coverage_flags_and_gcov_report(project):
    """coverage: true：编译/链接带覆盖率参数，运行后 gcov 能产出报告"""
    write_config(project, backend='antel', coverage=True)
    result = antel('rebuild')

    assert result.exit_code == 0, result.output

    compile_log = (project / 'demo_antel' / 'log' / 'demo.gxx').read_text()
    assert '-fprofile-arcs' in compile_log
    assert '-ftest-coverage' in compile_log

    link_script = (project / 'demo_antel' / 'log' / 'demo_link.sh').read_text()
    assert '--coverage' in link_script

    # 编译产生了 .gcno；运行程序后生成 .gcda
    assert (project / 'demo_antel' / 'obj' / 'src_main.gcno').exists()
    subprocess.run([str(project / 'demo_antel' / 'demo')], check=True)
    gcda = project / 'demo_antel' / 'obj' / 'src_main.gcda'
    assert gcda.exists()

    # gcov 在本机可用时能基于 .gcda 产出报告（文件名取源文件 basename）
    if shutil.which('gcov'):
        subprocess.run(['gcov', 'src_main.gcda'],
                       cwd=project / 'demo_antel' / 'obj', check=True)
        assert (project / 'demo_antel' / 'obj' / 'main.c.gcov').exists()


def test_clean_removes_coverage_artifacts(project):
    """clean 后无残留覆盖率文件（.gcda/.gcno 都在输出目录内）"""
    write_config(project, backend='antel', coverage=True)
    assert antel('rebuild').exit_code == 0
    subprocess.run([str(project / 'demo_antel' / 'demo')], check=True)

    obj_dir = project / 'demo_antel' / 'obj'
    assert list(obj_dir.glob('*.gcno')) != []
    assert list(obj_dir.glob('*.gcda')) != []

    antel('clean')
    assert not (project / 'demo_antel').exists()


def test_sanitize_flags_compile_and_link(project):
    """sanitize: ['address']：编译与链接都带 -fsanitize=address，程序可运行"""
    write_config(project, backend='antel', sanitize=['address'])
    result = antel('rebuild')

    assert result.exit_code == 0, result.output

    compile_log = (project / 'demo_antel' / 'log' / 'demo.gxx').read_text()
    assert '-fsanitize=address' in compile_log

    link_script = (project / 'demo_antel' / 'log' / 'demo_link.sh').read_text()
    assert '-fsanitize=address' in link_script

    # 地址消毒器下正常运行，输出与普通构建一致
    assert run_program(project) == 'foo1 bar1'


def test_sanitize_catches_bug(project):
    """sanitize 真的能抓错：堆越界写让程序以非 0 退出并给出消毒器报错"""
    (project / 'src' / 'main.c').write_text(
        '#include <stdio.h>\n'
        '#include <stdlib.h>\n'
        'int main(){ char *buf = malloc(4); buf[100] = 1; printf("no\\n"); return 0; }\n')
    write_config(project, backend='antel', sanitize=['address'])

    result = antel('rebuild')
    assert result.exit_code == 0, result.output

    run = subprocess.run([str(project / 'demo_antel' / 'demo')],
                         capture_output=True, text=True)
    assert run.returncode != 0
    assert 'AddressSanitizer' in run.stderr or 'ERROR: AddressSanitizer' in run.stdout
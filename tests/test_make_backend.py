"""M1 收口：跨实现一致性测试（DESIGN §3.3 的三条断言）。

内置执行器与 make 执行器必须同时满足：

1. **不漏编**：任意输入变化后，产物必须与输入一致（按 hash 判定，而不是只看时间戳）
2. **产物等价**：同一棵树用两种后端构建，产物字节一致
3. **不被 make 跳过**：交给 make 的过期目标必须真的重编（先删目标，DESIGN §3.2 约定 2）

另外覆盖 `antel sync-baseline`（手工跑过内部规则文件之后对齐 hash 基线）。
"""

import os
import shutil
import subprocess

import pytest
from click.testing import CliRunner

from antelope.antelope import main
from conftest import write_config, run_program

pytestmark = pytest.mark.skipif(shutil.which('gcc') is None or shutil.which('g++') is None
                                or shutil.which('make') is None,
                                reason='需要 gcc/g++ 与 make 才能执行真实构建')


def antel(*args):
    return CliRunner().invoke(main, list(args))


def test_inputs_are_never_left_stale(project):
    """断言一（不漏编）：一组输入变化后，make 后端的产物必须始终跟上输入"""
    write_config(project, backend='make')
    assert antel('rebuild').exit_code == 0

    scenarios = [
        # (改哪个文件, 改成什么, 运行预期)
        ('inc/bar.h',  '#define BAR_MSG "bar2"\n',  'foo1 bar2'),
        ('src/foo.h',  '#define FOO_MSG "foo3"\n',  'foo3 bar2'),
        ('src/main.c', '#include "foo.h"\n#include "bar.h"\nint main(){ '
                       'printf("%s+%s\\n", FOO_MSG, BAR_MSG); }\n', 'foo3+bar2'),
    ]

    for path, content, expected in scenarios:
        (project / path).write_text(content)
        assert antel('build').exit_code == 0, f'场景 {path} 构建失败'
        assert run_program(project) == expected, f'场景 {path} 产物与输入不一致（漏编）'


def test_backends_produce_identical_artifacts(project):
    """断言二（产物等价）：同一棵树用两种后端构建，可执行文件字节一致"""
    write_config(project, backend='make')
    assert antel('rebuild').exit_code == 0
    with_make = (project / 'demo_antel' / 'demo').read_bytes()

    write_config(project, backend='antel')
    assert antel('rebuild').exit_code == 0
    with_antel = (project / 'demo_antel' / 'demo').read_bytes()

    assert with_make == with_antel


def test_make_never_skips_a_stale_object(project):
    """断言三（不被 make 跳过）：目标文件时间戳比头文件还新时仍必须重编"""
    write_config(project, backend='make')
    assert antel('rebuild').exit_code == 0

    (project / 'inc' / 'bar.h').write_text('#define BAR_MSG "bar2"\n')
    os.utime(project / 'demo_antel' / 'obj' / 'src_main.o')

    assert antel('build').exit_code == 0

    assert run_program(project) == 'foo1 bar2'


def test_sync_baseline_after_manual_make(project):
    """手工跑过内部规则文件（绕过 antel 簿记）后，sync-baseline 能让 build 不再重编"""
    write_config(project, backend='make')
    assert antel('rebuild').exit_code == 0
    rule_file = project / 'demo_antel' / 'log' / 'antel.mk'

    # 对照组：改头文件、手工跑规则文件、但不 sync —— antel 会认为仍要重编
    (project / 'inc' / 'bar.h').write_text('#define BAR_MSG "bar2"\n')
    subprocess.run(['make', '-f', str(rule_file), 'all'], cwd=project, check=True)
    obj_file = project / 'demo_antel' / 'obj' / 'src_main.o'
    before = obj_file.stat().st_mtime_ns
    assert antel('build').exit_code == 0
    assert obj_file.stat().st_mtime_ns != before, '对照失败：未 sync 时 build 应该仍要重编'

    # 实验组：改头文件、手工跑规则文件、sync —— build 不再重编
    (project / 'inc' / 'bar.h').write_text('#define BAR_MSG "bar3"\n')
    subprocess.run(['make', '-f', str(rule_file), 'all'], cwd=project, check=True)
    assert antel('sync-baseline').exit_code == 0
    before = obj_file.stat().st_mtime_ns
    assert antel('build').exit_code == 0
    assert obj_file.stat().st_mtime_ns == before, 'sync-baseline 之后 build 不应重编'
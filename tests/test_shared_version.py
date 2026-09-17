"""P2-4：版本化动态库测试。

version: "1.0.0" → 产出 libX.so.1.0.0 并生成软链 libX.so.1 与 libX.so；
链接命令带 -Wl,-soname；readelf 能读到 SONAME；
用 soname 链接可执行程序，配合 rpath 可以加载运行。
"""

import os
import shutil
import subprocess

import pytest
from click.testing import CliRunner

from antelope.antelope import main
from conftest import write_config

pytestmark = pytest.mark.skipif(shutil.which('gcc') is None or shutil.which('g++') is None,
                                reason='需要 gcc/g++ 才能执行真实构建')


def antel(*args):
    return CliRunner().invoke(main, list(args))


def write_shared_project(project, version='1.0.0', soname='', rpath=None):
    """一个供链接执行的共享库：main 依赖同一个源里的函数（演示 soname 查找）"""
    (project / 'src' / 'main.c').write_text(
        '#include <stdio.h>\n'
        'int greeting(void){ return 42; }\n'
        'int main(){ printf("greeting=%d\\n", greeting()); return 0; }\n')
    overrides = dict(source=['src/main.c'], compile_args=['-w', '-fPIC'],
                     target_type='shared', version=version)
    if soname:
        overrides['soname'] = soname
    if rpath is not None:
        overrides['rpath'] = rpath
    write_config(project, **overrides)


def test_versioned_shared_lib_artifacts(project):
    """version 配置后产出 libX.so.<版本> 文件与软链，SONAME 正确"""
    write_shared_project(project, version='1.0.0')
    result = antel('rebuild')

    assert result.exit_code == 0, result.output

    out = project / 'demo_antel'
    real = out / 'libdemo.so.1.0.0'
    by_major = out / 'libdemo.so.1'
    by_plain = out / 'libdemo.so'

    assert real.exists()
    assert by_major.is_symlink()
    assert by_plain.is_symlink()
    assert os.path.realpath(by_major) == str(real)
    assert os.path.realpath(by_plain) == str(real)

    # readelf 里 SONAME 是 libdemo.so.1（由 version 主版本推导）
    readelf = subprocess.run(['readelf', '-d', str(real)],
                             capture_output=True, text=True).stdout
    assert 'SONAME' in readelf
    assert 'libdemo.so.1' in readelf

    # 链接命令里带 -Wl,-soname
    link_script = (out / 'log' / 'demo_link.sh').read_text()
    assert '-Wl,-soname,libdemo.so.1' in link_script


def test_explicit_soname_wins(project):
    """显式配置 soname 优先于 version 推导"""
    write_shared_project(project, version='2.3.4', soname='libcustom.so.2')
    assert antel('rebuild').exit_code == 0

    out = project / 'demo_antel'
    real = out / 'libdemo.so.2.3.4'
    readelf = subprocess.run(['readelf', '-d', str(real)],
                             capture_output=True, text=True).stdout
    assert 'libcustom.so.2' in readelf
    assert (out / 'libcustom.so.2').is_symlink()


def test_consumer_links_by_soname_and_runs_with_rpath(project):
    """
    soname 链接与加载：可执行程序依赖库的 SONAME（libdemo.so.1），
    构建可执行程序时通过 -L 与 -l 链接；运行靠 rpath 指向输出目录。
    """
    write_shared_project(project, version='1.0.0')
    assert antel('rebuild').exit_code == 0

    out = project / 'demo_antel'

    # 第二个配置：可执行程序，链接上面的库（-L 指向输出目录，-l demo）
    (project / 'main.c').write_text(
        '#include <stdio.h>\n'
        'extern int greeting(void);\n'
        'int main(){ printf("via-lib=%d\\n", greeting()); return 0; }\n')
    consumer = {
        'projectName': 'consumer',
        'target_type': 'exe',
        'compiler': 'gxx',
        'source': ['main.c'],
        'exclude_source': [],
        'include_directories': [],
        'compile_args': ['-w'],
        'link_args': ['-Ldemo_antel', '-ldemo'],
        'rpath': ['$ORIGIN/../demo_antel'],
    }
    import json
    (project / 'consumer.json').write_text(json.dumps(consumer, indent=4))
    assert antel('rebuild', '-f', 'consumer').exit_code == 0

    # 正常跑：rpath 指向库所在目录，运行时按 SONAME 找到 libdemo.so.1
    run = subprocess.run([str(project / 'consumer_consumer' / 'consumer')],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == 'via-lib=42'

    # 读动态依赖应记录 SONAME 而非文件名
    ldd = subprocess.run(['ldd', str(project / 'consumer_consumer' / 'consumer')],
                         capture_output=True, text=True).stdout
    assert 'libdemo.so.1' in ldd


def test_clean_removes_version_links(project):
    """clean 回收含软链的整个输出目录"""
    write_shared_project(project, version='1.0.0')
    assert antel('rebuild').exit_code == 0
    assert (project / 'demo_antel').exists()

    antel('clean')
    assert not (project / 'demo_antel').exists()


def test_static_library_links_successfully(project):
    """static 目标必须产出 libX.a（回归：P2-4 重构后 static 分支缺失 output 变量）"""
    (project / 'src' / 'main.c').write_text(
        '#include <stdio.h>\n'
        'int lib_value(void){ return 7; }\n'
        'int main(){ printf("v=%d\\n", lib_value()); return 0; }\n')
    write_config(project, source=['src/main.c'], target_type='static', compile_args=['-w'])

    result = antel('rebuild')

    assert result.exit_code == 0, result.output
    archive = project / 'demo_antel' / 'libdemo.a'
    assert archive.exists()
    # 归档里应包含目标文件与符号
    listing = subprocess.run(['ar', '-t', str(archive)],
                             capture_output=True, text=True).stdout
    assert 'src_main.o' in listing
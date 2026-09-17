"""P2-2：pkg-config 集成测试。用假的 pkg-config 脚本驱动，不依赖机器上的真实包。"""

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


def make_fake_which(fake_pkg_config):
    """让 shutil.which('pkg-config') 返回假脚本，其余命令仍走真实查找"""
    real_which = shutil.which

    def patched(name, *args, **kwargs):
        if name == 'pkg-config':
            return str(fake_pkg_config)
        return real_which(name, *args, **kwargs)

    return patched


def write_fake_pkg_config(project_dir, packages):
    """生成一个假的 pkg-config：packages 形如 {'foo': ('--cflags 输出', '--libs 输出')}"""
    fake = project_dir / 'fake-pkg-config'
    cases = {name: (cflags, libs) for name, (cflags, libs) in packages.items()}
    source = ("#!/usr/bin/env python3\n"
              "import sys\n"
              "cases = " + repr(cases) + "\n"
              "if len(sys.argv) == 3 and sys.argv[1] in ('--cflags', '--libs'):\n"
              "    spec = cases.get(sys.argv[2])\n"
              "    if spec is None:\n"
              "        sys.stderr.write('Package %s was not found\\n' % sys.argv[2])\n"
              "        sys.exit(1)\n"
              "    print(spec[0] if sys.argv[1] == '--cflags' else spec[1])\n"
              "else:\n"
              "    sys.exit(1)\n")
    fake.write_text(source)
    fake.chmod(0o755)
    return fake


def test_pkg_config_injects_flags_and_links(project, monkeypatch):
    """
    端到端：项目依赖一个假的"外部库"foo（真实编译出一个 libfoo.a）——
    没有 pkg_config 字段时编不过；加上后编译与链接都注入正确参数
    """
    ext = project / 'ext'
    ext.mkdir(exist_ok=True)
    (ext / 'foo.h').write_text('#ifndef FOO_H\n#define FOO_H\nint foo_value(void);\n#endif\n')
    (ext / 'foo.c').write_text('int foo_value(void){ return 7; }\n')
    libs_dir = project / 'libs'
    libs_dir.mkdir()
    subprocess.run(['gcc', '-c', '-o', str(libs_dir / 'foo.o'), str(ext / 'foo.c')], check=True)
    subprocess.run(['ar', 'csr', str(libs_dir / 'libfoo.a'), str(libs_dir / 'foo.o')], check=True)

    (project / 'src' / 'main.c').write_text(
        '#include <stdio.h>\n'
        '#include <foo.h>\n'
        'int main(){ printf("foo=%d\\n", foo_value()); }\n')

    fake = write_fake_pkg_config(project, {'foo': (f'-I{ext}', f'-L{libs_dir} -lfoo')})
    monkeypatch.setattr('shutil.which', make_fake_which(fake))

    write_config(project, source=['src/main.c'], compile_args=['-w'], pkg_config=['foo'])

    assert antel('rebuild').exit_code == 0

    assert run_program(project) == 'foo=7'

    compile_log = (project / 'demo_antel' / 'log' / 'demo.gxx').read_text()
    assert f'-I{ext}' in compile_log

    link_script = (project / 'demo_antel' / 'log' / 'demo_link.sh').read_text()
    assert f'-L{libs_dir} -lfoo' in link_script


def test_pkg_config_missing_package_fails_loudly(project, monkeypatch):
    """包不存在时必须明确报错，而不是静默跳过"""
    fake = write_fake_pkg_config(project, {})
    monkeypatch.setattr('shutil.which', make_fake_which(fake))
    write_config(project, pkg_config=['no_such_pkg'])

    result = antel('rebuild')

    assert result.exit_code != 0
    assert 'no_such_pkg' in result.output


def test_pkg_config_requires_command(project, monkeypatch):
    """机器上没有 pkg-config 命令时配置直接报错"""
    real_which = shutil.which
    monkeypatch.setattr('shutil.which',
                        lambda name, *a, **k: None if name == 'pkg-config' else real_which(name, *a, **k))
    write_config(project, pkg_config=['foo'])

    result = antel('rebuild')

    assert result.exit_code != 0
    assert 'pkg-config' in result.output
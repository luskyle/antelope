import shutil
import subprocess

import pytest
from click.testing import CliRunner

from antelope.antelope import main
from antelope.errors import CommandError, ConfigError
from conftest import run_program, write_config


pytestmark = pytest.mark.skipif(
    shutil.which('gcc') is None or shutil.which('g++') is None
    or shutil.which('git') is None,
    reason='需要 gcc/g++ 与 git 才能执行 ref 集成测试')


def git(*args, cwd):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True,
                          text=True)


def create_ref_repo(path, name, branch, value):
    path.mkdir()
    git('init', '-q', '-b', 'main', cwd=path)
    git('config', 'user.name', 'Antelope tests', cwd=path)
    git('config', 'user.email', 'antel-tests@example.invalid', cwd=path)

    (path / 'include').mkdir()
    (path / 'src').mkdir()
    (path / 'include' / f'{name}.h').write_text(
        f'int {name}_value(void);\n')
    source = path / 'src' / f'{name}.c'
    source.write_text(f'int {name}_value(void) {{ return 0; }}\n')
    git('add', '.', cwd=path)
    git('commit', '-q', '-m', 'initial', cwd=path)
    git('checkout', '-q', '-b', branch, cwd=path)
    source.write_text(f'int {name}_value(void) {{ return {value}; }}\n')
    git('commit', '-q', '-am', f'{branch} implementation', cwd=path)


def test_refs_are_cloned_on_requested_branches_before_build(project):
    upstream_alpha = project.parent / 'upstream-alpha'
    upstream_beta = project.parent / 'upstream-beta'
    create_ref_repo(upstream_alpha, 'alpha', 'release/alpha', 21)
    create_ref_repo(upstream_beta, 'beta', 'feature-beta', 34)

    (project / 'src' / 'main.c').write_text(
        '#include <stdio.h>\n'
        '#include <alpha.h>\n'
        '#include <beta.h>\n'
        'int main(void) { printf("%d %d\\n", alpha_value(), beta_value()); }\n')

    write_config(
        project,
        source=[
            'src/main.c',
            '.antel/refs/alpha/src/alpha.c',
            '.antel/refs/beta/src/beta.c',
        ],
        include_directories=[
            'inc',
            '.antel/refs/alpha/include',
            '.antel/refs/beta/include',
        ],
        ref=[
            {'url': str(upstream_alpha), 'branch': 'release/alpha', 'name': 'alpha'},
            {'url': str(upstream_beta), 'branch': 'feature-beta', 'name': 'beta'},
        ],
    )

    result = CliRunner().invoke(main, ['rebuild'])

    assert result.exit_code == 0, result.output
    assert run_program(project) == '21 34'
    assert git('-C', '.antel/refs/alpha', 'branch', '--show-current', cwd=project).stdout.strip() == 'release/alpha'
    assert git('-C', '.antel/refs/beta', 'branch', '--show-current', cwd=project).stdout.strip() == 'feature-beta'


def test_ref_cache_rejects_changed_branch(project):
    upstream = project.parent / 'upstream'
    create_ref_repo(upstream, 'lib', 'feature', 7)

    from antelope.refs import RefManager

    cache = project / '.antel' / 'refs' / 'lib'
    cache.parent.mkdir(parents=True)
    subprocess.run(['git', 'clone', '-q', '--branch', 'main', str(upstream),
                    str(cache)], check=True)

    manager = RefManager([{'url': str(upstream), 'branch': 'feature', 'name': 'lib'}])
    with pytest.raises(ConfigError, match='配置要求 feature'):
        manager.prepare()


def test_ref_clone_failure_keeps_git_diagnostic_and_cleans_partial_checkout(project):
    upstream = project.parent / 'upstream-invalid-branch'
    create_ref_repo(upstream, 'lib', 'feature', 7)

    from antelope.refs import RefManager

    manager = RefManager([{'url': str(upstream), 'branch': 'missing', 'name': 'lib'}])
    with pytest.raises(CommandError, match='下载 ref 项目 lib 失败') as raised:
        manager.prepare()

    assert raised.value.output.strip() in str(raised.value)
    assert not (project / '.antel' / 'refs' / 'lib').exists()


def test_fetch_ref_downloads_without_initializing_build(project):
    upstream = project.parent / 'upstream-fetch-ref'
    create_ref_repo(upstream, 'lib', 'feature', 7)
    write_config(
        project,
        ref=[{'url': str(upstream), 'branch': 'feature', 'name': 'lib'}],
        pkg_config=['not-installed'],
    )
    (project / 'antel.json').rename(project / 'deps.json')

    result = CliRunner().invoke(main, ['fetch-ref', '-f', 'deps'])

    assert result.exit_code == 0, result.output
    assert (project / '.antel' / 'refs' / 'lib' / 'src' / 'lib.c').exists()
    assert not (project / 'demo_deps').exists()
    assert '编译' not in result.output
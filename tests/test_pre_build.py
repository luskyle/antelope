from click.testing import CliRunner

from antelope.antelope import main
from conftest import run_program, write_config


def test_before_build_generates_source_before_compile_and_tracks_output(project):
    (project / 'prepare.py').write_text(
        'from pathlib import Path\n'
        'value = Path("generated-value.txt").read_text().strip()\n'
        'Path("src/generated.c").write_text(' 
        '"int generated_value(void) { return " + value + "; }\\n")\n')
    (project / 'generated-value.txt').write_text('41')
    (project / 'src' / 'main.c').write_text(
        '#include <stdio.h>\n'
        'int generated_value(void);\n'
        'int main(void) { printf("%d\\n", generated_value()); }\n')
    write_config(
        project,
        source=['src/main.c', 'src/generated.c'],
        include_directories=[],
        before_build=[{
            'command': ['python3', 'prepare.py'],
            'outputs': ['src/generated.c'],
        }],
    )

    result = CliRunner().invoke(main, ['rebuild'])

    assert result.exit_code == 0, result.output
    assert run_program(project) == '41'

    (project / 'generated-value.txt').write_text('42')
    result = CliRunner().invoke(main, ['build'])

    assert result.exit_code == 0, result.output
    assert run_program(project) == '42'


def test_before_build_output_change_triggers_relink(project):
    (project / 'src' / 'library.c').write_text('int library_value(void) { return 7; }\n')
    (project / 'prepare.py').write_text(
        'from pathlib import Path\n'
        'version = Path("map-version.txt").read_text().strip()\n'
        'Path(".antel/build/version.map").parent.mkdir(parents=True, exist_ok=True)\n'
        'Path(".antel/build/version.map").write_text('
        'version + " { global: library_value; local: *; };\\n")\n')
    (project / 'map-version.txt').write_text('VERSION_1')
    write_config(
        project,
        target_type='shared',
        source=['src/library.c'],
        include_directories=[],
        compile_args=['-fPIC'],
        link_args=['-Wl,--version-script=.antel/build/version.map'],
        before_build=[{
            'command': ['python3', 'prepare.py'],
            'outputs': ['.antel/build/version.map'],
        }],
    )

    result = CliRunner().invoke(main, ['rebuild'])

    assert result.exit_code == 0, result.output
    artifact = project / '.antel' / 'build' / 'demo_antel' / 'libdemo.so'
    before = artifact.read_bytes()

    (project / 'map-version.txt').write_text('VERSION_2')
    result = CliRunner().invoke(main, ['build'])

    assert result.exit_code == 0, result.output
    assert artifact.read_bytes() != before


def test_before_build_command_must_be_an_argv_array(project):
    write_config(project, before_build=[{'command': 'python3 prepare.py'}])

    result = CliRunner().invoke(main, ['rebuild'])

    assert result.exit_code != 0
    assert 'before_build[0].command' in result.output


def test_before_build_requires_declared_outputs(project):
    write_config(project, before_build=[{
        'command': ['python3', '-c', 'pass'],
        'outputs': ['generated/missing.h'],
    }])

    result = CliRunner().invoke(main, ['rebuild'])

    assert result.exit_code != 0
    assert 'before_build 命令未生成声明的文件' in result.output


def test_pre_build_name_reports_rename(project):
    write_config(project, pre_build=[{'command': ['python3', '-c', 'pass']}])

    result = CliRunner().invoke(main, ['rebuild'])

    assert result.exit_code != 0
    assert 'pre_build 已更名为 before_build' in result.output


def test_after_build_commands_run_in_order_after_build_and_noop(project):
    (project / 'after_one.py').write_text(
        'from pathlib import Path\n'
        'Path("after-order.txt").write_text("one")\n')
    (project / 'after_two.py').write_text(
        'from pathlib import Path\n'
        'path = Path("after-order.txt")\n'
        'path.write_text(path.read_text() + " two")\n')
    write_config(project, after_build=[
        {'command': ['python3', 'after_one.py']},
        {'command': ['python3', 'after_two.py']},
    ])

    result = CliRunner().invoke(main, ['rebuild'])

    assert result.exit_code == 0, result.output
    assert (project / 'after-order.txt').read_text() == 'one two'

    (project / 'after-order.txt').unlink()
    result = CliRunner().invoke(main, ['build'])

    assert result.exit_code == 0, result.output
    assert (project / 'after-order.txt').read_text() == 'one two'


def test_after_build_failure_returns_nonzero(project):
    write_config(project, after_build=[{'command': ['python3', '-c', 'raise SystemExit(7)']}])

    result = CliRunner().invoke(main, ['rebuild'])

    assert result.exit_code != 0
    assert 'python3 -c' in result.output
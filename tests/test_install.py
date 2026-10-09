import json
import os
import shutil

from click.testing import CliRunner
import pytest

from antelope.antelope import main


def configure_install(project, **overrides):
    config = {'install_path': str(project / 'installed'), 'projectName': 'bundle'}
    config.update(overrides)
    (project / 'install.json').write_text(json.dumps(config))
    return project / 'installed' / 'bundle'


def make_artifact(project, filename, name, kind, artifact, **overrides):
    config = {'projectName': name, 'target_type': kind}
    config.update(overrides)
    (project / f'{filename}.json').write_text(json.dumps(config))
    output = project / '.antel' / 'build' / f'{name}_{filename}'
    output.mkdir(parents=True)
    target = output / artifact
    target.write_bytes(b'build result')
    return target


def test_install_all_targets_and_preserve_links_and_permissions(project):
    prefix = configure_install(project)
    executable = make_artifact(project, 'release', 'viewer', 'exe', 'viewer')
    executable.chmod(0o755)
    make_artifact(project, 'static', 'demo', 'static', 'libdemo.a')
    library = make_artifact(project, 'shared', 'demo', 'shared',
                            'libdemo.so.1.2', version='1.2')
    (library.parent / 'libdemo.so').symlink_to(library.name)
    (library.parent / 'libdemo.so.1').symlink_to(library.name)
    (library.parent / 'obj').mkdir()
    (library.parent / 'obj' / 'intermediate.o').write_text('not installed')

    result = CliRunner().invoke(main, ['install'])

    assert result.exit_code == 0, result.output
    assert (prefix / 'bin/viewer').read_bytes() == executable.read_bytes()
    assert (prefix / 'bin/viewer').stat().st_mode & 0o777 == 0o755
    assert (prefix / 'lib/libdemo.a').is_file()
    assert (prefix / 'lib/libdemo.so.1.2').is_file()
    assert os.readlink(prefix / 'lib/libdemo.so') == 'libdemo.so.1.2'
    assert os.readlink(prefix / 'lib/libdemo.so.1') == 'libdemo.so.1.2'
    assert not (prefix / 'lib/obj').exists()
    assert not (prefix / 'bin/demo').exists()
    assert not (prefix.parent / 'bin').exists()
    assert not (prefix.parent / 'lib').exists()
    assert not (prefix.parent / 'share').exists()


@pytest.mark.parametrize('selected', ['viewer', ['viewer']])
def test_install_selects_projects(project, selected):
    prefix = configure_install(project, projects=selected)
    make_artifact(project, 'release', 'viewer', 'exe', 'viewer')
    make_artifact(project, 'static', 'library', 'static', 'liblibrary.a')

    result = CliRunner().invoke(main, ['install'])

    assert result.exit_code == 0, result.output
    assert (prefix / 'bin/viewer').exists()
    assert not (prefix / 'lib').exists()


def test_install_rejects_conflicting_targets_before_copying(project):
    prefix = configure_install(project)
    make_artifact(project, 'release', 'viewer', 'exe', 'viewer')
    make_artifact(project, 'debug', 'viewer', 'exe', 'viewer')

    result = CliRunner().invoke(main, ['install'])

    assert result.exit_code != 0
    assert '安装目标冲突' in result.output
    assert not prefix.exists()


@pytest.mark.parametrize('config', [[], {}, {'install_path': 123},
                                   {'install_path': 'installed', 'projectName': []}])
def test_install_rejects_invalid_config(project, config):
    (project / 'install.json').write_text(json.dumps(config))
    result = CliRunner().invoke(main, ['install'])
    assert result.exit_code != 0


def test_install_missing_config(project):
    result = CliRunner().invoke(main, ['install'])
    assert result.exit_code != 0
    assert 'install.json' in result.output


def test_install_missing_selected_target_does_not_copy(project):
    prefix = configure_install(project, projects=['viewer', 'missing'])
    make_artifact(project, 'release', 'viewer', 'exe', 'viewer')
    result = CliRunner().invoke(main, ['install'])
    assert result.exit_code != 0
    assert 'missing' in result.output
    assert not prefix.exists()


def test_install_permission_error_is_reported(project, monkeypatch):
    configure_install(project)
    make_artifact(project, 'release', 'viewer', 'exe', 'viewer')

    def deny_copy(*args, **kwargs):
        raise PermissionError('denied')

    monkeypatch.setattr('antelope.installer.shutil.copy2', deny_copy)
    result = CliRunner().invoke(main, ['install'])
    assert result.exit_code != 0
    assert '写入权限' in result.output


def test_install_deployed_resources_and_repeat_install(project):
    prefix = configure_install(project)
    target = make_artifact(project, 'release', 'viewer', 'exe', 'viewer',
                           data_files=[{'from': 'logo.png', 'to': 'assets/logo.png'},
                                       {'from': 'images', 'to': 'images'}])
    (target.parent / 'assets').mkdir()
    (target.parent / 'assets/logo.png').write_bytes(b'logo')
    (target.parent / 'images').mkdir()
    (target.parent / 'images/sample.png').write_bytes(b'image')

    for iteration in range(2):
        result = CliRunner().invoke(main, ['install'])
        assert result.exit_code == 0, result.output
    assert (prefix / 'share/viewer_release/assets/logo.png').read_bytes() == b'logo'
    assert (prefix / 'share/viewer_release/images/sample.png').read_bytes() == b'image'


def test_install_rejects_resource_path_escape(project):
    prefix = configure_install(project)
    make_artifact(project, 'release', 'viewer', 'exe', 'viewer',
                   data_files=[{'from': 'logo.png', 'to': '../outside.png'}])
    result = CliRunner().invoke(main, ['install'])
    assert result.exit_code != 0
    assert '构建目录内' in result.output
    assert not prefix.exists()


@pytest.mark.parametrize('name', ['..', '.', '../bin', '/usr/local/bin', ['viewer']])
def test_install_rejects_invalid_package_directory(project, name):
    configure_install(project, projectName=name)
    result = CliRunner().invoke(main, ['install'])
    assert result.exit_code != 0
    assert '独立安装目录名' in result.output


def test_install_does_not_use_existing_unmanaged_directory(project):
    prefix = configure_install(project)
    prefix.mkdir(parents=True)
    (prefix / 'existing.txt').write_text('keep')
    make_artifact(project, 'release', 'viewer', 'exe', 'viewer')
    result = CliRunner().invoke(main, ['install'])
    assert result.exit_code != 0
    assert '不是 Antel 安装目录' in result.output
    assert (prefix / 'existing.txt').read_text() == 'keep'
    assert not (prefix / 'bin').exists()


def test_install_rejects_package_directory_symlink(project):
    prefix = configure_install(project)
    prefix.parent.mkdir()
    external = project / 'external'
    external.mkdir()
    prefix.symlink_to(external, target_is_directory=True)
    result = CliRunner().invoke(main, ['install'])
    assert result.exit_code != 0
    assert '符号链接' in result.output
    assert list(external.iterdir()) == []


def test_install_rejects_subdirectory_symlink_escape(project):
    prefix = configure_install(project)
    prefix.mkdir(parents=True)
    (prefix / '.antel-install').touch()
    external = project / 'external'
    external.mkdir()
    (prefix / 'bin').symlink_to(external, target_is_directory=True)
    make_artifact(project, 'release', 'viewer', 'exe', 'viewer')
    result = CliRunner().invoke(main, ['install'])
    assert result.exit_code != 0
    assert '越出独立安装目录' in result.output
    assert list(external.iterdir()) == []


def test_uninstall_uses_manifest_without_build_outputs(project):
    prefix = configure_install(project)
    target = make_artifact(project, 'release', 'viewer', 'exe', 'viewer')
    library = make_artifact(project, 'shared', 'demo', 'shared',
                            'libdemo.so.1.2', version='1.2')
    (library.parent / 'libdemo.so').symlink_to(library.name)
    assert CliRunner().invoke(main, ['install']).exit_code == 0
    target.unlink()
    library.unlink()
    (project / 'release.json').unlink()
    (project / 'shared.json').unlink()

    result = CliRunner().invoke(main, ['uninstall'])

    assert result.exit_code == 0, result.output
    assert not prefix.exists()
    assert prefix.parent.exists()
    assert CliRunner().invoke(main, ['uninstall']).exit_code == 0


def test_uninstall_preserves_user_files(project):
    prefix = configure_install(project)
    make_artifact(project, 'release', 'viewer', 'exe', 'viewer')
    assert CliRunner().invoke(main, ['install']).exit_code == 0
    (prefix / 'notes.txt').write_text('keep')
    (prefix / 'bin/custom').write_text('keep')

    result = CliRunner().invoke(main, ['uninstall'])

    assert result.exit_code == 0, result.output
    assert (prefix / 'notes.txt').read_text() == 'keep'
    assert (prefix / 'bin/custom').read_text() == 'keep'
    assert not (prefix / 'bin/viewer').exists()
    assert CliRunner().invoke(main, ['uninstall']).exit_code == 0
    assert CliRunner().invoke(main, ['install']).exit_code == 0
    assert (prefix / 'bin/viewer').is_file()
    assert (prefix / 'bin/custom').read_text() == 'keep'


def test_uninstall_selects_projects_from_install_config(project):
    prefix = configure_install(project)
    make_artifact(project, 'release', 'viewer', 'exe', 'viewer')
    make_artifact(project, 'static', 'demo', 'static', 'libdemo.a')
    assert CliRunner().invoke(main, ['install']).exit_code == 0
    configure_install(project, projects=['viewer'])

    result = CliRunner().invoke(main, ['uninstall'])

    assert result.exit_code == 0, result.output
    assert not (prefix / 'bin/viewer').exists()
    assert (prefix / 'lib/libdemo.a').is_file()
    configure_install(project)
    assert CliRunner().invoke(main, ['uninstall']).exit_code == 0
    assert not prefix.exists()


def test_uninstall_requires_legacy_marker_upgrade(project):
    prefix = configure_install(project)
    prefix.mkdir(parents=True)
    (prefix / '.antel-install').touch()
    (prefix / 'notes.txt').write_text('keep')

    result = CliRunner().invoke(main, ['uninstall'])

    assert result.exit_code != 0
    assert '先使用 antel install' in result.output
    assert (prefix / 'notes.txt').read_text() == 'keep'


def test_uninstall_rejects_manifest_path_escape(project):
    prefix = configure_install(project)
    prefix.mkdir(parents=True)
    (prefix / '.antel-install').write_text(json.dumps({
        'version': 1, 'files': {'../outside': 'viewer'}}))
    external = prefix.parent / 'outside'
    external.write_text('keep')
    result = CliRunner().invoke(main, ['uninstall'])
    assert result.exit_code != 0
    assert external.read_text() == 'keep'


def test_uninstall_rejects_parent_symlink_escape(project):
    prefix = configure_install(project)
    make_artifact(project, 'release', 'viewer', 'exe', 'viewer')
    assert CliRunner().invoke(main, ['install']).exit_code == 0
    (prefix / 'bin/viewer').unlink()
    (prefix / 'bin').rmdir()
    external = project / 'external'
    external.mkdir()
    (external / 'viewer').write_text('keep')
    (prefix / 'bin').symlink_to(external, target_is_directory=True)
    result = CliRunner().invoke(main, ['uninstall'])
    assert result.exit_code != 0
    assert (external / 'viewer').read_text() == 'keep'


def test_uninstall_permission_error_retains_manifest(project, monkeypatch):
    prefix = configure_install(project)
    make_artifact(project, 'release', 'viewer', 'exe', 'viewer')
    assert CliRunner().invoke(main, ['install']).exit_code == 0
    original_unlink = type(prefix).unlink

    def deny_unlink(path, *args, **kwargs):
        if path == prefix / 'bin/viewer':
            raise PermissionError('denied')
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(type(prefix), 'unlink', deny_unlink)
    result = CliRunner().invoke(main, ['uninstall'])
    assert result.exit_code != 0
    assert '写入权限' in result.output
    assert (prefix / 'bin/viewer').is_file()
    manifest = json.loads((prefix / '.antel-install').read_text())
    assert manifest['files']['bin/viewer'] == 'viewer'


def prepare_legacy_install(project):
    package = configure_install(project)
    target = make_artifact(project, 'release', 'viewer', 'exe', 'viewer')
    library = make_artifact(project, 'shared', 'demo', 'shared',
                            'libdemo.so.1.2', version='1.2')
    (library.parent / 'libdemo.so').symlink_to(library.name)
    prefix = package.parent
    (prefix / 'bin').mkdir(parents=True)
    (prefix / 'lib').mkdir()
    (prefix / 'share').mkdir()
    shutil.copy2(target, prefix / 'bin/viewer')
    shutil.copy2(library, prefix / 'lib/libdemo.so.1.2')
    (prefix / 'lib/libdemo.so').symlink_to(library.name)
    return prefix


def test_legacy_uninstall_preview_and_cleanup_preserve_system_directories(project):
    prefix = prepare_legacy_install(project)
    (prefix / 'bin/unrelated').write_text('keep')
    result = CliRunner().invoke(main, ['uninstall', '--legacy-system', '--dry-run'])
    assert result.exit_code == 0, result.output
    assert '共 3 个匹配' in result.output
    assert (prefix / 'bin/viewer').exists()
    result = CliRunner().invoke(main, ['uninstall', '--legacy-system'])
    assert result.exit_code == 0, result.output
    assert not (prefix / 'bin/viewer').exists()
    assert not os.path.lexists(prefix / 'lib/libdemo.so')
    assert not (prefix / 'lib/libdemo.so.1.2').exists()
    assert (prefix / 'bin/unrelated').read_text() == 'keep'
    assert all((prefix / name).is_dir() for name in ['bin', 'lib', 'share'])
    assert CliRunner().invoke(main, ['uninstall', '--legacy-system']).exit_code == 0


def test_legacy_uninstall_mismatch_prevents_all_deletion(project):
    prefix = prepare_legacy_install(project)
    (prefix / 'bin/viewer').write_text('different installation')
    result = CliRunner().invoke(main, ['uninstall', '--legacy-system'])
    assert result.exit_code != 0
    assert '未删除任何文件' in result.output
    assert (prefix / 'bin/viewer').read_text() == 'different installation'
    assert (prefix / 'lib/libdemo.so.1.2').exists()


def test_legacy_uninstall_resource_cleanup_keeps_unrelated_files(project):
    prefix = prepare_legacy_install(project)
    config = json.loads((project / 'release.json').read_text())
    config['data_files'] = [{'from': 'logo.png', 'to': 'assets/logo.png'}]
    (project / 'release.json').write_text(json.dumps(config))
    resource = project / '.antel' / 'build' / 'viewer_release' / 'assets/logo.png'
    resource.parent.mkdir()
    resource.write_bytes(b'logo')
    installed = prefix / 'share/viewer_release/assets/logo.png'
    installed.parent.mkdir(parents=True)
    shutil.copy2(resource, installed)
    (installed.parent / 'user-note').write_text('keep')
    result = CliRunner().invoke(main, ['uninstall', '--legacy-system'])
    assert result.exit_code == 0, result.output
    assert not installed.exists()
    assert (installed.parent / 'user-note').read_text() == 'keep'


def test_legacy_uninstall_rejects_directory_symlink_escape(project):
    prefix = prepare_legacy_install(project)
    (prefix / 'bin/viewer').unlink()
    (prefix / 'bin').rmdir()
    external = project / 'external'
    external.mkdir()
    (external / 'viewer').write_bytes(b'build result')
    (prefix / 'bin').symlink_to(external, target_is_directory=True)
    result = CliRunner().invoke(main, ['uninstall', '--legacy-system'])
    assert result.exit_code != 0
    assert (external / 'viewer').exists()
    assert (prefix / 'lib/libdemo.so.1.2').exists()


def test_legacy_uninstall_does_not_touch_separate_package_directory(project):
    prefix = prepare_legacy_install(project)
    package = prefix / 'bundle'
    package.mkdir()
    (package / 'notes.txt').write_text('keep')
    result = CliRunner().invoke(main, ['uninstall', '--legacy-system'])
    assert result.exit_code == 0, result.output
    assert (package / 'notes.txt').read_text() == 'keep'
    assert not (prefix / 'bin/viewer').exists()
import filecmp
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

import click

from antelope.errors import ConfigError, BuildError
from antelope.resources import readDataFiles


def load_install_json(path):
    try:
        with path.open(encoding='utf-8') as stream:
            config = json.load(stream)
    except (OSError, ValueError) as error:
        raise ConfigError(f'无法读取 {path.name}: {error}') from error
    if not isinstance(config, dict):
        raise ConfigError(f'{path.name} 必须是 JSON 对象')
    return config


def load_install_settings(validate_directory=True):
    directory = Path.cwd()
    config = load_install_json(directory / 'install.json')
    prefix = config.get('install_path')
    if not isinstance(prefix, str) or not prefix.strip():
        raise ConfigError('install_path 必须是非空路径字符串')
    parent = Path(prefix).expanduser().absolute()
    package = config.get('projectName')
    if (not isinstance(package, str) or package in ('.', '..') or
            re.fullmatch(r'[A-Za-z0-9_.-]+', package) is None):
        raise ConfigError('projectName 必须是独立安装目录名，只能包含字母、数字、下划线、点和连字符')
    prefix = parent / package
    if validate_directory and prefix.is_symlink():
        raise ConfigError(f'安装目录不能是符号链接：{prefix}')
    marker = prefix / '.antel-install'
    if validate_directory and (marker.is_symlink() or (prefix.exists() and not marker.is_file())):
        raise ConfigError(f'安装目录已存在且不是 Antel 安装目录：{prefix}')
    selected = config.get('projects')
    if isinstance(selected, str):
        selected = [selected]
    if selected is not None and (
            not isinstance(selected, list) or not selected or
            any(not isinstance(name, str) or
                re.fullmatch(r'[A-Za-z0-9_.-]+', name) is None for name in selected)):
        raise ConfigError('projects 必须是项目名字符串或非空项目名数组')
    return prefix, marker, selected


def read_install_manifest(marker):
    if not marker.exists() or marker.stat().st_size == 0:
        return {}
    manifest = load_install_json(marker)
    files = manifest.get('files')
    if manifest.get('version') != 1 or not isinstance(files, dict):
        raise ConfigError('安装清单格式非法')
    for filename, project in files.items():
        relative = Path(filename)
        if (relative.is_absolute() or relative.as_posix() != filename or '..' in relative.parts or
                len(relative.parts) < 2 or relative.parts[0] not in ('bin', 'lib', 'share') or
                not isinstance(project, str) or
                re.fullmatch(r'[A-Za-z0-9_.-]+', project) is None):
            raise ConfigError(f'安装清单记录非法：{filename}')
    return files


def save_install_manifest(marker, files):
    descriptor, temporary = tempfile.mkstemp(prefix='.antel-manifest-', dir=marker.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump({'version': 1, 'files': files}, stream, indent=2)
        os.replace(temporary, marker)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


def collect_install_plan(prefix, selected):
    directory = Path.cwd()
    plan = {}
    owners = {}
    found = set()
    for path in sorted(directory.glob('*.json')):
        if path.name == 'install.json':
            continue
        build = load_install_json(path)
        name = build.get('projectName')
        kind = str(build.get('target_type', '')).lower()
        if kind not in ('static', 'shared', 'exe'):
            continue
        if selected is not None and name not in selected:
            continue
        if not isinstance(name, str) or re.fullmatch(r'[A-Za-z0-9_.-]+', name) is None:
            raise ConfigError(f'{path.name}: projectName 非法')
        output = directory / f'{name}_{path.stem}'
        if kind == 'exe':
            filename = name
        elif kind == 'static':
            filename = f'lib{name}.a'
        else:
            version = build.get('version', '')
            filename = f'lib{name}.so' + (f'.{version}' if version else '')
        if Path(filename).name != filename or filename in ('.', '..'):
            raise ConfigError(f'{path.name}: 生成目标文件名非法')
        artifact = output / filename
        if not artifact.is_file():
            continue
        if artifact.is_symlink():
            raise ConfigError(f'生成目标必须是普通文件：{artifact}')
        found.add(name)
        targets = [artifact]
        if kind == 'shared':
            targets += [entry for entry in sorted(output.iterdir())
                        if entry.is_symlink() and entry.resolve() == artifact.resolve()]
        for source in targets:
            destination = prefix / ('bin' if kind == 'exe' else 'lib') / source.name
            if destination in plan:
                raise ConfigError(f'安装目标冲突：{plan[destination]} 与 {source} -> {destination}')
            if source.is_symlink() and os.readlink(source) != artifact.name:
                raise ConfigError(f'共享库符号链接必须指向同目录生成目标：{source}')
            if source.resolve() == destination.resolve():
                raise ConfigError(f'安装路径与生成目标相同：{destination}')
            plan[destination] = source
            owners[destination] = name
        for entry in readDataFiles(build):
            relative = Path(entry['to'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ConfigError(f'data_files 安装路径必须位于构建目录内：{relative}')
            resource = output / relative
            if not resource.exists():
                raise ConfigError(f'构建后的资源缺失：{resource}')
            resources = sorted(resource.rglob('*')) if resource.is_dir() else [resource]
            for source in resources:
                if source.is_symlink() or output.resolve() not in source.resolve().parents:
                    raise ConfigError(f'安装资源不能包含符号链接或目录外文件：{source}')
                if not source.is_file():
                    continue
                destination = prefix / 'share' / output.name / source.relative_to(output)
                if destination in plan and plan[destination] != source:
                    raise ConfigError(f'资源安装目标冲突：{destination}')
                if source.resolve() == destination.resolve():
                    raise ConfigError(f'安装路径与资源相同：{destination}')
                plan[destination] = source
                owners[destination] = name
    if selected is not None and set(selected) - found:
        raise ConfigError('没有找到已构建项目：' + ', '.join(sorted(set(selected) - found)))
    if not plan:
        raise ConfigError('当前目录没有已构建的生成目标，请先运行 antel build/rebuild')
    for destination in plan:
        if prefix.resolve() not in destination.resolve().parents:
            raise ConfigError(f'安装目标不能通过符号链接越出独立安装目录：{destination}')
    return plan, owners


def install_targets():
    directory = Path.cwd()
    prefix, marker, selected = load_install_settings()
    installed = read_install_manifest(marker)
    plan, owners = collect_install_plan(prefix, selected)

    try:
        prefix.mkdir(parents=True, exist_ok=True)
        marker.touch()
        for destination, source in plan.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix='.antel-install-', dir=destination.parent)
            os.close(descriptor)
            try:
                if source.is_symlink():
                    os.unlink(temporary)
                    os.symlink(os.readlink(source), temporary)
                else:
                    shutil.copy2(source, temporary)
                os.replace(temporary, destination)
                installed[destination.relative_to(prefix).as_posix()] = owners[destination]
                save_install_manifest(marker, installed)
            finally:
                if os.path.lexists(temporary):
                    os.unlink(temporary)
            click.echo(f'安装：{source.relative_to(directory)} -> {destination}')
    except OSError as error:
        raise BuildError(f'安装失败：{error}；请确认目标目录写入权限') from error
    click.echo(f'install finished! 已安装 {len(plan)} 个文件/链接到 {prefix}')


def uninstall_targets():
    prefix, marker, selected = load_install_settings()
    if not prefix.exists():
        click.echo(f'没有已安装目录，无需卸载：{prefix}')
        return
    installed = read_install_manifest(marker)
    if marker.stat().st_size == 0:
        raise ConfigError('缺少安装清单，请先使用 antel install 更新安装记录')
    targets = {filename: prefix / filename for filename, project in installed.items()
               if selected is None or project in selected}
    for destination in targets.values():
        parent = destination.parent.resolve()
        if prefix.resolve() != parent and prefix.resolve() not in parent.parents:
            raise ConfigError(f'卸载目标不能通过符号链接越出独立安装目录：{destination}')
        if destination.exists() and destination.is_dir() and not destination.is_symlink():
            raise ConfigError(f'卸载目标已被替换为目录，拒绝删除：{destination}')
    try:
        directories = set()
        for filename, destination in targets.items():
            if os.path.lexists(destination):
                destination.unlink()
                click.echo(f'卸载：{destination}')
            del installed[filename]
            save_install_manifest(marker, installed)
            directories.update(parent for parent in destination.parents
                               if prefix in parent.parents)
        for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
            if directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()):
                directory.rmdir()
        if not installed:
            if not any(entry != marker for entry in prefix.iterdir()):
                marker.unlink()
                prefix.rmdir()
            else:
                click.echo(f'保留用户文件及目录：{prefix}')
    except OSError as error:
        raise BuildError(f'卸载失败：{error}；请确认目标目录写入权限') from error
    click.echo(f'uninstall finished! 已移除 {len(targets)} 个安装记录')


def uninstall_legacy_system(dry_run=False):
    package, marker, selected = load_install_settings(validate_directory=False)
    prefix = package.parent
    plan, owners = collect_install_plan(prefix, selected)
    targets = []
    mismatches = []
    try:
        for destination, source in plan.items():
            if not os.path.lexists(destination):
                continue
            if source.is_symlink():
                matches = destination.is_symlink() and os.readlink(destination) == os.readlink(source)
            else:
                matches = (not destination.is_symlink() and destination.is_file()
                           and filecmp.cmp(source, destination, shallow=False))
            if not matches:
                mismatches.append(str(destination))
            else:
                targets.append(destination)
        for destination in targets:
            click.echo(f'旧版卸载候选：{destination}')
        if mismatches:
            raise ConfigError('旧版文件与当前构建产物不一致，未删除任何文件：\n' + '\n'.join(mismatches))
        if dry_run:
            click.echo(f'dry-run: 共 {len(targets)} 个匹配文件/链接，不执行删除')
            return
        directories = set()
        for destination in targets:
            destination.unlink()
            click.echo(f'旧版卸载：{destination}')
            relative = destination.relative_to(prefix)
            if relative.parts[0] == 'share':
                resource_root = prefix / 'share' / relative.parts[1]
                directories.update(parent for parent in destination.parents
                                   if parent == resource_root or resource_root in parent.parents)
        for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
            if directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()):
                directory.rmdir()
    except OSError as error:
        raise BuildError(f'旧版卸载失败：{error}；请确认目标目录写入权限') from error
    click.echo(f'legacy uninstall finished! 已移除 {len(targets)} 个文件/链接；保留系统目录')
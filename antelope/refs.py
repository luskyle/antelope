import os
import re
import shutil

from antelope.errors import CommandError, ConfigError
from antelope.os_ops.command import Command


REF_ROOT = '.antel/refs'
REF_NAME_PATTERN = re.compile(r'[A-Za-z0-9_.-]+')


def readRefs(config:dict):
    """Read and validate Git project references from antel.json."""
    value = config.get('ref', [])
    if not isinstance(value, list):
        raise ConfigError(f'ref 必须是数组，当前为 {type(value).__name__}: {value}')

    refs = []
    names = set()
    for item in value:
        if not isinstance(item, dict):
            raise ConfigError(f'ref 的每一项必须是对象，当前为：{item}')

        url = item.get('url')
        if not isinstance(url, str) or url.strip() == '':
            raise ConfigError(f'ref.url 必须是非空字符串，当前为：{url}')

        branch = item.get('branch', '')
        if not isinstance(branch, str):
            raise ConfigError(f'ref.branch 必须是字符串，当前为：{branch}')
        branch = branch.strip()
        if branch.startswith('-') or '\n' in branch or '\r' in branch:
            raise ConfigError(f'ref.branch 不是有效分支名：{branch}')

        default_name = url.rstrip('/').rsplit('/', 1)[-1].rsplit(':', 1)[-1]
        if default_name.endswith('.git'):
            default_name = default_name[:-4]
        name = item.get('name', default_name)
        if not isinstance(name, str):
            raise ConfigError(f'ref.name 必须是字符串，当前为：{name}')
        name = name.strip()
        if (name in ('', '.', '..')
                or REF_NAME_PATTERN.fullmatch(name) is None):
            raise ConfigError(f'ref.name 只能包含字母、数字、下划线、点与连字符，当前为：{name}')
        if name in names:
            raise ConfigError(f'ref.name 重复：{name}')

        refs.append({'url': url.strip(), 'branch': branch, 'name': name})
        names.add(name)

    return refs


class RefManager:
    """Populate stable, tool-managed shallow clones before source scanning."""

    def __init__(self, refs:list):
        self.refs = list(refs)
        self.command = Command()

    def prepare(self):
        if len(self.refs) == 0:
            return
        if shutil.which('git') is None:
            raise ConfigError('配置了 ref，但当前机器上没有 git 命令')

        for ref in self.refs:
            self.prepareOne(ref)

    def prepareOne(self, ref:dict):
        path = f'{REF_ROOT}/{ref["name"]}'
        if os.path.exists(path):
            self.validateExisting(ref, path)
            print(f'引用项目已就绪：{ref["name"]}（{path}）')
            return

        os.makedirs(REF_ROOT, exist_ok=True)
        print(f'正在下载引用项目：{ref["name"]}（{ref["url"]}）')
        argv = ['git', 'clone', '--depth', '1', '--quiet']
        if ref['branch'] != '':
            argv += ['--branch', ref['branch']]
        argv += ['--', ref['url'], path]
        try:
            self.command.run_argv(argv, capture=True)
        except CommandError as error:
            shutil.rmtree(path, ignore_errors=True)
            detail = error.output.strip()
            reason = f'下载 ref 项目 {ref["name"]} 失败'
            if detail != '':
                reason += f'：{detail}'
            raise CommandError(error.command, error.return_code, error.output,
                               reason=reason) from error

        print(f'引用项目已下载：{ref["name"]}（{path}）')

    def validateExisting(self, ref:dict, path:str):
        if not os.path.isdir(os.path.join(path, '.git')):
            raise ConfigError(f'ref 目标目录已存在但不是 Git 仓库：{path}')

        origin = self.command.run_argv(
            ['git', '-C', path, 'remote', 'get-url', 'origin'], capture=True).strip()
        if origin != ref['url']:
            raise ConfigError(
                f'ref {ref["name"]} 的缓存来源不匹配：{origin}；配置要求 {ref["url"]}。'
                f'如需重新下载，请删除 {path}')

        if ref['branch'] != '':
            branch = self.command.run_argv(
                ['git', '-C', path, 'branch', '--show-current'], capture=True).strip()
            if branch != ref['branch']:
                raise ConfigError(
                    f'ref {ref["name"]} 当前分支为 {branch}，配置要求 {ref["branch"]}。'
                    f'如需重新下载，请删除 {path}')
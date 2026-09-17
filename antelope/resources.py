"""运行资源打包：data_files（复制）、gresource（GLib 资源嵌入）、embed（任意二进制嵌入）。

三种形态（对应配置字段同名的三种用法）：

- `data_files`: 把资源复制到输出目录，程序按相对路径读。适合可替换、体积大的资源。
- `gresource`: 用 glib-compile-resources 把资源编译成 C 源码再编译进程序（单文件分发），
  程序用 GResource API 按前缀路径读取。
- `embed`: 用 `ld -r -b binary` 把任意文件嵌成 .o 再参与链接（单文件分发），
  程序用 `_binary_<路径转下划线>_start/_end` 符号访问。

生成物（gresource.c、embed 的 .o）都落在输出目录内，由 `antel clean` 一并回收。
"""

import os
import re
import shutil
import xml.etree.ElementTree as ET

from antelope.errors import ConfigError
from antelope.os_ops.command import Command


def readDataFiles(config:dict):
    """读取 data_files：字符串（from==to）或对象 {from, to}，均在项目目录下相对解析"""
    value = config.get('data_files', [])
    if not isinstance(value, list):
        raise ConfigError(f'data_files 必须是数组，当前为 {type(value).__name__}: {value}')

    entries = []
    for item in value:
        if isinstance(item, str):
            entries.append({'from': item, 'to': item})
        elif isinstance(item, dict) and 'from' in item and 'to' in item:
            entries.append({'from': str(item['from']), 'to': str(item['to'])})
        else:
            raise ConfigError(f'data_files 的每一项必须是字符串或 {{"from": 源, "to": 目标}}，当前为：{item}')
    return entries


def readGresource(config:dict):
    """读取 gresource：.gresource.xml 文件路径（prefix 由 xml 内的 <gresource prefix> 决定）"""
    value = config.get('gresource', '')
    if value == '':
        return ''
    if not isinstance(value, str):
        raise ConfigError(f'gresource 必须是 .gresource.xml 的文件路径，当前为 {type(value).__name__}: {value}')
    return value


def readEmbeds(config:dict):
    """读取 embed：需要嵌入二进制的文件路径数组"""
    value = config.get('embed', [])
    if not isinstance(value, list):
        raise ConfigError(f'embed 必须是数组，当前为 {type(value).__name__}: {value}')
    return [str(item) for item in value]


def symbolName(path:str):
    """ld -r -b binary 生成的符号名：路径中非字母数字字符全部换成下划线"""
    return '_binary_' + re.sub(r'[^a-zA-Z0-9]', '_', path)


class ResourceManager:
    """资源部署的单一入口：解析、校验、部署、跟踪、生成源/目标清单"""

    def __init__(self, data_files:list=[], gresource:str='', embeds:list=[], output_dir:str='.'):
        self.data_files = list(data_files)
        self.gresource = gresource
        self.embeds = list(embeds)
        self.output_dir = output_dir
        self.command = Command()

        self.validate()

    def validate(self):
        """配置校验：路径必须存在，工具必须可用。缺了什么直接报错，不静默跳过"""
        for entry in self.data_files:
            if not os.path.exists(entry['from']):
                raise ConfigError(f'data_files 源不存在：{entry["from"]}')

        if self.gresource != '':
            if not os.path.exists(self.gresource):
                raise ConfigError(f'gresource 的 xml 不存在：{self.gresource}')
            if shutil.which('glib-compile-resources') is None:
                raise ConfigError('配置了 gresource，但机器上没有 glib-compile-resources 命令')

        for embed in self.embeds:
            if not os.path.exists(embed):
                raise ConfigError(f'embed 文件不存在：{embed}')

    # ---- 部署 ----

    def deploy(self):
        """幂等部署全部资源：复制 data_files、生成 gresource.c、生成 embed 的 .o"""
        for entry in self.data_files:
            self.sync_one(entry['from'], f'{self.output_dir}/{entry["to"]}')

        if self.gresource != '':
            self.generate_gresource_c()

        for index, embed in enumerate(self.embeds):
            self.generate_embed_obj(embed, index)

    def sync_one(self, source:str, target:str):
        """把源文件/目录同步到目标。目录整体复制（保持内部结构），文件按名复制"""
        if not os.path.isdir(source):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(source, target)
            return

        if os.path.isdir(target) and os.path.exists(target):
            shutil.rmtree(target)
        shutil.copytree(source, target)

    def generate_gresource_c(self):
        """glib-compile-resources 生成 C 源码。输出确定性（已实测），可参与 hash 增量判定"""
        os.makedirs(self.output_dir, exist_ok=True)
        target = f'{self.output_dir}/gresource.c'
        argv = ['glib-compile-resources', '--generate-source', '--target', target, self.gresource]
        self.command.run_argv(argv, capture=True)

    def generate_embed_obj(self, source:str, index:int):
        """ld -r -b binary 嵌入任意文件，产出 obj/embed_<序号>.o，链接时被自动收集"""
        obj_dir = f'{self.output_dir}/obj'
        os.makedirs(obj_dir, exist_ok=True)
        obj = f'{obj_dir}/embed_{index}.o'
        argv = ['ld', '-r', '-b', 'binary', source, '-o', obj]
        self.command.run_argv(argv, capture=True)

    # ---- 参与增量判定 / 生成物清单 ----

    def track_files(self):
        """
        参与 hash 变更检测的全部输入：data_files 源、gresource 的 xml 及其引用的文件、
        embed 源，以及已生成的 gresource.c（资源一变它就会变，从而触发该单元重编）
        """
        files = []

        for entry in self.data_files:
            if os.path.isdir(entry['from']):
                files += self.walk_files(entry['from'])
            else:
                files.append(entry['from'])

        if self.gresource != '':
            files += self.gresource_inputs()

        files += [embed for embed in self.embeds]

        generated = f'{self.output_dir}/gresource.c'
        if self.gresource != '' and os.path.exists(generated):
            files.append(generated)

        return files

    def gresource_inputs(self):
        """gresource 的 xml 与该 xml 引用的全部资源文件"""
        files = [self.gresource]
        try:
            root = ET.parse(self.gresource).getroot()
        except (ET.ParseError, OSError):
            return files

        base = os.path.dirname(self.gresource)
        for gresource in root.iter('gresource'):
            for file in gresource.iter('file'):
                if file.text is not None and file.text.strip() != '' and not file.text.startswith(('https://', 'http://')):
                    files.append(os.path.join(base, file.text).replace('\\', '/'))
        return files

    def generated_sources(self):
        """需要纳入编译的生成源（已生成的 gresource.c）"""
        if self.gresource == '':
            return []
        generated = f'{self.output_dir}/gresource.c'
        return [generated] if os.path.exists(generated) else []

    def generated_objects(self):
        """需要纳入链接的生成目标（生成的 embed .o）"""
        objs = []
        for index in range(len(self.embeds)):
            obj = f'{self.output_dir}/obj/embed_{index}.o'
            if os.path.exists(obj):
                objs.append(obj)
        return objs

    def walk_files(self, path:str):
        """目录下全部文件（相对路径）"""
        files = []
        for root, dirs, names in os.walk(path):
            for name in names:
                files.append(os.path.join(root, name).replace('\\', '/'))
        return files
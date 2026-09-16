import os
import sys
import functools
import click

from antelope.md5 import *
from antelope.enums import *
from antelope.errors import *
from antelope.os_ops.dir import *
from antelope.os_ops.log import *
from antelope.args_parser.external import *
from antelope.args_parser.external_json import *
from antelope.compiler.compiler import *
from antelope.linker.linker import *
from antelope.analyze.analyzor import *
from antelope.cli.init_json import *
from antelope.cli.console import *
from antelope.runner import *

class Antelope:
    def __init__(self):
        self.project_name = ""
        self.source = []
        self.include_directories = []
        self.target_type = TargetType.Static
        self.compiler_type = CompilerType.gxx
        self.compile_args_list = []
        self.link_args_list = []
        self.analyze_files = []

        self.dir = Directory()
        self.console = Console()
        self.output_dir = '.'

    def flushSetting(self):
        self.external = External(self.project_name, self.source,
                            self.include_directories, self.target_type,
                            self.compiler_type, self.compile_args_list,
                            self.link_args_list, self.output_dir)

        compilerObj = Compiler(self.project_name, self.source,
                            self.include_directories, self.target_type,
                            self.compiler_type, self.compile_args_list,
                            self.link_args_list, self.output_dir)
        self.compiler = compilerObj

        linkerObj = Linker(self.project_name, self.source,
                            self.include_directories, self.target_type,
                            self.compiler_type, self.compile_args_list,
                            self.link_args_list, self.output_dir)
        self.linker = linkerObj

        runnerObj = Runner(self.project_name, self.source,
                            self.include_directories, self.target_type,
                            self.compiler_type, self.compile_args_list,
                            self.link_args_list, self.output_dir)
        self.runner = runnerObj

        self.analyzor = Analyzor(self.output_dir)

    def get_include_files(self):
        """
        获取所有 include 项中需要参与构建的文件
        """
        include_files = []
        compile_files = []
        for path in self.external.include_directories:
            files = self.dir.walkDirFullPath(f'{path}')
            include_files += files

        for file in include_files:
            if file.endswith('.c') or file.endswith('.cc') or file.endswith('.cpp') or file.endswith('.h'):
                compile_files.append(file)

        return compile_files

    def get_project_source(self):
        """本次构建涉及的全部输入文件"""
        return self.source + self.get_include_files()

    def get_track_files(self):
        """参与变更检测的文件：配置中的源文件、include 目录下的文件、以及上次构建记录的依赖"""
        return self.source + self.compiler.collect_dependencies()

    def save_baseline(self):
        """构建成功后刷新 hash 基线，使下次构建以本次成功构建为比较基准"""
        CalcHash(self.get_track_files(), self.output_dir).compute_new_Md5()

    def build(self):
        self.buildType = BuildType.Build

        self.dir.MakeDirectory(f"{self.output_dir}/obj/")
        self.dir.MakeDirectory(f"{self.output_dir}/log/")

        calc = CalcHash(self.get_track_files(), self.output_dir)
        changed_files = calc.GetChangedFiles()

        stale_sources = self.compiler.get_stale_sources(self.get_project_source(), changed_files)
        if stale_sources.__len__() == 0:
            self.console.WriteNotice('项目没有改动，无需重新构建. 如需强制全量构建，请使用 antel rebuild 构建.')
            return

        os.system(f'rm -rf {self.output_dir}/*.a {self.output_dir}/*.so')

        self.compiler.compile(stale_sources)
        self.linker.link()
        self.save_baseline()

    def rebuild(self):
        self.buildType = BuildType.Rebuild
        os.system(f'rm -rf {self.output_dir}/*.a {self.output_dir}/*.so')

        self.dir.ClearMakeDirectory(f"{self.output_dir}/obj/")
        self.dir.ClearMakeDirectory(f"{self.output_dir}/log/")

        self.compiler.compile(self.get_project_source())
        self.linker.link()
        self.save_baseline()

    def link(self):
        self.linker.link()

    def analyze(self, source=[]):
        self.analyzor.analyze_obj(source)

    def run(self):
        self.runner.run()

def readList(config:dict, key:str):
    """读取数组型配置项"""
    value = config.get(key, [])
    if not isinstance(value, list):
        raise ConfigError(f'{key} 必须是数组，当前为 {type(value).__name__}: {value}')
    return list(value)

def parseJsonConfig(file:str='antel'):
    external_json = External_Json()

    if not os.path.exists(f'./{file}.json'):
        raise ConfigError(f'{file}.json is not exist!')

    config = external_json.deserialize(f'./{file}.json')
    antel = Antelope()

    antel.project_name = str(config.get('projectName', '')).strip()
    if antel.project_name == '':
        raise ConfigError('projectName 不能为空')

    antel.output_dir = f'{antel.project_name}_{file}'
    print('项目名：' + antel.project_name)

    antel.source = readList(config, 'source')
    if antel.source.__len__() == 0:
        raise ConfigError('source 不能为空')
    antel.include_directories = readList(config, 'include_directories')

    target_type = str(config.get('target_type', '')).lower()
    if target_type == 'static':
        antel.target_type = TargetType(TargetType.Static.value)
    elif target_type == 'shared':
        antel.target_type = TargetType(TargetType.Shared.value)
    elif target_type == 'exe':
        antel.target_type = TargetType(TargetType.Executable.value)
    else:
        raise ConfigError(f'target_type 取值非法：{target_type}，可选 static、shared、exe')
    print('生成目标为：' + antel.target_type.name)

    compiler_type = str(config.get('compiler', '')).lower()
    if compiler_type == 'msvc':
        antel.compiler_type = CompilerType(CompilerType.msvc.value)
    elif compiler_type == 'gxx':
        antel.compiler_type = CompilerType(CompilerType.gxx.value)
    elif compiler_type == 'llvm':
        antel.compiler_type = CompilerType(CompilerType.llvm.value)
    else:
        raise ConfigError(f'compiler 取值非法：{compiler_type}，可选 msvc、gxx、llvm')
    print('编译器类型：' + antel.compiler_type.name)

    antel.compile_args_list = readList(config, 'compile_args')
    antel.link_args_list = readList(config, 'link_args')
    antel.analyze_files = readList(config, 'analyze_files')

    antel.flushSetting()
    print('--------------------------------------------------')
    return antel

def handleBuildError(func):
    """构建失败时以非 0 退出码结束，避免失败被当成成功"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BuildError as error:
            click.echo(str(error), err=True)
            sys.exit(1)
    return wrapper

@click.group()
def main():
    pass

@main.command(help='初始化配置文件 antel.json')
def init():
    init = InitJson()
    init.createFromTemplate()

@main.command(help='构建项目差异部分')
@click.option('--file', '-f', default='antel', help='指定一个配置文件')
@handleBuildError
def build(file):
    config = parseJsonConfig(file)
    config.build()

@main.command(help='重新构建项目')
@click.option('--file', '-f', default='antel', help='指定一个配置文件')
@handleBuildError
def rebuild(file):
    config = parseJsonConfig(file)
    config.rebuild()

@main.command(help='不编译，只进行一次链接操作')
@click.option('--file', '-f', default='antel', help='指定一个配置文件')
@handleBuildError
def link(file):
    config = parseJsonConfig(file)
    config.link()

@main.command(help='分析源文件及其生成')
@click.option('--file', '-f', default='antel', help='指定一个配置文件')
@handleBuildError
def analyze(file):
    config = parseJsonConfig(file)
    config.analyze(config.analyze_files)
    print('analyze finished!')

@main.command(help='清除构建生成，包括所有中间文件与生成目标')
@click.option('--file', '-f', default='antel', help='指定一个配置文件')
@handleBuildError
def clean(file):
    config = parseJsonConfig(file)
    Log(config.output_dir).clearLog()
    print('clean finished!')

@main.command(help='执行编译后的结果')
@click.option('--file', '-f', default='antel', help='指定一个配置文件')
@handleBuildError
def run(file):
    config = parseJsonConfig(file)
    config.run()
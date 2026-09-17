import os
import re
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
from antelope.makefile import *
from antelope.analyze.analyzor import *
from antelope.cli.init_json import *
from antelope.cli.console import *
from antelope.runner import *

DEFAULT_JOBS = min(8, os.cpu_count() or 1)
BACKENDS = ('auto', 'make', 'antel')
RESPONSE_FILE_MODES = ('auto', 'always', 'never')
GENERATED_TARGETS = ['*.a', '*.so']

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
        self.jobs = DEFAULT_JOBS
        self.backend = 'auto'
        self.compile_commands = True
        self.response_file = 'auto'

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
                            self.link_args_list, self.output_dir,
                            self.jobs, self.compile_commands)
        self.compiler = compilerObj

        linkerObj = Linker(self.project_name, self.source,
                            self.include_directories, self.target_type,
                            self.compiler_type, self.compile_args_list,
                            self.link_args_list, self.output_dir,
                            self.response_file)
        self.linker = linkerObj

        runnerObj = Runner(self.project_name, self.source,
                            self.include_directories, self.target_type,
                            self.compiler_type, self.compile_args_list,
                            self.link_args_list, self.output_dir)
        self.runner = runnerObj

        self.make_runner = MakeRunner(self.output_dir, self.project_name, self.jobs)

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

        self.dir.RemoveFiles(self.output_dir, GENERATED_TARGETS)

        self.compileSources(stale_sources)
        self.linker.link()
        self.save_baseline()

    def rebuild(self):
        self.buildType = BuildType.Rebuild
        self.dir.RemoveFiles(self.output_dir, GENERATED_TARGETS)

        self.dir.ClearMakeDirectory(f"{self.output_dir}/obj/")
        self.dir.ClearMakeDirectory(f"{self.output_dir}/log/")

        self.compileSources([], rebuild=True)
        self.linker.link()
        self.save_baseline()

    def compileSources(self, stale_sources:list, rebuild:bool=False):
        """
        按 backend 选择执行器。无论走哪条路，都由 antel 决定"编什么"，
        make 只负责把它们并行编完（DESIGN §3.2）
        """
        backend = self.resolveBackend()
        jobs = self.executorJobs(backend)
        self.compiler.jobs = jobs
        self.make_runner.jobs = jobs

        if backend == 'make':
            plan = self.buildMakePlan()
            stale = set(stale_sources)
            stale_objs = [unit.obj for unit in plan.units
                        if rebuild or unit.source in stale]
            self.make_runner.run(plan, stale_objs)
            return

        if rebuild:
            self.compiler.compile(self.get_project_source())
        else:
            self.compiler.compile(stale_sources)

    def resolveBackend(self):
        """auto：优先用 make，机器上没有 make 时回退内置执行器并提示"""
        if self.backend != 'auto':
            return self.backend

        if makeAvailable():
            return 'make'

        self.console.WriteNotice('未找到 make，回退到内置执行器（backend: auto）')
        return 'antel'

    def executorJobs(self, backend:str):
        """
        被 make 调用时不在内部再叠加并行：内置执行器无法共享 make 的 jobserver，
        退回串行；make 执行器交给 MAKEFLAGS 自己处理（见 MakeRunner.buildArgv）
        """
        if backend == 'make':
            return self.jobs

        flags = parentMakeFlags()
        if flags != '':
            self.console.WriteNotice(f'检测到由 make 调用（MAKEFLAGS={flags}），内置执行器改为串行（jobs=1）')
            return 1
        return self.jobs

    def buildMakePlan(self):
        """本轮构建的完整计划：全部编译单元（make 需要每个单元的规则）+ 链接作业（供手工 make 使用）"""
        units = self.compiler.build_compile_units(self.get_project_source())
        self.compiler.log_compile_units(units)
        self.compiler.write_compile_commands(units)

        self.linker.external.parse_link_args()
        link_job = self.linker.build_link_job([unit.obj for unit in units],
                                            self.linker.external.parse_compile_args())
        return BuildPlan(units=units, link=link_job, jobs=self.jobs, backend=self.backend)

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

def readBool(config:dict, key:str, default:bool):
    """读取布尔型配置项"""
    value = config.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f'{key} 必须是 true 或 false，当前为 {type(value).__name__}: {value}')
    return value

def readJobs(config:dict):
    """读取并行度。1 表示串行"""
    value = config.get('jobs', DEFAULT_JOBS)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f'jobs 必须是正整数，当前为 {type(value).__name__}: {value}')
    if value < 1:
        raise ConfigError(f'jobs 必须大于 0，当前为 {value}')
    return value

def readResponseFile(config:dict):
    """读取响应文件策略：auto（命令行过长才用）/ always / never"""
    value = str(config.get('response_file', 'auto')).lower()
    if value not in RESPONSE_FILE_MODES:
        raise ConfigError(f'response_file 取值非法：{value}，可选 ' + '、'.join(RESPONSE_FILE_MODES))
    return value

def readBackend(config:dict):
    """执行器：auto（默认：优先 make，缺 make 时回退）/ make / antel"""
    value = str(config.get('backend', 'auto')).lower()
    if value not in BACKENDS:
        raise ConfigError(f'backend 取值非法：{value}，可选 ' + '、'.join(BACKENDS))
    return value

def describeBackend(backend:str):
    """把 auto 解析成实际会用的执行器，便于在配置摘要里一眼看到"""
    if backend != 'auto':
        return backend

    if makeAvailable():
        return 'auto → make'
    return 'auto → antel（未找到 make）'

def readProjectName(config:dict):
    """
    读取并校验项目名。项目名会进入生成目标名与链接脚本，
    因此限制为字母、数字、下划线、点与连字符（含中文等 Unicode 文字字符）
    """
    name = str(config.get('projectName', '')).strip()
    if name == '':
        raise ConfigError('projectName 不能为空')

    if not re.fullmatch(r'[\w.-]+', name):
        invalid = ''.join(sorted({item for item in name if not re.fullmatch(r'[\w.-]', item)}))
        raise ConfigError(f'projectName 只能包含字母、数字、下划线、点与连字符，当前含非法字符：{invalid}')
    return name

def parseJsonConfig(file:str='antel'):
    external_json = External_Json()

    if not os.path.exists(f'./{file}.json'):
        raise ConfigError(f'{file}.json is not exist!')

    config = external_json.deserialize(f'./{file}.json')
    antel = Antelope()

    antel.project_name = readProjectName(config)

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

    antel.jobs = readJobs(config)
    antel.backend = readBackend(config)
    antel.compile_commands = readBool(config, 'compile_commands', True)
    antel.response_file = readResponseFile(config)
    print(f'并行度：{antel.jobs}  执行器：{describeBackend(antel.backend)}  compile_commands.json：'
        + ('开启' if antel.compile_commands else '关闭'))

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
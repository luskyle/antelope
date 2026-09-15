import sys
from antelope.md5 import *
from antelope.enums import *
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
import click

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
        self.log = Log()
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
        获取所有 include 项中需要编译的文件
        """

        # includes = self.external.include_directories
        # print(includes)
        
        include_files = []
        compile_files = []
        for path in self.external.include_directories:
            files = self.dir.walkDirFullPath(f'{path}')
            include_files += files
        
        for file in include_files:
            if file.endswith('.c') or file.endswith('.cc') or file.endswith('.cpp') or file.endswith('.h'):
                compile_files.append(file)
        
        return compile_files

    def build(self):
        self.buildType = BuildType.Build

        if not os.path.exists(f"{self.output_dir}/obj/"):
            self.dir.ClearMakeDirectory(f"{self.output_dir}/obj/")
        if not os.path.exists(f"{self.output_dir}/log/"):
            self.dir.ClearMakeDirectory(f"{self.output_dir}/log/")
        
        include_files = self.get_include_files()
        print('include 的所有文件:')
        print(include_files)
        self.source = self.source + include_files
        
        calc = CalcHash(self.source, self.output_dir)
        hashes = calc.GetMd5List()
        diff_src = list(calc.diff.keys())

        if diff_src.__len__() == 0:
            self.console.WriteNotice('项目没有改动或未生成. 如果您确实需要生成项目，请使用 antel rebuild 构建.')
            return
        
        os.system(f'rm -rf {self.output_dir}/*.a {self.output_dir}/*.so')

        self.external.parse_source(self.source)
        uncompiled_files = self.compiler.get_uncompiled_files()

        print(diff_src + uncompiled_files)
        self.compiler.compile(diff_src + uncompiled_files)
        self.linker.link()
    
    def rebuild(self):
        self.buildType = BuildType.Rebuild
        os.system(f'rm -rf {self.output_dir}/*.a {self.output_dir}/*.so')

        self.dir.ClearMakeDirectory(f"{self.output_dir}/obj/")
        self.dir.ClearMakeDirectory(f"{self.output_dir}/log/")

        include_files = self.get_include_files()
        print('include 的所有文件:')
        print(include_files)
        self.source = self.source + include_files

        calc = CalcHash(self.source, self.output_dir)
        calc.compute_new_Md5()

        self.compiler.compile(self.source)
        self.linker.link()

    def clear(self):
        self.log.clearLog()

    def link(self):
        self.linker.link()

    def analyze(self, source=[]):
        self.analyzor.analyze_obj(source)
    
    def run(self):
        self.runner.run()

def parseJsonConfig(file:str='antel'):
    external_json = External_Json()

    if not os.path.exists(f'./{file}.json'):
        print(f'{file}.json is not exist!')
        return

    json = external_json.deserialize(f'./{file}.json')
    antel = Antelope()

    antel.project_name = json['projectName']
    antel.output_dir = f'{antel.project_name}_{file}'
    print('项目名：' + antel.project_name)

    antel.source = list(json['source'])
    exclude_source = list(json['exclude_source'])
    antel.include_directories = list(json['include_directories'])
    
    target_type = str(json['target_type']).lower()
    if target_type == 'static':
        antel.target_type = TargetType(TargetType.Static.value)
    elif target_type == 'shared':
        antel.target_type = TargetType(TargetType.Shared.value)
    elif target_type == 'exe':
        antel.target_type = TargetType(TargetType.Executable.value)
    print('生成目标为：' + antel.target_type.name)

    compiler_type = str(json['compiler']).lower()
    if compiler_type == 'msvc':
        antel.compiler_type = CompilerType(CompilerType.msvc.value)
    elif compiler_type == 'gxx':
        antel.compiler_type = CompilerType(CompilerType.gxx.value)
    elif compiler_type == 'llvm':
        antel.compiler_type = CompilerType(CompilerType.llvm.value)

    # print(antel.compiler_type)
    print('编译器类型：' + antel.compiler_type.name)

    antel.compile_args_list = list(json['compile_args'])
    antel.link_args_list = (str(json['link_args']))
    antel.analyze_files = list(json['analyze_files'])

    antel.flushSetting()
    print('--------------------------------------------------')
    return antel

@click.group()
def main():
    pass

@main.command(help='初始化配置文件 antel.json')
def init():
    init = InitJson()
    init.createFromTemplate()

@main.command(help='构建项目差异部分')
@click.option('--file', '-f', default='antel', help='指定一个配置文件')
def build(file):
    config = parseJsonConfig(file)
    if config is not None:
        config.build()

@main.command(help='重新构建项目')
@click.option('--file', '-f', default='antel', help='指定一个配置文件')
def rebuild(file):
    config = parseJsonConfig(file)
    if config is not None:
        config.rebuild()

@main.command(help='不编译，只进行一次链接操作')
@click.option('--file', '-f', default='antel', help='指定一个配置文件')
def link(file):
    config = parseJsonConfig(file)
    if config is not None:
        config.link()

@main.command(help='分析源文件及其生成')
@click.option('--file', '-f', default='antel', help='指定一个配置文件')
def analyze(file):
    config = parseJsonConfig(file)
    if config is not None:
        config.analyze(config.analyze_files)
    print('analyze finished!')

@main.command(help='清除构建生成(不包括 static、shared、executable 目标)')
@click.option('--antel_config', '-f', default='antel', help='指定一个用于构建的配置文件名，清除对应的输出')
def clean(antel_config):
    config = parseJsonConfig(antel_config)
    if config is not None:
        log = Log(f'{config.project_name}_{antel_config}')
        log.clearLog()
        print('clean finished!')

@main.command(help='执行编译后的结果')
@click.option('--antel_config', '-f', default='antel', help='指定一个配置文件')
def run(antel_config):
    config = parseJsonConfig(antel_config)
    config.run()
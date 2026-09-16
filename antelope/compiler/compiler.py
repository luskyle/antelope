from alive_progress import alive_bar
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from antelope.enums import *
from antelope.errors import *
from antelope.build_plan import *
from antelope.args_parser.external import *
from antelope.os_ops.command import *
from antelope.os_ops.dir import *
from antelope.os_ops.log import *

class Compiler():
    def __init__(self, project_name_global:str="", source_global:list=[],
                include_directories_global:list=[], target_type_global:TargetType=TargetType.Static,
                compiler_global:CompilerType=CompilerType.gxx, compiler_args_list_global:list=[],
                link_args_list_global:list=[], output_dir:str='.', jobs:int=1,
                compile_commands:bool=True):
        self.project_name = project_name_global
        self.source = list(source_global)
        self.include_directories = list(include_directories_global)
        self.target_type = target_type_global
        self.compiler_type = compiler_global
        self.compile_args_list = list(compiler_args_list_global)
        self.link_args_list = list(link_args_list_global)
        self.output_dir = output_dir
        self.jobs = jobs
        self.compile_commands = compile_commands

        self.dir = Directory()
        self.log = Log(output_dir)
        self.command = Command()
        self.external = External(self.project_name, self.source,
                            self.include_directories, self.target_type,
                            self.compiler_type, self.compile_args_list,
                            self.link_args_list, self.output_dir)

    def compile(self, input_src:list):
        units = self.build_compile_units(input_src)
        self.log.writeLogfile([unit.render() + '\n' for unit in units],
                            self.project_name + '.' + self.compiler_type.name)
        self.write_compile_commands(units)
        self.run_units(units)

    def build_compile_units(self, input_src:list):
        """把本轮要编译的源文件展开成带结构化参数的编译单元"""
        self.external.parse_source(input_src)
        includes = self.external.parse_include_directories()
        compile_args = self.external.parse_compile_args()

        if self.target_type == TargetType.Shared:
            print("生成目标为 Shared")
        elif self.target_type == TargetType.Static:
            print("生成目标为 Static")
        elif self.target_type == TargetType.Executable:
            print("生成目标为 Executable")

        units = []
        for i, obj_file in enumerate(self.external.obj_files):
            source = self.external.compile_files[i]
            obj = f'{self.output_dir}/obj/{obj_file}'

            args = list(compile_args)
            args += self.parse_dep_file_args(obj)
            args += ['-c', '-o', obj, source]
            args += includes

            units.append(CompileUnit(source=source, obj=obj, dep=f'{obj}.d',
                                    driver=self.compile_driver(source), args=args))
        return units

    def compile_driver(self, source:str):
        """按编译器类型与源文件后缀选择驱动。.c 走 C 编译器，其余走 C++ 编译器"""
        if self.compiler_type == CompilerType.msvc:
            return 'cl'
        elif self.compiler_type == CompilerType.llvm:
            return 'clang'

        if os.path.splitext(source)[-1] == '.c':
            return 'gcc'
        return 'g++'

    def parse_dep_file_args(self, obj_item:str):
        """生成依赖文件所需的编译参数。msvc 无 -MMD，其目标文件每次都需重新编译"""
        if self.compiler_type == CompilerType.msvc:
            return []
        return ['-MMD', '-MF', f'{obj_item}.d']

    def run_units(self, units:list):
        """按 jobs 并发执行编译单元。任一失败即停止派发，并以非 0 退出"""
        if units.__len__() == 0:
            return

        jobs = max(1, min(self.jobs, units.__len__()))
        stop = threading.Event()
        failures = []

        with alive_bar(units.__len__()) as bar:
            if jobs == 1:
                for unit in units:
                    self.run_unit(unit, stop, failures)
                    bar()
            else:
                with ThreadPoolExecutor(max_workers=jobs) as pool:
                    futures = [pool.submit(self.run_unit, unit, stop, failures) for unit in units]
                    for future in as_completed(futures):
                        future.result()
                        bar()

        if failures.__len__() != 0:
            unit, error = failures[0]
            raise CommandError(error.command, error.return_code, error.output,
                            reason=f'{failures.__len__()}/{units.__len__()} 个编译单元失败，'
                                   f'首个失败源文件：{unit.source}')

    def run_unit(self, unit:CompileUnit, stop:threading.Event, failures:list):
        """执行单个编译单元。已收到停止信号则跳过，避免失败后继续做无用功"""
        if stop.is_set():
            return

        try:
            self.command.run_argv(unit.argv())
        except BuildError as error:
            stop.set()
            failures.append((unit, error))

    def write_compile_commands(self, units:list):
        """输出 compile_commands.json，供 clangd 等工具解析"""
        if not self.compile_commands:
            return ''

        path = f'{self.output_dir}/compile_commands.json'
        writeCompileCommands(path, units, os.path.abspath('.'))
        print(f'compile_commands.json 已更新：{path}')
        return path

    def read_dep_file(self, dep_file:str):
        """解析 -MMD 生成的依赖文件，返回其中记录的依赖文件路径"""
        if not os.path.exists(dep_file):
            return []

        with open(dep_file) as file:
            content = file.read()

        """
        形如：obj/src_main.o: src/main.c src/foo.h \
		 inc/bar.h
        """
        content = content.replace('\\\n', ' ')
        dependencies = content.partition(':')[2]
        return dependencies.split()

    def collect_dependencies(self):
        """收集所有已生成依赖文件中记录的输入文件"""
        dependencies = []
        dep_dir = f'{self.output_dir}/obj'
        if not os.path.exists(dep_dir):
            return dependencies

        for file in os.listdir(dep_dir):
            if file.endswith('.d'):
                dependencies += self.read_dep_file(f'{dep_dir}/{file}')
        return list(dict.fromkeys(dependencies))

    def get_stale_sources(self, source:list, changed_files:list):
        """返回需要重新编译的源文件：目标文件或依赖文件缺失，或源文件及其依赖发生变化"""
        self.external.parse_source(source)
        changed = set(changed_files)

        stale_sources = []
        for obj_file, compile_file in self.external.compile_obj_files_map.items():
            obj_path = f'{self.output_dir}/obj/{obj_file}'
            dep_path = f'{obj_path}.d'
            dependencies = self.read_dep_file(dep_path)

            if (not os.path.exists(obj_path)
                    or not os.path.exists(dep_path)
                    or compile_file in changed
                    or changed & set(dependencies)):
                stale_sources.append(compile_file)

        print('全部待编译文件：' + str(self.external.obj_files.__len__()))
        print('需重新编译文件：' + str(stale_sources.__len__()))
        self.log.writeLogfile([f"'{item}'\n" for item in stale_sources], 'stale_files')
        return stale_sources
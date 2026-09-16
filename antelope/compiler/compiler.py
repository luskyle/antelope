from alive_progress import alive_bar
import os

from antelope.enums import *
from antelope.args_parser.external import *
from antelope.os_ops.command import *
from antelope.os_ops.dir import *
from antelope.os_ops.log import *

class Compiler():
    def __init__(self, project_name_global:str="", source_global:list=[],
                include_directories_global:list=[], target_type_global:TargetType=TargetType.Static,
                compiler_global:CompilerType=CompilerType.gxx, compiler_args_list_global:list=[],
                link_args_list_global:list=[], output_dir:str='.'):
        self.project_name = project_name_global
        self.source = list(source_global)
        self.include_directories = list(include_directories_global)
        self.target_type = target_type_global
        self.compiler_type = compiler_global
        self.compile_args_list = list(compiler_args_list_global)
        self.link_args_list = list(link_args_list_global)
        self.output_dir = output_dir

        self.dir = Directory()
        self.log = Log(output_dir)
        self.command = Command()
        self.external = External(self.project_name, self.source,
                            self.include_directories, self.target_type,
                            self.compiler_type, self.compile_args_list,
                            self.link_args_list, self.output_dir)

    def compile(self, input_src:list):
        self.external.parse_source(input_src)
        objs = self.gen_build_objects()
        self.log.writeLogfile(objs, self.project_name + '.' + self.compiler_type.name)

        with alive_bar(objs.__len__()) as bar:
            for command in objs:
                self.command.run(command)
                bar()

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

    def gen_build_objects(self):
        includes = self.external.parse_include_directories()

        if self.target_type == TargetType.Shared:
            print("生成目标为 Shared")
        elif self.target_type == TargetType.Static:
            print("生成目标为 Static")
        elif self.target_type == TargetType.Executable:
            print("生成目标为 Executable")

        compile_args = self.external.parse_compile_args()

        build_command_item = []
        for i, obj_file in enumerate(self.external.obj_files):
            obj_item = f"{self.output_dir}/obj/{obj_file}"
            compile_item = self.external.compile_files[i]
            compile_item_ext = os.path.splitext(compile_item)[-1]

            compiler_type = ''
            if self.compiler_type == CompilerType.msvc:
                compiler_type = 'cl '
            elif self.compiler_type == CompilerType.gxx:
                if compile_item_ext == '.c':
                    compiler_type = 'gcc '
                else:
                    compiler_type = 'g++ '
            elif self.compiler_type == CompilerType.llvm:
                compiler_type = 'clang '

            build_command_item.append(compiler_type + compile_args
                                      + self.parse_dep_file_args(obj_item)
                                      + "-c -o " + obj_item + " " + compile_item + " " + includes + "\n")
        return build_command_item

    def parse_dep_file_args(self, obj_item:str):
        """生成依赖文件所需的编译参数。msvc 无 -MMD，其目标文件每次都需重新编译"""
        if self.compiler_type == CompilerType.msvc:
            return ''
        return f'-MMD -MF {obj_item}.d '
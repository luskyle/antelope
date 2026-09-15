from alive_progress import alive_bar
import os
from antelope.enums import *
from antelope.args_parser.external import *
from antelope.os_ops.dir import *
from antelope.os_ops.log import *

class Compiler():
    def __init__(self, project_name_global:str="", source_global:list=[], 
                include_directories_global:list=[], target_type_global:TargetType=TargetType.Static, 
                compiler_global:CompilerType=CompilerType.gxx, compiler_args_list_global:list=[],
                link_args_list_global:list=[], output_dir:str='.'):
        self.project_name = project_name_global
        self.source = source_global
        self.include_directories = include_directories_global
        self.target_type = target_type_global
        self.compiler_type = compiler_global
        self.compile_args_list = compiler_args_list_global
        self.link_args_list = link_args_list_global
        self.output_dir = output_dir

        self.dir = Directory()
        self.log = Log(output_dir)
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
                os.system(command)
                bar()

    def get_uncompiled_files(self):
        compiled_objs = self.dir.walkDir(f'{self.output_dir}/obj')

        print('全部待编译文件：' + str(self.external.obj_files.__len__()))
        print('已编译文件：' + str(compiled_objs.__len__()))

        result_objs = list(set(self.external.obj_files) - set(compiled_objs))
        print('需重新编译文件：' + str(result_objs.__len__()))
        # print(result_objs)

        result_files = []
        result_files_log = []

        for item in result_objs:
            file = self.external.compile_obj_files_map.get(item)
            print(file)
            result_files.append(file)
            result_files_log.append("'" + file + "'" + "\n")

        self.log.writeLogfile(result_files_log, 'uncompiled_files')
        return result_files
    
    def gen_build_objects(self):
        includes = self.external.parse_include_directories()

        if self.target_type == TargetType.Shared:
            self.external.compile_args_list.append('-fPIC -shared')
            print("生成目标为 Shared")
        elif self.target_type == TargetType.Static:
            print("生成目标为 Static")
        elif self.target_type == TargetType.Executable:
            print("生成目标为 Executable")

        compile_args = self.external.parse_compile_args()
        # self.log.writeLogfile(compile_args, self.external.project_name + '.compile.args')
        # print(includes)

        build_command_item = []
        i = 0

        # print(self.external.obj_files)
        for item in self.external.obj_files:
            obj_item = f"{self.output_dir}/obj/{self.external.obj_files[i]}"
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

            build_command_item.append(compiler_type + compile_args + "-c -o " + obj_item + " " + compile_item + " " + includes + "\n")
            i += 1
        return build_command_item

from alive_progress import alive_bar
import os
from antelope.enums import *
from antelope.args_parser.external import *
from antelope.os_ops.dir import *
from antelope.os_ops.log import *

class Runner():
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

    def run(self):
        # print(f'---------{self.output_dir}----------')
        if self.target_type != TargetType.Executable:
            print(f"目标{self.target_type} 不是可执行的程序！")
            return
        
        print("开始执行...")
        build_folder = f'{self.output_dir}'
        if os.path.exists(build_folder):
            os.system(f'./{build_folder}/{self.project_name}')
        else:
            print("不存在可执行的程序，请先生成项目！")

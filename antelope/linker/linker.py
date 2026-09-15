import os
import shlex
import subprocess
from antelope.enums import *
from antelope.args_parser.external import *
from antelope.os_ops.dir import *
from antelope.os_ops.log import *

ld_command = ""

class Linker():
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
                            self.compiler_type, self.compile_args_list, self.link_args_list)

    def link(self):
        objs = ""        
        link_args = self.external.parse_link_args()
        compile_args = self.external.parse_compile_args()

        for root, dirs, files in os.walk(f'{self.output_dir}/obj/'):
            for file in files:
                objs += root + file + ' '

        global ld_command
        if self.target_type == TargetType.Static:
            ld_command = f'ar csr {self.output_dir}/lib{self.project_name}.a {objs} '
        elif self.target_type == TargetType.Shared:
            ld_command = f'ld -shared -o {self.output_dir}/lib{self.project_name}.so --add-needed -lc -lm {self.external.link_system_args} {objs} '
        elif self.target_type == TargetType.Executable:
            # print('------------' + str(self.compiler_type))
            if self.compiler_type == CompilerType.msvc:
                pass
            elif self.compiler_type == CompilerType.gxx:
                ld_command = f'g++ -s {objs} -o {self.output_dir}/{self.project_name} -Wl,--add-needed -lc -lm {compile_args} {self.external.link_system_args} '
            elif self.compiler_type == CompilerType.llvm:
                pass

        # print('dfdfd'+ld_command)

        if self.target_type != TargetType.Static:
            self.log.writeLogfile("#!/usr/bin/bash\n" + ld_command + self.external.link_user_args, self.project_name + '_link.sh')
        else:
            self.log.writeLogfile("#!/usr/bin/bash\n" + ld_command, self.project_name + '_link.sh')

        cmd = shlex.split(f'bash {self.output_dir}/log/{self.project_name}_link.sh')
        print('开始链接...')
        call = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout= subprocess.PIPE, stderr=subprocess.STDOUT)
        out,err = call.communicate()
        call.wait()
        self.log.writeLogfile(bytes.decode(out), 'linkInfor')
        print(bytes.decode(out))
        print('链接完毕')
        
        print('优化生成目标...')
        if self.target_type == TargetType.Shared:
            os.system(f'readelf -a {self.output_dir}/lib{self.project_name}.so >{self.output_dir}/log/readelf_lib{self.project_name}.so.txt')
            os.system(f'ldd {self.output_dir}/lib{self.project_name}.so >{self.output_dir}/log/ldd_lib{self.project_name}.so.txt')
            os.system(f'nm -ACD {self.output_dir}/lib{self.project_name}.so >{self.output_dir}/log/nm_lib{self.project_name}.so.txt')
        elif self.target_type == TargetType.Static:
            os.system(f'nm -g {self.output_dir}/lib{self.project_name}.a >{self.output_dir}/log/symbol_lib{self.project_name}.a.txt')
            os.system(f'ar -t {self.output_dir}/lib{self.project_name}.a >{self.output_dir}/log/archive_lib{self.project_name}.a.txt')
            os.system(f'objdump -x {self.output_dir}/lib{self.project_name}.a >{self.output_dir}/log/objdump_lib{self.project_name}.a.txt')
            os.system(f'strip --strip-unneeded {self.output_dir}/lib{self.project_name}.a')
        print('优化完毕')

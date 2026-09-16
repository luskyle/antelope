import os

from antelope.enums import *
from antelope.errors import *
from antelope.args_parser.external import *
from antelope.os_ops.command import *
from antelope.os_ops.dir import *
from antelope.os_ops.log import *

class Linker():
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

    def link(self):
        objs = ""
        compile_args = self.external.parse_compile_args()
        self.external.parse_link_args()

        for root, dirs, files in os.walk(f'{self.output_dir}/obj/'):
            for file in files:
                if file.endswith('.o'):
                    objs += root + file + ' '

        link_script = "#!/usr/bin/bash\n" + self.gen_link_command(objs, compile_args)
        self.log.writeLogfile([link_script], self.project_name + '_link.sh')

        print('开始链接...')
        self.command.run(f'bash {self.output_dir}/log/{self.project_name}_link.sh',
                        redirect_to=f'{self.output_dir}/log/linkInfor', echo=True)
        print('链接完毕')

        print('优化生成目标...')
        self.analyze_target()
        print('优化完毕')

    def gen_link_command(self, objs:str, compile_args:str):
        if self.target_type == TargetType.Static:
            return f'ar csr {self.output_dir}/lib{self.project_name}.a {objs} \n'
        elif self.target_type == TargetType.Shared:
            return (f'{self.link_driver()} -shared -o {self.output_dir}/lib{self.project_name}.so {objs} '
                    f'-lm {self.external.link_system_args} {self.external.link_user_args}\n')
        else:
            return (f'{self.link_driver()} -s {objs} -o {self.output_dir}/{self.project_name} '
                    f'-Wl,--add-needed -lc -lm {compile_args} {self.external.link_system_args} '
                    f'{self.external.link_user_args}\n')

    def link_driver(self):
        """共享库与可执行程序必须经由编译器驱动链接，才能自动带上 crt 与 C++ 运行时"""
        if self.compiler_type == CompilerType.gxx:
            return 'g++'
        elif self.compiler_type == CompilerType.llvm:
            return 'clang++'

        raise ConfigError(f'{self.compiler_type.name} 的链接尚未实现，无法生成 {self.target_type.name} 目标')

    def analyze_target(self):
        """把生成目标的符号、依赖等信息落盘，便于事后核查"""
        log_dir = f'{self.output_dir}/log'

        if self.target_type == TargetType.Shared:
            target = f'{self.output_dir}/lib{self.project_name}.so'
            self.command.run(f'readelf -a {target}', redirect_to=f'{log_dir}/readelf_lib{self.project_name}.so.txt')
            self.command.run(f'ldd {target}', redirect_to=f'{log_dir}/ldd_lib{self.project_name}.so.txt')
            self.command.run(f'nm -ACD {target}', redirect_to=f'{log_dir}/nm_lib{self.project_name}.so.txt')
        elif self.target_type == TargetType.Static:
            target = f'{self.output_dir}/lib{self.project_name}.a'
            self.command.run(f'nm -g {target}', redirect_to=f'{log_dir}/symbol_lib{self.project_name}.a.txt')
            self.command.run(f'ar -t {target}', redirect_to=f'{log_dir}/archive_lib{self.project_name}.a.txt')
            self.command.run(f'objdump -x {target}', redirect_to=f'{log_dir}/objdump_lib{self.project_name}.a.txt')
            self.command.run(f'strip --strip-unneeded {target}')
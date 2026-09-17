import os

from antelope.enums import *
from antelope.errors import *
from antelope.build_plan import *
from antelope.args_parser.external import *
from antelope.os_ops.command import *
from antelope.os_ops.dir import *
from antelope.os_ops.log import *

RESPONSE_FILE_THRESHOLD = 100000

class Linker():
    def __init__(self, project_name_global:str="", source_global:list=[],
                include_directories_global:list=[], target_type_global:TargetType=TargetType.Static,
                compiler_global:CompilerType=CompilerType.gxx, compiler_args_list_global:list=[],
                link_args_list_global:list=[], output_dir:str='.', response_file:str='auto',
                pkg_libs:list=[]):
        self.project_name = project_name_global
        self.source = list(source_global)
        self.include_directories = list(include_directories_global)
        self.target_type = target_type_global
        self.compiler_type = compiler_global
        self.compile_args_list = list(compiler_args_list_global)
        self.link_args_list = list(link_args_list_global)
        self.output_dir = output_dir
        self.response_file = response_file
        self.pkg_libs = list(pkg_libs)

        self.dir = Directory()
        self.log = Log(output_dir)
        self.command = Command()
        self.external = External(self.project_name, self.source,
                            self.include_directories, self.target_type,
                            self.compiler_type, self.compile_args_list,
                            self.link_args_list, self.output_dir)

    def link(self):
        objs = self.collect_objects()
        compile_args = self.external.parse_compile_args()
        self.external.parse_link_args()

        job = self.build_link_job(objs, compile_args)
        self.log.writeLogfile([job.script()], self.project_name + '_link.sh')

        print('开始链接...')
        self.command.run_argv(['bash', f'{self.output_dir}/log/{self.project_name}_link.sh'],
                            redirect_to=f'{self.output_dir}/log/linkInfor', echo=True)
        print('链接完毕')

        print('优化生成目标...')
        self.analyze_target()
        print('优化完毕')

    def collect_objects(self):
        """收集 obj/ 下所有目标文件（依赖文件不以 .o 结尾，天然被排除）"""
        objs = []
        for root, dirs, files in os.walk(f'{self.output_dir}/obj/'):
            for file in files:
                if file.endswith('.o'):
                    objs.append(root + file)
        return objs

    def build_link_job(self, objs:list, compile_args:list):
        """构造链接作业。共享库与可执行程序经编译器驱动链接，才能自动带上 crt 与运行时"""
        if self.target_type == TargetType.Static:
            driver = 'ar'
            args = ['csr', f'{self.output_dir}/lib{self.project_name}.a'] + objs
        elif self.target_type == TargetType.Shared:
            driver = self.link_driver()
            args = ['-shared', '-o', f'{self.output_dir}/lib{self.project_name}.so'] + objs
            args += ['-lm'] + self.external.link_system_args + self.external.link_user_args
            args += self.pkg_libs
        else:
            driver = self.link_driver()
            args = ['-s'] + objs
            args += ['-o', f'{self.output_dir}/{self.project_name}', '-Wl,--add-needed', '-lc', '-lm']
            args += list(compile_args) + self.external.link_system_args + self.external.link_user_args
            args += self.pkg_libs

        return LinkJob(driver=driver, args=args,
                    output=f'{self.output_dir}/{self.project_name}',
                    response_file=self.plan_response_file(driver, args))

    def plan_response_file(self, driver:str, args:list):
        """
        命令行过长时落一个响应文件并返回其路径，否则返回空串。
        ar 不支持 @file，只有编译器驱动才走这条路
        """
        if self.response_file == 'never' or driver == 'ar':
            return ''

        length = len(' '.join([driver] + args))
        if self.response_file == 'auto' and length < RESPONSE_FILE_THRESHOLD:
            return ''

        path = f'{self.output_dir}/log/{self.project_name}_link.rsp'
        with open(path, 'w') as file:
            file.write('\n'.join(args) + '\n')
        print(f'命令行过长（{length} 字符），改用响应文件：{path}')
        return path

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
            self.command.run_argv(['readelf', '-a', target], redirect_to=f'{log_dir}/readelf_lib{self.project_name}.so.txt')
            self.command.run_argv(['ldd', target], redirect_to=f'{log_dir}/ldd_lib{self.project_name}.so.txt')
            self.command.run_argv(['nm', '-ACD', target], redirect_to=f'{log_dir}/nm_lib{self.project_name}.so.txt')
        elif self.target_type == TargetType.Static:
            target = f'{self.output_dir}/lib{self.project_name}.a'
            self.command.run_argv(['nm', '-g', target], redirect_to=f'{log_dir}/symbol_lib{self.project_name}.a.txt')
            self.command.run_argv(['ar', '-t', target], redirect_to=f'{log_dir}/archive_lib{self.project_name}.a.txt')
            self.command.run_argv(['objdump', '-x', target], redirect_to=f'{log_dir}/objdump_lib{self.project_name}.a.txt')
            self.command.run_argv(['strip', '--strip-unneeded', target])
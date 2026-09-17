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
                pkg_libs:list=[], sanitize:list=[], coverage:bool=False,
                version:str='', soname:str='', rpath:list=[]):
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
        self.sanitize = list(sanitize)
        self.coverage = coverage
        self.version = version
        self.soname = soname
        self.rpath = list(rpath)

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

        self.create_version_links()

        print('优化生成目标...')
        self.analyze_target()
        print('优化完毕')

    def create_version_links(self):
        """版本化共享库的符号链接：libX.so.1 → libX.so.1.0.0，libX.so → libX.so.1"""
        if self.target_type != TargetType.Shared or self.version == '':
            return

        base = f'{self.output_dir}/lib{self.project_name}'
        real = f'{base}.so.{self.version}'
        # 用户给的 soname 可能是相对名（libcustom.so.2），统一落到输出目录下
        links = [f'{self.output_dir}/{self.soname}'] if self.soname != '' else []

        major = self.version.partition('.')[0]
        major_link = f'{base}.so.{major}'
        if major_link != real and major_link not in links:
            links.append(major_link)
        if f'{base}.so' not in links and f'{base}.so' != real:
            links.append(f'{base}.so')

        if not os.path.exists(real):
            raise CommandError(f'{self.project_name}_link.sh 未产出 {real}',
                               return_code=1, reason='版本化动态库链接结果缺失')

        for link in links:
            if os.path.exists(link) or os.path.islink(link):
                os.remove(link)
            os.symlink(os.path.basename(real), link)
            print(f'符号链接：{link} -> {os.path.basename(real)}')

    def shared_lib_path(self):
        """共享库实际产出路径：配置了 version 就是 libX.so.<版本>，否则 libX.so"""
        if self.version != '':
            return f'{self.output_dir}/lib{self.project_name}.so.{self.version}'
        return f'{self.output_dir}/lib{self.project_name}.so'

    def rpath_args(self):
        """rpath 链接参数：每个路径一条 -Wl,-rpath,<path>"""
        return [f'-Wl,-rpath,{path}' for path in self.rpath]

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
            output = f'{self.output_dir}/lib{self.project_name}.a'
            args = ['csr', output] + objs
        elif self.target_type == TargetType.Shared:
            driver = self.link_driver()
            output = self.shared_lib_path()
            args = ['-shared', '-o', output] + objs
            # 版本化共享库：链接标上 soname（运行时按它查找，与文件名解耦）
            if self.version != '':
                soname = self.soname if self.soname != '' else f'lib{self.project_name}.so.{self.version.partition(".")[0]}'
                args += ['-Wl,-soname,' + soname]
            args += ['-lm'] + self.external.link_system_args + self.external.link_user_args
            args += self.pkg_libs
        else:
            driver = self.link_driver()
            output = f'{self.output_dir}/{self.project_name}'
            args = ['-s'] + objs
            args += ['-o', output, '-Wl,--add-needed', '-lc', '-lm']
            args += list(compile_args) + self.external.link_system_args + self.external.link_user_args
            args += self.pkg_libs

        # 消毒器、覆盖率与 rpath：链接阶段必须带上的运行时/查找路径
        if driver != 'ar':
            args += self.sanitize_args()
            if self.coverage:
                args += ['--coverage']
            args += self.rpath_args()

        return LinkJob(driver=driver, args=args,
                    output=output,
                    response_file=self.plan_response_file(driver, args))

    def sanitize_args(self):
        """消毒器参数：每个 -fsanitize=<item>，链接时带运行时（与编译一致）"""
        return [f'-fsanitize={item}' for item in self.sanitize]

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
            target = self.shared_lib_path()
            stem = os.path.basename(target)
            self.command.run_argv(['readelf', '-a', target], redirect_to=f'{log_dir}/readelf_{stem}.txt')
            self.command.run_argv(['ldd', target], redirect_to=f'{log_dir}/ldd_{stem}.txt')
            self.command.run_argv(['nm', '-ACD', target], redirect_to=f'{log_dir}/nm_{stem}.txt')
        elif self.target_type == TargetType.Static:
            target = f'{self.output_dir}/lib{self.project_name}.a'
            self.command.run_argv(['nm', '-g', target], redirect_to=f'{log_dir}/symbol_lib{self.project_name}.a.txt')
            self.command.run_argv(['ar', '-t', target], redirect_to=f'{log_dir}/archive_lib{self.project_name}.a.txt')
            self.command.run_argv(['objdump', '-x', target], redirect_to=f'{log_dir}/objdump_lib{self.project_name}.a.txt')
            self.command.run_argv(['strip', '--strip-unneeded', target])
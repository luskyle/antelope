from antelope.enums import *

class External():
    def __init__(self, project_name_global:str="", source_global:list=[],
                include_directories_global:list=[], target_type_global:TargetType=TargetType.Static,
                compiler_global:CompilerType=CompilerType.gxx, compiler_args_list_global:list=[],
                link_args_list_global:list=[], output_dir:str='.'):
        self.project_name = project_name_global
        self.source = list(source_global)
        self.include_directories = list(include_directories_global)
        self.target_type = target_type_global
        self.compiler = compiler_global
        self.compile_args_list = list(compiler_args_list_global)
        self.link_args_list = list(link_args_list_global)
        self.link_system_args = ""
        self.link_user_args = ""
        self.output_dir = output_dir

        """
        要编译的文件
        """
        self.compile_files = []

        """
        要编译的 object
        """
        self.obj_files = []

        """
        要编译的 文件路径（无后缀）-文件后缀 组成的字典
        """
        self.compile_files_map = {}

        """
        要编译的 object-文件路径（包含后缀） 组成的字典
        """
        self.compile_obj_files_map = {}
        self.buildType = BuildType.Unknown

    def parse_source(self, input_src:list):
        self.compile_files = []
        self.obj_files = []
        self.compile_files_map = {}
        self.compile_obj_files_map = {}

        for item in input_src:
            self.parse_compile_files('.c', item)
            self.parse_compile_files('.cc', item)
            self.parse_compile_files('.cpp', item)

    def parse_include_directories(self):
        """解析包含参数"""
        include_dirs = ""
        for item in self.include_directories:
            include_dirs += '-I ' + item + ' '
        return include_dirs

    def parse_link_args(self):
        """解析链接参数"""
        args = ""
        self.link_system_args = ""
        self.link_user_args = ""

        for item in self.link_args_list:
            if str(item).startswith('-l'):
                self.link_system_args += item + ' '
            else:
                self.link_user_args += item + ' '
            args += item + ' '
        return args

    def parse_compile_files(self, suffix:str, fileItem:str):
        if fileItem.endswith(suffix):
            self.compile_files.append(fileItem)
            obj = fileItem.replace('/', '_').replace(suffix, '.o')
            self.obj_files.append(obj)
            self.compile_files_map.update({obj.replace('.o', ''):suffix})
            self.compile_obj_files_map.update({obj:fileItem})

    def parse_compile_args(self):
        """解析编译参数"""
        args = ""
        for item in self.compile_args_list:
            args += item + ' '
        return args
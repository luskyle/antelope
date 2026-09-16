from antelope.os_ops.command import *
from antelope.os_ops.dir import *

class Analyzor():
    def __init__(self, output_dir:str='.'):
        self.dir = Directory()
        self.command = Command()
        self.output_dir = output_dir

    def analyze_obj(self, objects_args:list):
        """对指定的源文件生成其目标文件的分析报告"""
        for fileItem in objects_args:
            for suffix in ('.c', '.cc', '.cpp'):
                if fileItem.endswith(suffix):
                    obj = fileItem.replace('/', '_').replace(suffix, '.o')
                    log_dir = f'{self.output_dir}/log/{obj}'
                    self.dir.ClearMakeDirectory(log_dir)
                    self.command.run_argv(['objdump', '-x', f'{self.output_dir}/obj/{obj}'],
                                        redirect_to=f'{log_dir}/objdump-x')
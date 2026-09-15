import os
from antelope.os_ops.dir import *

class Analyzor():
    def __init__(self, output_dir:str='.'):
        self.dir = Directory()
        self.output_dir = output_dir

    def analyze_obj(self, objects_args:list):
        for fileItem in objects_args:
            suffix = str(fileItem).split('.')[1]
            if fileItem.endswith('.c'):
                obj = fileItem.replace('/', '_').replace('.c', '.o')
                self.dir.ClearMakeDirectory(f'{self.output_dir}/log/{obj}')
                os.system(f'objdump -x {self.output_dir}/obj/{obj}>{self.output_dir}/log/{obj}/objdump-x')
            elif fileItem.endswith('.cc'):
                obj = fileItem.replace('/', '_').replace('.cc', '.o')
                self.dir.ClearMakeDirectory(f'{self.output_dir}/log/{obj}')
                os.system(f'objdump -x {self.output_dir}/obj/{obj}>{self.output_dir}/log/{obj}/objdump-x')
            elif fileItem.endswith('.cpp'):
                obj = fileItem.replace('/', '_').replace('.cpp', '.o')
                self.dir.ClearMakeDirectory(f'{self.output_dir}/log/{obj}')
                os.system(f'objdump -x {self.output_dir}/obj/{obj}>{self.output_dir}/log/{obj}/objdump-x')
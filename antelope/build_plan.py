import json
import os
import shlex

class CompileUnit():
    """一个编译单元：源文件、目标文件、依赖文件、编译器驱动与结构化参数"""

    def __init__(self, source:str, obj:str, dep:str='', driver:str='', args:list=[]):
        self.source = source
        self.obj = obj
        self.dep = dep
        self.driver = driver
        self.args = list(args)

    def argv(self):
        """可直接执行的参数列表"""
        return [self.driver] + self.args

    def render(self):
        """审计用的 shell 文本"""
        return shlex.join(self.argv())

    def compileCommand(self, directory:str):
        """compile_commands.json 的一条记录，优先给结构化的 arguments"""
        return {
            'directory': directory,
            'file': self.source,
            'output': self.obj,
            'arguments': self.argv(),
        }

class LinkJob():
    """一次链接：驱动、结构化参数、产出与可选的响应文件"""

    def __init__(self, driver:str='', args:list=[], output:str='', response_file:str=''):
        self.driver = driver
        self.args = list(args)
        self.output = output
        self.response_file = response_file

    def argv(self):
        argv = [self.driver] + self.args
        if self.response_file != '':
            argv.append('@' + self.response_file)
        return argv

    def responseContent(self):
        """响应文件内容：每行一个参数，gcc 会按空白切分"""
        return '\n'.join(self.args) + '\n'

    def script(self):
        """落盘的链接脚本：既是审计产物，也是实际执行的内容"""
        return '#!/usr/bin/bash\n' + shlex.join(self.argv()) + '\n'

class BuildPlan():
    """一次构建的完整计划"""

    def __init__(self, units:list=[], link:LinkJob=None, jobs:int=1, backend:str='antel'):
        self.units = units
        self.link = link
        self.jobs = jobs
        self.backend = backend

    def renderUnits(self):
        return [unit.render() + '\n' for unit in self.units]

def compileCommands(units:list, directory:str):
    """compile_commands.json 的完整内容（优先结构化 arguments，字符串形态在含空格路径上不可靠）"""
    return [unit.compileCommand(directory) for unit in units]

def writeCompileCommands(path:str, units:list, directory:str):
    """写出 compile_commands.json，供 clangd 等工具解析"""
    parent = os.path.dirname(path)
    if parent != '':
        os.makedirs(parent, exist_ok=True)

    with open(path, 'w') as file:
        json.dump(compileCommands(units, directory), file, indent=2, ensure_ascii=False)
    return path
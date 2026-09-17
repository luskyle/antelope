import os
import shlex

from antelope.build_plan import *
from antelope.errors import *
from antelope.os_ops.command import *

RULE_FILE_NAME = 'antel.mk'
GENERATED_MARKER = '# 由 antel 生成，请勿手改（每次构建重建；它不是交付物，只是 make 的输入）'
RECIPE_INDENT = '\t'

def ruleFilePath(output_dir:str):
    """内部规则文件的位置：与 log/<项目名>_link.sh 同构，凡真正执行的东西一律落盘留档"""
    return f'{output_dir}/log/{RULE_FILE_NAME}'

def escapePath(path:str):
    """make 语法里目标名与依赖名的转义：$ 翻倍，空格、制表符与 # 加反斜杠"""
    return path.replace('$', '$$').replace(' ', '\\ ').replace('\t', '\\\t').replace('#', '\\#')

def escapeRecipe(argv:list):
    """
    渲染 recipe 行：先按 shell 规则转义（shlex），再把 $ 翻倍。
    make 会先吃掉一层 $ —— 实测 '-Wl,-rpath,$ORIGIN' 不翻倍会变成 '-Wl,-rpath,RIGIN'
    """
    return shlex.join(argv).replace('$', '$$')

def renderRuleText(plan:BuildPlan):
    """把 BuildPlan 渲染成 make 规则文件的内容"""
    lines = [GENERATED_MARKER, '']

    if plan.link is not None:
        lines += ['.PHONY: all', f'all: {escapePath(plan.link.output)}', '']

    # 目标失败时不留半成品，避免下次被当成"已构建"
    lines += ['.DELETE_ON_ERROR:', '']

    for unit in plan.units:
        # 逐单元显式规则：目标名是扁平化的（src/main.c → obj/src_main.o），模式规则表达不了
        lines += [f'{escapePath(unit.obj)}: {escapePath(unit.source)}',
                  f'{RECIPE_INDENT}@mkdir -p $(dir $@)',
                  f'{RECIPE_INDENT}{escapeRecipe(unit.argv())}', '']

    if plan.link is not None:
        objs = ' '.join(escapePath(unit.obj) for unit in plan.units)
        lines += [f'{escapePath(plan.link.output)}: {objs}',
                  f'{RECIPE_INDENT}{escapeRecipe(plan.link.argv())}', '']

    deps = ' '.join(escapePath(f'{unit.obj}.d') for unit in plan.units)
    if deps != '':
        lines += ['# 只为"有人手工跑这个文件"保留依赖语义；antel 调用时会先删目标，不依赖它',
                  f'-include {deps}', '']

    return '\n'.join(lines)

class MakeRunner():
    """用 make 执行编译：antel 决定编什么，make 只负责并行编完"""

    def __init__(self, output_dir:str, project_name:str, jobs:int=1):
        self.output_dir = output_dir
        self.project_name = project_name
        self.jobs = jobs
        self.command = Command()

    def run(self, plan:BuildPlan, stale_objs:list):
        """写规则文件 → 删掉本轮过期目标 → 交给 make 并行重建"""
        path = ruleFilePath(self.output_dir)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as file:
            file.write(renderRuleText(plan))
        print(f'规则文件已更新：{path}')

        self.removeStaleObjects(stale_objs)

        argv = ['make', '-f', path, f'-j{max(1, self.jobs)}'] + list(stale_objs)
        log_file = f'{self.output_dir}/log/{self.project_name}.make'
        try:
            self.command.run_argv(argv, redirect_to=log_file, echo=True)
        except CommandError as error:
            raise CommandError(error.command, error.return_code, error.output,
                            reason=f'make 执行失败，规则文件：{path}')
        return path

    def removeStaleObjects(self, stale_objs:list):
        """
        先删掉过期目标再交给 make：make 按 mtime 判定，
        实测"已是最新的目标"会被直接跳过（输出'已是最新'），而按 hash 判定它们确实过期
        """
        for obj in stale_objs:
            if os.path.exists(obj):
                os.remove(obj)
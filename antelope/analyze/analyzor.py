"""可视化分析报告：antel analyze 生成单文件 HTML 报告。

报告是自包含的（内联 CSS，无外部依赖），浏览器打开即可看：
项目配置摘要、源码清单、编译命令、日志产物、目标符号表、产物大小。
"""

import html
import json
import os

from antelope.os_ops.command import *
from antelope.os_ops.dir import *


class Analyzor():
    def __init__(self, output_dir:str='.'):
        self.dir = Directory()
        self.command = Command()
        self.output_dir = output_dir

    def analyze_obj(self, antel, objects_args:list):
        """收集项目信息并生成可视化报告"""
        report = self.collect(antel, objects_args)
        path = f'{self.output_dir}/report.html'
        with open(path, 'w', encoding='utf-8') as file:
            file.write(render_report(report))
        print(f'报告已生成：{path}')
        return path

    # ---- 数据收集 ----

    def collect(self, antel, objects_args:list):
        """把项目当前状态整理成结构化数据，供报告模板渲染"""
        return {
            'project': self.project_summary(antel),
            'sources': self.source_sections(antel),
            'targets': self.target_sections(antel),
            'compile_commands': self.compile_commands(),
            'logs': self.log_files(),
        }

    def project_summary(self, antel):
        return {
            'projectName': antel.project_name,
            'target_type': antel.target_type.name,
            'compiler': antel.compiler_type.name,
            'jobs': antel.jobs,
            'backend': antel.backend,
            'config': f'{antel.project_name}_{os.path.basename(antel.output_dir)}',
        }

    def source_sections(self, antel):
        """每个源文件的目标符号（nm -g），用于可视化符号分布。
        自动覆盖配置中的全部源文件，无需额外填 analyze_files"""
        sections = []
        for item in antel.source:
            for suffix in ('.c', '.cc', '.cpp'):
                if item.endswith(suffix):
                    obj = item.replace('/', '_').replace(suffix, '.o')
                    sections.append(self.symbols_of(obj, item))
        return sections

    def symbols_of(self, obj:str, source:str):
        """一个目标文件的全量符号（nm），按段类型分组"""
        obj_path = f'{self.output_dir}/obj/{obj}'
        if not os.path.exists(obj_path):
            return {'source': source, 'exists': False, 'symbols': []}

        output = self.command.run_argv(['nm', '-n', obj_path], capture=True)
        symbols = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            symbols.append({'addr': parts[0], 'type': parts[1], 'name': ' '.join(parts[2:])})
        return {'source': source, 'exists': True, 'symbols': symbols}

    def target_sections(self, antel):
        """构建产物（可执行/库）的符号与大小"""
        targets = []

        # exe / shared 的导出与依赖在 log/readelf_*、ldd_*、nm_*
        for name in sorted(os.listdir(f'{self.output_dir}/log')) if os.path.exists(f'{self.output_dir}/log') else []:
            if name.startswith(('nm_', 'ldd_', 'readelf_')):
                with open(f'{self.output_dir}/log/{name}', encoding='utf-8', errors='replace') as file:
                    targets.append({'file': name, 'content': file.read()})
        return targets

    def compile_commands(self):
        """compile_commands.json 里的编译命令清单"""
        path = f'{self.output_dir}/compile_commands.json'
        if not os.path.exists(path):
            return []
        with open(path, encoding='utf-8') as file:
            return json.load(file)

    def log_files(self):
        """log/ 目录下的产物清单（文件名 + 大小）"""
        log_dir = f'{self.output_dir}/log'
        if not os.path.exists(log_dir):
            return []
        entries = []
        for name in sorted(os.listdir(log_dir)):
            full = f'{log_dir}/{name}'
            if os.path.isfile(full):
                entries.append({'name': name, 'size': os.path.getsize(full)})
        return entries


def render_report(report:dict) -> str:
    """渲染单文件 HTML 报告（自包含，无外部依赖）"""
    project = report['project']

    source_rows = ''
    total_symbols = 0
    for section in report['sources']:
        if not section['exists']:
            source_rows += f'<tr><td class="name">{html.escape(section["source"])}</td>' \
                           f'<td colspan="3" class="warn">目标文件缺失（未编译）</td></tr>'
            continue
        total_symbols += len(section['symbols'])
        detail = ' '.join(html.escape(s['type']) + '&nbsp;' + html.escape(s['name'])
                          for s in section['symbols'][:80])
        source_rows += (f'<tr><td class="name">{html.escape(section["source"])}</td>'
                        f'<td>{len(section["symbols"])}</td>'
                        f'<td rowspan="1" class="mono">{detail}</td></tr>')

    target_rows = ''
    for target in report['targets']:
        preview = html.escape(target['content'][:600])
        target_rows += (f'<details><summary>{html.escape(target["file"])}'
                        f'（{len(target["content"])} 字节）</summary>'
                        f'<pre>{preview}</pre></details>')

    command_rows = ''
    for entry in report['compile_commands']:
        argv = ' '.join(entry.get('arguments', []))
        command_rows += (f'<tr><td class="mono">{html.escape(entry.get("file", ""))}</td>'
                         f'<td class="mono wrap">{html.escape(argv)}</td></tr>')

    log_rows = ''
    for entry in report['logs']:
        log_rows += f'<tr><td class="mono">{html.escape(entry["name"])}</td><td>{entry["size"]}</td></tr>'

    return f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(project['projectName'])} — antel 分析报告</title>
<style>
:root {{ color-scheme: dark; }}
body {{ margin: 0; background: #0f172a; color: #e2e8f0;
       font: 14px/1.6 "DejaVu Sans", system-ui, sans-serif; }}
.wrap {{ max-width: 1080px; margin: 0 auto; padding: 24px 20px 60px; }}
h1 {{ font-size: 22px; margin: 0 0 4px; }}
.sub {{ color: #94a3b8; margin-bottom: 20px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px; margin-bottom: 24px; }}
.card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 12px 16px; }}
.card .k {{ color: #94a3b8; font-size: 12px; }}
.card .v {{ font-size: 18px; font-weight: 700; color: #67e8f9; }}
h2 {{ font-size: 16px; margin: 24px 0 10px; padding-bottom: 6px;
     border-bottom: 1px solid #334155; }}
table {{ width: 100%; border-collapse: collapse; background: #1e293b;
        border: 1px solid #334155; border-radius: 10px; overflow: hidden; }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #262f43;
         vertical-align: top; }}
th {{ background: #243047; color: #cbd5e1; font-weight: 600; font-size: 13px; }}
.mono {{ font-family: "DejaVu Sans Mono", monospace; font-size: 12px; }}
.wrap {{ word-break: break-all; }}
.name {{ white-space: nowrap; }}
.warn {{ color: #fbbf24; }}
details {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
          padding: 8px 12px; margin-bottom: 8px; }}
summary {{ cursor: pointer; color: #7dd3fc; }}
pre {{ white-space: pre-wrap; word-break: break-all; margin: 8px 0 0;
      font-size: 12px; color: #cbd5e1; }}
a {{ color: #7dd3fc; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{html.escape(project['projectName'])} — 分析报告</h1>
  <div class="sub">输出目录：{html.escape(project['config'])}</div>

  <div class="grid">
    <div class="card"><div class="k">目标类型</div><div class="v">{html.escape(project['target_type'])}</div></div>
    <div class="card"><div class="k">编译器</div><div class="v">{html.escape(project['compiler'])}</div></div>
    <div class="card"><div class="k">并行度</div><div class="v">{project['jobs']}</div></div>
    <div class="card"><div class="k">执行器</div><div class="v">{html.escape(project['backend'])}</div></div>
    <div class="card"><div class="k">源文件</div><div class="v">{len(report['sources'])}</div></div>
    <div class="card"><div class="k">符号总数</div><div class="v">{total_symbols}</div></div>
  </div>

  <h2>目标符号表</h2>
  <table>
    <tr><th>源文件</th><th>符号数</th><th>符号（前 80 个）</th></tr>
    {source_rows}
  </table>

  <h2>编译命令（compile_commands.json）</h2>
  <table>
    <tr><th>源文件</th><th>命令</th></tr>
    {command_rows if command_rows else '<tr><td colspan="2">未生成 compile_commands.json</td></tr>'}
  </table>

  <h2>构建产物分析</h2>
  {target_rows if target_rows else '<div class="sub">构建后才有符号表/动态依赖分析（log/ 下 nm_*、ldd_*、readelf_*）</div>'}

  <h2>日志产物</h2>
  <table>
    <tr><th>文件</th><th>大小（字节）</th></tr>
    {log_rows if log_rows else '<tr><td colspan="2">log/ 为空</td></tr>'}
  </table>
</div>
</body>
</html>
'''
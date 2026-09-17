"""可视化分析报告：antel analyze / report: true 生成单文件 HTML 报告。

报告是自包含的（内联 CSS，无外部依赖），浏览器打开即可看。分析维度：

1. 项目与产物摘要：配置、目标、产物文件与大小
2. 增量状态：hash 基线、本次变化文件、待重编文件
3. 编译参数统计：-O / -std / -D / -W / -I 的词频
4. 符号分类：按 nm 段类型分组（T 函数、D/B 数据、U 未定义…）
5. 目标文件大小分布：CSS 条形图
6. 头文件依赖：从 -MMD 的 .d 文件反推出每个源文件的头文件依赖
7. 动态依赖：exe/shared 的 NEEDED（readelf）与 ldd 结果
8. 日志产物清单
"""

import html
import json
import os
import time

from antelope.enums import *
from antelope.os_ops.command import *
from antelope.resources import symbolName as symbol_name


class Analyzor():
    def __init__(self, output_dir:str='.'):
        self.command = Command()
        self.output_dir = output_dir

    def analyze_obj(self, antel, objects_args:list=[]):
        """收集项目信息并生成可视化报告"""
        report = self.collect(antel)
        path = f'{self.output_dir}/report.html'
        with open(path, 'w', encoding='utf-8') as file:
            file.write(render_report(report))
        print(f'报告已生成：{path}')
        return path

    # ---- 数据收集 ----

    def collect(self, antel) -> dict:
        target = self.target_path(antel)
        return {
            'project': self.project_summary(antel),
            'source_count': len(antel.source),
            'target': self.target_info(antel, target),
            'incremental': self.incremental_status(),
            'flags': self.compile_flag_stats(),
            'symbols': self.symbol_sections(antel),
            'objects': self.object_sizes(),
            'dependencies': self.dependency_map(antel),
            'dynamic': self.dynamic_deps(target),
            'resources': self.resource_info(antel),
            'compile_commands': self.compile_commands(),
            'logs': self.log_files(),
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        }

    def resource_info(self, antel) -> dict:
        """
        资源明细：把每个资源文件展开成一行独立分析。
        行字段：形态 / 资源路径 / 类型（file 探测）/ 大小 / 状态 / 详情。
        """
        rows = []

        # ---- data_files：目录整体复制时展开到文件级 ----
        for entry in getattr(antel, 'data_files', []):
            source = entry['from']
            target = f'{self.output_dir}/{entry["to"]}'
            target_exists = os.path.exists(target)

            files = []
            if os.path.isdir(source):
                for root, dirs, names in os.walk(source):
                    for name in sorted(names):
                        full = os.path.join(root, name)
                        rel = os.path.relpath(full, source)
                        files.append({'rel': rel, 'source': full,
                                      'copied': os.path.exists(f'{self.output_dir}/{entry["to"]}/{rel}')})
            else:
                files.append({'rel': os.path.basename(source), 'source': source,
                              'copied': target_exists and os.path.isfile(target)})

            if not files:
                rows.append(self._resource_row('data_files', source, '—',
                                               '目录为空', '未复制', ''))
                continue

            for item in files:
                kind, size = self._probe(item['source'])
                state = '✓ 已复制' if item['copied'] else '✗ 未复制'
                target_path = f'{entry["to"]}/{item["rel"]}'
                detail = f'复制到 {target_path}'
                rows.append(self._resource_row('data_files', item['rel'], kind, size, state, detail))

        # ---- gresource：XML 与每个引用文件分开 ----
        if getattr(antel, 'gresource', '') != '':
            xml_kind, xml_size = self._probe(antel.gresource)
            rows.append(self._resource_row('gresource', antel.gresource, xml_kind, xml_size,
                                           '✓ XML 存在' if os.path.exists(antel.gresource) else '✗ XML 缺失',
                                           '资源清单'))

            generated = f'{self.output_dir}/gresource.c'
            generated_ok = os.path.exists(generated)
            inputs = antel.resource.gresource_inputs() if hasattr(antel.resource, 'gresource_inputs') else []
            for path in inputs:
                if path == antel.gresource:
                    continue
                kind, size = self._probe(path)
                detail = f'前缀 {self._gresource_prefix(antel.gresource)}（未编译前资源文件）'
                rows.append(self._resource_row('gresource', os.path.basename(path), kind, size,
                                               '✓ 已编入' if generated_ok else '✗ 未生成',
                                               detail))
            if generated_ok:
                rows.append(self._resource_row('gresource', 'gresource.c', 'C 源码',
                                               os.path.getsize(generated), '✓ 生成物',
                                               '编译进可执行文件（单文件分发）'))

        # ---- embed：每个嵌入文件一行 ----
        for index, embed in enumerate(getattr(antel, 'embeds', [])):
            obj = f'{self.output_dir}/obj/embed_{index}.o'
            kind, size = self._probe(embed)
            state = '✓ 已嵌入' if os.path.exists(obj) else \
                    ('✗ 未嵌入' if os.path.exists(embed) else '✗ 源缺失')
            rows.append(self._resource_row('embed', embed, kind, size, state,
                                           f'符号 {symbol_name(embed)}'))

        return rows

    def _resource_row(self, form:str, path:str, kind, size, state:str, detail:str) -> dict:
        return {'form': form, 'path': path, 'kind': kind,
                'size': size, 'state': state, 'detail': detail}

    def _probe(self, path:str):
        """文件类型（file 命令首段）与大小；缺失时返回 ('—', 0)"""
        if not os.path.exists(path) or not os.path.isfile(path):
            return '—', 0
        size = os.path.getsize(path)
        kind = ''
        try:
            out = self.command.run_argv(['file', '-b', '-L', path], capture=True)
            kind = out.strip().split(',')[0] if out.strip() else ''
        except Exception:
            pass
        return kind, size

    def _gresource_prefix(self, xml:str) -> str:
        """从 gresource.xml 里读 <gresource prefix>，找不到给个通用说明"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.parse(xml).getroot()
            for g in root.iter('gresource'):
                prefix = g.get('prefix')
                if prefix:
                    return prefix
        except Exception:
            pass
        return 'gresource://'

    def target_path(self, antel) -> str:
        """当前配置的生成目标路径（exe / 静态库 / 共享库）"""
        if antel.target_type == TargetType.Executable:
            return f'{self.output_dir}/{antel.project_name}'
        if antel.target_type == TargetType.Static:
            return f'{self.output_dir}/lib{antel.project_name}.a'
        # Shared：优先版本化文件，否则 libX.so
        base = f'{self.output_dir}/lib{antel.project_name}'
        versioned = getattr(antel, 'version', '') or ''
        if versioned != '':
            return f'{base}.so.{versioned}'
        return f'{base}.so'

    def project_summary(self, antel) -> dict:
        return {
            'projectName': antel.project_name,
            'target_type': antel.target_type.name,
            'compiler': antel.compiler_type.name,
            'jobs': antel.jobs,
            'backend': antel.backend,
            'report': bool(getattr(antel, 'report', False)),
            'config': os.path.basename(antel.output_dir),
        }

    def target_info(self, antel, target:str) -> dict:
        """产物文件信息：存在性、大小、类型（file 命令）"""
        if not os.path.exists(target):
            return {'path': target, 'exists': False, 'size': 0, 'kind': ''}
        kind = ''
        try:
            out = self.command.run_argv(['file', '-b', target], capture=True)
            kind = out.strip().split(',')[0] if out.strip() else ''
        except Exception:
            pass
        return {'path': target, 'exists': True, 'size': os.path.getsize(target), 'kind': kind}

    def incremental_status(self) -> dict:
        """增量状态：基线是否存在、本次变化（hashes_diff）、待重编（stale_files）"""
        log_dir = f'{self.output_dir}/log'
        status = {'has_baseline': False, 'changed': [], 'stale': []}

        hashes = f'{log_dir}/hashes'
        if os.path.exists(hashes):
            status['has_baseline'] = os.path.getsize(hashes) > 0

        changed = f'{log_dir}/hashes_diff'
        if os.path.exists(changed):
            try:
                with open(changed, encoding='utf-8') as file:
                    data = json.load(file)
                status['changed'] = list(data.keys())
            except (json.JSONDecodeError, ValueError):
                pass

        stale = f'{log_dir}/stale_files'
        if os.path.exists(stale):
            with open(stale, encoding='utf-8') as file:
                status['stale'] = [line.strip().strip("'") for line in file
                                   if line.strip() != '']
        return status

    def compile_flag_stats(self) -> dict:
        """从 compile_commands.json 统计编译参数词频：-O / -std / -D / -W / -I / -f / 其他"""
        counts = {'-O': {}, '-std': {}, '-D': {}, '-W': {}, '-I': {}, '-f': {}, 'other': {}}
        for entry in self.compile_commands():
            args = entry.get('arguments', [])
            for arg in args:
                if not isinstance(arg, str):
                    continue
                for prefix, bucket in (('-O', '-O'), ('-std', '-std'), ('-D', '-D'),
                                       ('-W', '-W'), ('-I', '-I'), ('-f', '-f')):
                    if arg.startswith(prefix) and arg != '-c' and arg != '-o':
                        bucket = counts.get(bucket if prefix != '-O' else '-O', {})
                        bucket[arg] = bucket.get(arg, 0) + 1
                        break
                else:
                    if arg.startswith('-') and arg not in ('-c', '-o', '-MMD', '-MF'):
                        key = arg if len(arg) <= 20 else arg[:17] + '...'
                        counts['other'][key] = counts['other'].get(key, 0) + 1
        return counts

    def symbol_sections(self, antel) -> list:
        """每个源文件的符号分类统计 + 明细"""
        sections = []
        for item in antel.source:
            for suffix in ('.c', '.cc', '.cpp'):
                if item.endswith(suffix):
                    obj = item.replace('/', '_').replace(suffix, '.o')
                    sections.append(self.symbols_of(obj, item))
        return sections

    def symbols_of(self, obj:str, source:str) -> dict:
        """一个目标文件的符号：按 nm 类型分组计数，附前 N 个明细"""
        obj_path = f'{self.output_dir}/obj/{obj}'
        if not os.path.exists(obj_path):
            return {'source': source, 'exists': False, 'groups': {}, 'total': 0, 'symbols': []}

        output = self.command.run_argv(['nm', '-n', obj_path], capture=True)
        groups = {}
        symbols = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            kind, name = parts[1], ' '.join(parts[2:])
            label = {
                'T': '函数 (T)', 't': '内部函数 (t)', 'D': '全局数据 (D)',
                'd': '局部数据 (d)', 'B': 'BSS 数据 (B)', 'b': '局部 BSS (b)',
                'R': '只读数据 (R)', 'U': '未定义引用 (U)', 'A': '绝对符号 (A)',
            }.get(kind, kind)
            if label not in groups:
                groups[label] = 0
            groups[label] += 1
            symbols.append((kind, name))

        total = len(symbols)
        # 优先展示有意义的符号（函数/数据/未定义），去掉调试区段细节
        interesting = [s for s in symbols if s[0] in 'TtDdBbRU']
        return {'source': source, 'exists': True, 'groups': groups,
                'total': total, 'symbols': interesting[:100]}

    def object_sizes(self) -> list:
        """obj/ 下所有目标文件的路径与大小（含依赖文件排除）"""
        obj_dir = f'{self.output_dir}/obj'
        if not os.path.exists(obj_dir):
            return []
        sizes = []
        for name in sorted(os.listdir(obj_dir)):
            if name.endswith('.o'):
                full = f'{obj_dir}/{name}'
                sizes.append({'name': name, 'size': os.path.getsize(full)})
        return sizes

    def dependency_map(self, antel) -> list:
        """头文件依赖：读每个编译单元的 .d 文件，给出 源文件 → 依赖的头文件"""
        rows = []
        for item in antel.source:
            for suffix in ('.c', '.cc', '.cpp'):
                if item.endswith(suffix):
                    obj = item.replace('/', '_').replace(suffix, '.o')
                    deps = self.read_dep_file(f'{self.output_dir}/obj/{obj}.d')
                    rows.append({'source': item, 'deps': deps})
        return rows

    def read_dep_file(self, dep_file:str) -> list:
        """解析 -MMD 依赖文件中的头文件路径（排除目标自身与主源文件）"""
        if not os.path.exists(dep_file):
            return []
        with open(dep_file, encoding='utf-8', errors='replace') as file:
            content = file.read()
        content = content.replace('\\\n', ' ')
        dependencies = content.partition(':')[2].split()
        return dependencies

    def dynamic_deps(self, target:str) -> dict:
        """动态依赖：readelf -d 的 NEEDED 列表 + ldd 解析结果（exe/shared）"""
        if not os.path.exists(target):
            return {'needed': [], 'ldd': []}

        needed = []
        try:
            out = self.command.run_argv(['readelf', '-d', target], capture=True)
            for line in out.splitlines():
                if 'NEEDED' in line and '[' in line:
                    lib = line.partition('[')[2].partition(']')[0]
                    needed.append(lib)
        except Exception:
            pass

        ldd = []
        try:
            out = self.command.run_argv(['ldd', target], capture=True)
            for line in out.splitlines():
                if '=>' in line:
                    ldd.append(line.strip())
                elif 'not found' in line:
                    ldd.append(line.strip())
        except Exception:
            pass
        return {'needed': needed, 'ldd': ldd}

    def compile_commands(self) -> list:
        path = f'{self.output_dir}/compile_commands.json'
        if not os.path.exists(path):
            return []
        with open(path, encoding='utf-8') as file:
            return json.load(file)

    def log_files(self) -> list:
        log_dir = f'{self.output_dir}/log'
        if not os.path.exists(log_dir):
            return []
        entries = []
        for name in sorted(os.listdir(log_dir)):
            full = f'{log_dir}/{name}'
            if os.path.isfile(full):
                entries.append({'name': name, 'size': os.path.getsize(full)})
        return entries


# ---- 渲染 ----

def esc(text) -> str:
    return html.escape(str(text))


def flag_table(counts:dict) -> str:
    """编译参数词频 → 5 列表格，突出高频项"""
    buckets = [('-O 优化级别', counts['-O'], 3), ('-std 语言标准', counts['-std'], 20),
               ('-D 宏定义', counts['-D'], 20), ('-W 警告', counts['-W'], 20),
               ('-f 特性开关', counts['-f'], 20)]
    rows = ''
    for title, bucket, show in buckets:
        items = sorted(bucket.items(), key=lambda kv: -kv[1])[:show]
        if not items:
            continue
        chips = ' '.join(f'<span class="chip">{esc(k)}×{v}</span>' for k, v in items)
        rows += f'<tr><td>{title}</td><td>{chips}</td></tr>'
    if rows == '':
        return '<tr><td colspan="2">未启用额外编译参数</td></tr>'
    return rows


def scaled(size:int) -> str:
    """文件大小的人类可读表示：B / KB / MB"""
    if size < 1024:
        return f'{size} B'
    if size < 1024 * 1024:
        return f'{size / 1024:.1f} KB'
    return f'{size / (1024 * 1024):.2f} MB'


def object_bar(objects:list) -> str:
    """目标文件大小条形图（纯 CSS），右侧标注带单位的大小"""
    if not objects:
        return '<div class="sub">无目标文件</div>'
    max_size = max(item['size'] for item in objects) or 1
    rows = ''
    for item in objects:
        pct = int(item['size'] * 100 / max_size)
        rows += (f'<div class="bar-row"><span class="bar-name">{esc(item["name"])}</span>'
                 f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>'
                 f'<span class="bar-size">{scaled(item["size"])}</span></div>')
    return rows


def resource_section(rows:list) -> str:
    """资源明细表：每个资源文件一行（形态 / 路径 / 类型 / 大小 / 状态 / 详情）"""
    if not rows:
        return ''

    trs = ''
    for r in rows:
        state_class = 'ok' if r['state'].startswith('✓') else 'warn'
        trs += (f'<tr>'
                f'<td class="name">{esc(r["form"])}</td>'
                f'<td class="mono small">{esc(r["path"])}</td>'
                f'<td class="small">{esc(r["kind"])}</td>'
                f'<td>{scaled(r["size"])}</td>'
                f'<td class="{state_class}">{esc(r["state"])}</td>'
                f'<td class="small">{esc(r["detail"])}</td>'
                f'</tr>')

    forms = sorted({r['form'] for r in rows})
    total = sum(r['size'] for r in rows if r['path'] != 'gresource.c')
    summary = ' · '.join(f'<code>{esc(f)}</code> {sum(1 for r in rows if r["form"] == f)} 项' for f in forms)

    return (f'  <h2>资源情况</h2>\n'
            f'  <div class="sub">共 {len(rows)} 个资源文件 · 资源总体积 {scaled(total)} · {summary}</div>\n'
            f'  <table>\n'
            f'    <tr><th>形态</th><th>资源</th><th>类型</th><th>大小</th><th>状态</th><th>详情</th></tr>\n'
            f'    {trs}\n'
            f'  </table>')


def render_report(report:dict) -> str:
    p = report['project']
    target = report['target']
    inc = report['incremental']
    flags = report['flags']

    # 摘要卡片
    size_kb = f'{target["size"] / 1024:.1f} KB' if target['exists'] else '未生成'
    cards = [
        ('目标类型', esc(p['target_type'])),
        ('编译器', esc(p['compiler'])),
        ('并行度', str(p['jobs'])),
        ('执行器', esc(p['backend'])),
        ('源文件', str(report['source_count'])),
        ('产物大小', size_kb),
    ]
    card_html = ''.join(f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div></div>'
                        for k, v in cards)

    # 增量状态
    inc_rows = ''
    if inc['has_baseline']:
        inc_rows += '<div class="ok">✓ hash 基线存在（上次构建成功，增量可用）</div>'
    else:
        inc_rows += '<div class="warn">✗ hash 基线缺失（下次 build 会全量）</div>'
    if inc['changed']:
        inc_rows += ('<div class="sub">本次相对基线变化：' +
                     ' '.join(f'<code>{esc(f)}</code>' for f in inc['changed']) + '</div>')
    if inc['stale']:
        inc_rows += ('<div class="sub">待重编：' +
                     ' '.join(f'<code>{esc(f)}</code>' for f in inc['stale']) + '</div>')

    # 符号表
    symbol_rows = ''
    total_symbols = sum(s['total'] for s in report['symbols'] if s['exists'])
    for section in report['symbols']:
        if not section['exists']:
            symbol_rows += (f'<tr><td class="name">{esc(section["source"])}</td>'
                            f'<td class="warn" colspan="2">目标文件缺失（未编译）</td></tr>')
            continue
        group_text = ' '.join(f'<span class="group-chip">{esc(k)} <b>{v}</b></span>'
                              for k, v in section['groups'].items())
        detail = ' '.join(f'<code class="sym-chip">{esc(k)}&nbsp;{esc(n)}</code>'
                          for k, n in section['symbols'][:60])
        symbol_rows += (f'<tr><td class="name">{esc(section["source"])}</td>'
                        f'<td>{section["total"]}</td>'
                        f'<td class="small">{group_text}<br>{detail}</td></tr>')

    # 依赖表
    dep_rows = ''
    all_headers = set()
    for row in report['dependencies']:
        all_headers.update(row['deps'])
    for row in report['dependencies']:
        deps = ' '.join(f'<code>{esc(d)}</code>' for d in row['deps'])
        dep_rows += f'<tr><td class="name">{esc(row["source"])}</td><td>{deps or "—"}</td></tr>'

    # 编译命令
    command_rows = ''
    for entry in report['compile_commands']:
        argv = ' '.join(entry.get('arguments', []))
        command_rows += (f'<tr><td class="mono small">{esc(entry.get("file", ""))}</td>'
                         f'<td class="mono small wrap">{esc(argv)}</td></tr>')

    # 动态依赖
    dyn = report['dynamic']
    needed_html = ' '.join(f'<code>{esc(lib)}</code>' for lib in dyn['needed'])
    dyn_rows = ''
    for line in dyn['ldd']:
        dyn_rows += f'<div class="mono small">{esc(line)}</div>'

    # 日志
    log_rows = ''
    for entry in report['logs']:
        log_rows += (f'<tr><td class="mono small">{esc(entry["name"])}</td>'
                     f'<td>{scaled(entry["size"])}</td></tr>')

    # 资源情况（配置了才有区块）
    resource_html = resource_section(report['resources'])

    target_status = (f'<div class="ok">✓ 已生成 &nbsp;{esc(target["path"])}'
                     f'&nbsp;（{size_kb}）</div>') if target['exists'] else \
                    f'<div class="warn">✗ 尚未构建，目标不存在</div>'

    return f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(p['projectName'])} — antel 分析报告</title>
<style>
:root {{ color-scheme: dark; }}
body {{ margin: 0; background: #0f172a; color: #e2e8f0;
       font: 14px/1.6 "DejaVu Sans", system-ui, sans-serif; }}
.wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px 20px 60px; }}
h1 {{ font-size: 22px; margin: 0 0 4px; }}
.sub {{ color: #94a3b8; margin-bottom: 12px; }}
.meta {{ color: #64748b; font-size: 12px; margin-bottom: 20px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px; margin-bottom: 24px; }}
.card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 12px 16px; }}
.card .k {{ color: #94a3b8; font-size: 12px; }}
.card .v {{ font-size: 17px; font-weight: 700; color: #67e8f9; word-break: break-all; }}
h2 {{ font-size: 16px; margin: 28px 0 10px; padding-bottom: 6px;
     border-bottom: 1px solid #334155; }}
table {{ width: 100%; border-collapse: collapse; background: #1e293b;
        border: 1px solid #334155; border-radius: 10px; overflow: hidden; }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #262f43;
         vertical-align: top; }}
th {{ background: #243047; color: #cbd5e1; font-weight: 600; font-size: 13px; }}
.mono {{ font-family: "DejaVu Sans Mono", monospace; }}
.small {{ font-size: 12px; }}
.wrap {{ word-break: break-all; }}
.name {{ white-space: nowrap; }}
.ok {{ color: #4ade80; }}
.warn {{ color: #fbbf24; }}
code {{ background: #0f172a; border: 1px solid #334155; border-radius: 4px;
       padding: 0 5px; font-size: 12px; color: #7dd3fc; }}
.chip {{ display: inline-block; background: #0f172a; border: 1px solid #334155;
        border-radius: 999px; padding: 0 8px; margin: 1px; font-size: 12px;
        color: #a5b4fc; }}
.group-chip {{ display: inline-block; background: #1e293b; border: 1px solid #334155;
              border-radius: 6px; padding: 1px 8px; margin: 1px 2px 1px 0;
              font-size: 12px; color: #cbd5e1; }}
.group-chip b {{ color: #67e8f9; }}
.sym-chip {{ display: inline-block; background: #0f172a; border: 1px solid #334155;
            border-radius: 6px; padding: 1px 7px; margin: 2px 3px 2px 0;
            font-size: 12px; color: #e2e8f0; white-space: nowrap;
            font-family: "DejaVu Sans Mono", monospace; }}
.bar-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }}
.bar-name {{ width: 34%; font-size: 12px; white-space: nowrap; overflow: hidden;
            text-overflow: ellipsis; }}
.bar-track {{ flex: 1; background: #1e293b; border: 1px solid #334155; border-radius: 6px;
             height: 16px; overflow: hidden; }}
.bar-fill {{ background: linear-gradient(90deg, #0ea5e9, #67e8f9); height: 100%; }}
.bar-size {{ width: 70px; text-align: right; font-size: 12px; color: #94a3b8; }}
details {{ margin-bottom: 8px; }}
summary {{ cursor: pointer; color: #7dd3fc; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{esc(p['projectName'])} — 分析报告</h1>
  <div class="meta">输出目录 <code>{esc(p['config'])}</code> · 生成于 {esc(report['generated_at'])}</div>

  <div class="grid">{card_html}</div>

  <h2>产物</h2>
  {target_status}

  <h2>增量状态</h2>
  {inc_rows}

  <h2>编译参数统计</h2>
  <table>
    <tr><th>类别</th><th>使用情况</th></tr>
    {flag_table(flags)}
  </table>

  {resource_html}

  <h2>目标符号表（{total_symbols} 个符号）</h2>
  <table>
    <tr><th>源文件</th><th>符号数</th><th>分类与符号明细</th></tr>
    {symbol_rows}
  </table>

  <h2>头文件依赖</h2>
  <table>
    <tr><th>源文件</th><th>依赖的头文件</th></tr>
    {dep_rows}
  </table>

  <h2>目标文件大小分布</h2>
  {object_bar(report['objects'])}

  <h2>动态依赖</h2>
  <div class="sub">NEEDED：{needed_html if needed_html else '—'}</div>
  {dyn_rows if dyn_rows else '<div class="sub">目标未生成或为静态/归档，无动态依赖分析</div>'}

  <h2>编译命令</h2>
  <table>
    <tr><th>源文件</th><th>命令</th></tr>
    {command_rows if command_rows else '<tr><td colspan="2">未生成 compile_commands.json</td></tr>'}
  </table>

  <h2>日志产物</h2>
  <table>
    <tr><th>文件</th><th>大小</th></tr>
    {log_rows if log_rows else '<tr><td colspan="2">log/ 为空</td></tr>'}
  </table>
</div>
</body>
</html>
'''
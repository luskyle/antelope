"""antel analyze / report: 可视化分析报告测试。

报告是自包含的单文件 HTML（内联 CSS，无外部依赖），浏览器直接打开即可看。
report: true 时构建成功后自动生成；report 不影响编译（产物字节不变）。
"""

import os
import shutil

import pytest
from click.testing import CliRunner

from antelope.antelope import main
from conftest import write_config

pytestmark = pytest.mark.skipif(shutil.which('gcc') is None or shutil.which('g++') is None,
                                reason='需要 gcc/g++ 才能执行真实构建')


def antel(*args):
    return CliRunner().invoke(main, list(args))


def test_analyze_generates_html_report(project):
    """antel analyze 在输出目录生成自包含的 report.html，含全部区块"""
    assert antel('rebuild').exit_code == 0
    result = antel('analyze')

    assert result.exit_code == 0
    report = project / 'demo_antel' / 'report.html'
    assert report.exists()
    text = report.read_text()

    assert '<link' not in text   # 自包含：无外部资源引用
    assert '<style>' in text

    for section in ('antel 分析报告', '目标类型', '增量状态', '编译参数统计',
                    '目标符号表', '头文件依赖', '目标文件大小分布', '编译命令',
                    '日志产物'):
        assert section in text


def test_report_flag_auto_generates_after_build(project):
    """report: true → rebuild/build 成功后自动生成报告"""
    write_config(project, report=True)
    assert antel('rebuild').exit_code == 0
    assert (project / 'demo_antel' / 'report.html').exists()

    report = project / 'demo_antel' / 'report.html'
    before = report.stat().st_mtime_ns

    # 无改动时 build 不重编，也不重新生成报告
    assert antel('build').exit_code == 0
    assert report.stat().st_mtime_ns == before


def test_report_flag_does_not_affect_artifacts(project):
    """report 只决定是否生成报告：产物字节应与 report: false 完全一致"""
    write_config(project)
    assert antel('rebuild').exit_code == 0
    without_report = (project / 'demo_antel' / 'demo').read_bytes()

    write_config(project, report=True)
    assert antel('rebuild').exit_code == 0
    with_report = (project / 'demo_antel' / 'demo').read_bytes()

    assert with_report == without_report


def test_report_shows_symbols_by_default(project):
    """报告自动覆盖全部源文件（不再依赖 analyze_files 字段）"""
    assert antel('rebuild').exit_code == 0
    antel('analyze')

    text = (project / 'demo_antel' / 'report.html').read_text()
    assert 'src/main.c' in text
    assert '函数 (T)' in text          # nm 符号分类标签
    assert 'main' in text
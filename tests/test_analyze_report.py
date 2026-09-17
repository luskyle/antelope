"""antel analyze 可视化报告测试。

报告是自包含的单文件 HTML（内联 CSS，无外部依赖），
浏览器直接打开即可：项目摘要、符号表、编译命令、构建产物、日志清单。
"""

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
    """analyze 在输出目录生成自包含的 report.html，含全部区块"""
    assert antel('rebuild').exit_code == 0
    result = antel('analyze')

    assert result.exit_code == 0
    report = project / 'demo_antel' / 'report.html'
    assert report.exists()
    text = report.read_text()

    # 自包含：无外部资源引用（全部内联 CSS）
    assert '<link' not in text
    assert '<style>' in text

    # 核心区块都在
    assert 'antel 分析报告' in text  # 页面标题
    for section in ('目标类型', '符号总数', '目标符号表',
                    '编译命令', '构建产物分析', '日志产物'):
        assert section in text


def test_analyze_shows_source_symbols_without_analyze_files(project):
    """报告自动覆盖全部源文件：不填 analyze_files 也有符号表"""
    assert antel('rebuild').exit_code == 0

    result = antel('analyze')
    assert result.exit_code == 0

    text = (project / 'demo_antel' / 'report.html').read_text()
    assert 'src/main.c' in text
    assert 'main' in text
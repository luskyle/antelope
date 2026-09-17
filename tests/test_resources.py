"""运行资源打包：data_files（复制）、gresource（GLib 嵌入）、embed（ld -r -b binary 嵌入）。

三种形态都要验证：

1. **data_files**：资源复制进输出目录，改资源后 build 会重新同步
2. **gresource**：资源编成 C 源码再编译进程序（单文件），程序用 GResource API 读取；
   改资源文本 → 触发 gresource.c 重编 + 重链接 → 运行输出变化
3. **embed**：ld -r -b binary 嵌入 .o，程序用 `_binary_<路径转下划线>_start` 符号读取；
   改嵌入文件 → 源码没变也要重链接（资源变化驱动链接）

另外覆盖 clean 把输出目录（含拷贝的数据与生成物）一并回收。
"""

import shutil
import subprocess

import pytest
from click.testing import CliRunner

from antelope.antelope import main
from conftest import write_config, run_program

pytestmark = pytest.mark.skipif(shutil.which('gcc') is None or shutil.which('g++') is None,
                                reason='需要 gcc/g++ 才能执行真实构建')


def antel(*args):
    return CliRunner().invoke(main, list(args))


def write_assets(project_dir, content='hello resource\n'):
    """放一个 assets/hello.txt 资源文件，返回其路径"""
    assets = project_dir / 'assets'
    assets.mkdir(exist_ok=True)
    text = assets / 'hello.txt'
    text.write_text(content)
    return text


def test_data_files_copied_into_output_dir(project):
    """data_files：目录整体复制进输出目录；改源文件后 build 会重新同步"""
    text = write_assets(project)
    write_config(project, data_files=['assets'])

    assert antel('rebuild').exit_code == 0
    copied = project / 'demo_antel' / 'assets' / 'hello.txt'
    assert copied.exists()
    assert copied.read_text() == 'hello resource\n'

    text.write_text('updated resource\n')
    assert antel('build').exit_code == 0
    assert copied.read_text() == 'updated resource\n'


def test_gresource_embeds_into_single_binary(project):
    """gresource：资源编进可执行文件，程序用 GResource API 读取；改资源触发重编重链"""
    if shutil.which('glib-compile-resources') is None:
        pytest.skip('需要 glib-compile-resources')
    if shutil.which('pkg-config') is None:
        pytest.skip('需要 pkg-config')

    write_assets(project, 'gres hello\n')
    (project / 'gresource.gresource.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gresources>\n'
        '  <gresource prefix="/com/test">\n'
        '    <file>assets/hello.txt</file>\n'
        '  </gresource>\n'
        '</gresources>\n')
    (project / 'src' / 'main.c').write_text(
        '#include <stdio.h>\n'
        '#include <gio/gio.h>\n'
        'int main(){\n'
        '    /* glib-compile-resources 生成的代码带 ELF constructor，资源自动注册 */\n'
        '    GBytes *bytes = g_resources_lookup_data("/com/test/assets/hello.txt",\n'
        '                                             G_RESOURCE_LOOKUP_FLAGS_NONE, NULL);\n'
        '    if (bytes == NULL) { printf("lookup failed\\n"); return 1; }\n'
        '    gsize size = 0;\n'
        '    const char *data = g_bytes_get_data(bytes, &size);\n'
        '    printf("%.*s", (int)size, data);\n'
        '    g_bytes_unref(bytes);\n'
        '    return 0;\n'
        '}\n')

    write_config(project, source=['src/main.c'], compile_args=['-w'],
                 pkg_config=['gio-2.0'], gresource='gresource.gresource.xml')

    assert antel('rebuild').exit_code == 0
    assert run_program(project) == 'gres hello'

    # 改资源文本：只改数据不改代码，build 也必须重编 gresource.c 并重链接
    write_assets(project, 'gres updated\n')
    assert antel('build').exit_code == 0
    assert run_program(project) == 'gres updated'


def test_embed_binary_into_executable(project):
    """embed：任意二进制经 ld -r -b binary 嵌入，程序用 _binary_ 符号访问；改文件触发重链接"""
    if shutil.which('ld') is None:
        pytest.skip('需要 ld')

    write_assets(project, 'embed payload\n')
    (project / 'src' / 'main.c').write_text(
        '#include <stdio.h>\n'
        'extern const unsigned char _binary_assets_hello_txt_start[];\n'
        'extern const unsigned char _binary_assets_hello_txt_end[];\n'
        'int main(){\n'
        '    const unsigned char *start = _binary_assets_hello_txt_start;\n'
        '    const unsigned char *end = _binary_assets_hello_txt_end;\n'
        '    printf("%.*s", (int)(end - start), (const char *)start);\n'
        '    return 0;\n'
        '}\n')

    write_config(project, source=['src/main.c'], compile_args=['-w'],
                 embed=['assets/hello.txt'])

    assert antel('rebuild').exit_code == 0
    assert run_program(project) == 'embed payload'

    # 只改嵌入文件不改源码：没有编译单元变 stale，但资源变化必须驱动重链接
    write_assets(project, 'embed v2\n')
    assert antel('build').exit_code == 0
    assert run_program(project) == 'embed v2'


def test_resource_change_without_source_change_still_relinks(project):
    """embed 资源变了但源码没变时，build 必须重链接（资源变化是链接触发条件之一）"""
    if shutil.which('ld') is None:
        pytest.skip('需要 ld')

    write_assets(project, 'v1\n')
    (project / 'src' / 'main.c').write_text(
        '#include <stdio.h>\n'
        'extern const unsigned char _binary_assets_hello_txt_start[];\n'
        'extern const unsigned char _binary_assets_hello_txt_end[];\n'
        'int main(){\n'
        '    const unsigned char *start = _binary_assets_hello_txt_start;\n'
        '    const unsigned char *end = _binary_assets_hello_txt_end;\n'
        '    printf("%.*s", (int)(end - start), (const char *)start);\n'
        '    return 0;\n'
        '}\n')
    write_config(project, source=['src/main.c'], compile_args=['-w'],
                 embed=['assets/hello.txt'])

    assert antel('rebuild').exit_code == 0
    assert run_program(project) == 'v1'

    # 基线稳定后：不改任何东西，build 应为无改动（可执行文件不被重写）
    program = project / 'demo_antel' / 'demo'
    before = program.stat().st_mtime_ns
    assert antel('build').exit_code == 0
    assert program.stat().st_mtime_ns == before, '无改动时不应重链接'

    write_assets(project, 'v2\n')
    assert antel('build').exit_code == 0
    assert run_program(project) == 'v2'


def test_clean_removes_copied_resources(project):
    """clean 回收整个输出目录，包括 data_files 的拷贝与 embed 生成物"""
    if shutil.which('ld') is None:
        pytest.skip('需要 ld')

    write_assets(project)
    write_config(project, data_files=['assets'], embed=['assets/hello.txt'])

    assert antel('rebuild').exit_code == 0
    assert (project / 'demo_antel').exists()

    assert antel('clean').exit_code == 0
    assert not (project / 'demo_antel').exists()
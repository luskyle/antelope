import json
import platform
import struct
import sys
from pathlib import Path
from subprocess import check_call, check_output


ROOT = Path(__file__).resolve().parent
REF_DIR = ROOT / '.antel' / 'refs' / 'libgit2'
FEATURES_HEADER = ROOT / '.antel' / 'build' / 'libgit2-generated' / 'git2_features.h'
CONFIG_PATH = ROOT / 'generated.json'
SHARED_CONFIG_PATH = ROOT / 'shared.json'
CLI_CONFIG_PATH = ROOT / 'cli.json'
LG2_CONFIG_PATH = ROOT / 'lg2.json'
LIBGIT2_TEST_CONFIG_PATH = ROOT / 'tests-libgit2.json'
UTIL_TEST_CONFIG_PATH = ROOT / 'tests-util.json'

INCLUDE_DIRECTORIES = [
    '.antel/refs/libgit2/src/libgit2',
    '.antel/refs/libgit2/src/util',
    '.antel/refs/libgit2/include',
    '.antel/build/libgit2-generated',
    '.antel/refs/libgit2/deps/llhttp',
    '.antel/refs/libgit2/deps/ntlmclient',
    '.antel/refs/libgit2/deps/reftable',
    '.antel/refs/libgit2/deps/reftable/include',
    '.antel/refs/libgit2/deps/xdiff',
]
PKG_CONFIG = ['openssl', 'libpcre', 'zlib']


def selected_sources():
    if not REF_DIR.is_dir():
        raise SystemExit('libgit2 ref is missing; run antel fetch-ref -f generated first.')
    if not sys.platform.startswith('linux'):
        raise SystemExit('This source selection currently targets Linux.')

    patterns = (
        'src/libgit2/**/*.c',
        'src/util/*.c',
        'src/util/allocators/*.c',
        'src/util/unix/*.c',
        'src/util/hash/collisiondetect.c',
        'src/util/hash/openssl.c',
        'src/util/hash/sha1dc/*.c',
        'deps/llhttp/*.c',
        'deps/ntlmclient/crypt_openssl.c',
        'deps/ntlmclient/ntlm.c',
        'deps/ntlmclient/unicode_builtin.c',
        'deps/ntlmclient/util.c',
        'deps/reftable/*.c',
        'deps/xdiff/*.c',
    )
    sources = sorted({
        f'.antel/refs/libgit2/{path.relative_to(REF_DIR).as_posix()}'
        for pattern in patterns
        for path in REF_DIR.glob(pattern)
        if path.is_file()
    })
    if len(sources) < 150:
        raise SystemExit(f'Expected the libgit2 library source set, found {len(sources)} files.')

    object_names = [source.replace('/', '_').replace('.c', '.o') for source in sources]
    if len(object_names) != len(set(object_names)):
        raise SystemExit('Source paths collide under Antel object naming.')
    return sources


def ref_sources(paths, description):
    missing = [path for path in paths if not (REF_DIR / path).is_file()]
    if missing:
        raise SystemExit(
            f'Missing {description} sources: ' + ', '.join(missing[:10])
        )
    return [f'.antel/refs/libgit2/{path}' for path in paths]


def source_paths(directory, patterns):
    return sorted({
        path.relative_to(REF_DIR).as_posix()
        for pattern in patterns
        for path in (REF_DIR / directory).glob(pattern)
        if path.is_file() and path.suffix == '.c'
    })


def ensure_unique_objects(sources, description):
    object_names = [source.replace('/', '_').replace('.c', '.o') for source in sources]
    if len(object_names) != len(set(object_names)):
        raise SystemExit(f'{description} source paths collide under Antel object naming.')
    return sources


def feature_header():
    commit = check_output(
        ['git', '-C', str(REF_DIR), 'rev-parse', 'HEAD'],
        text=True,
    ).strip()
    cpu = platform.machine()
    macros = [
        'GIT_THREADS',
        'GIT_THREADS_PTHREADS',
        'GIT_SHA1_BUILTIN',
        'GIT_SHA256_OPENSSL',
        'GIT_COMPRESSION_ZLIB',
        'GIT_NSEC',
        'GIT_NSEC_MTIM',
        'GIT_REGEX_PCRE',
        'GIT_HTTP',
        'GIT_HTTPS',
        'GIT_HTTPS_OPENSSL',
        'GIT_HTTPPARSER_BUILTIN',
        'GIT_AUTH_NTLM',
        'GIT_AUTH_NTLM_BUILTIN',
        'GIT_QSORT_GNU',
        'GIT_FUTIMENS',
        'GIT_RAND_GETENTROPY',
        'GIT_RAND_GETLOADAVG',
        'GIT_IO_POLL',
        'GIT_IO_SELECT',
    ]
    if struct.calcsize('P') == 8:
        macros.append('GIT_ARCH_64')
    else:
        macros.append('GIT_ARCH_32')

    lines = [
        '#ifndef INCLUDE_features_h__',
        '#define INCLUDE_features_h__',
        '',
        *(f'#define {macro} 1' for macro in macros),
        f'#define GIT_BUILD_CPU "{cpu}"',
        f'#define GIT_BUILD_COMMIT "{commit}"',
        '',
        '#endif',
        '',
    ]
    return '\n'.join(lines)


def write_if_changed(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding='utf-8') != content:
        path.write_text(content, encoding='utf-8')


def common_config(refs, sources, target_type, compile_args, **kwargs):
    return {
        'projectName': 'git2',
        'target_type': target_type,
        'compiler': 'gxx',
        'ref': refs,
        'source': sources,
        'include_directories': [],
        'compile_args': compile_args,
        'link_args': [],
        'pkg_config': PKG_CONFIG,
        'before_build': [{
            'command': ['python3', 'prepare_antelope.py'],
            'outputs': ['.antel/build/libgit2-generated/git2_features.h'],
        }],
        **kwargs,
    }


def test_config(refs, name, project_name, test_sources, test_root, clar_output):
    test_path = f'.antel/refs/libgit2/{test_root}'
    fixture_path = (REF_DIR / 'tests' / 'resources').as_posix() + '/'
    clar_sources = ref_sources(source_paths('deps/clar', ['*.c']), 'Clar')
    sources = ensure_unique_objects(
        [*clar_sources, *ref_sources(test_sources, name)],
        name,
    )
    return common_config(
        refs,
        sources,
        'exe',
        [
            '-std=c99',
            '-O2',
            '-DNDEBUG',
            '-DGIT_STATIC_BUILD=1',
            '-DGIT_DEPRECATE_HARD=1',
            '-D_FILE_OFFSET_BITS=64',
            '-D_GNU_SOURCE',
            f'-DCLAR_FIXTURE_PATH="{fixture_path}"',
            '-DCLAR_TMPDIR="libgit2_tests"',
            '-DCLAR_WIN32_LONGPATHS',
            '-DCLAR_HAS_REALPATH',
            *(f'-I{directory}' for directory in [
                *INCLUDE_DIRECTORIES,
                '.antel/refs/libgit2/deps/clar',
                test_path,
                clar_output,
            ]),
        ],
        projectName=project_name,
        link_args=[
            '.antel/build/git2_generated/libgit2.a',
            '-pthread',
            '-lm',
        ],
        before_build=[{
            'command': ['python3', 'prepare_antelope.py'],
            'outputs': [
                '.antel/build/libgit2-generated/git2_features.h',
                f'{clar_output}/clar.suite',
                f'{clar_output}/clar_suite.h',
            ],
        }],
    )


def prepare_clar(test_directory, output_directory, excludes=()):
    command = [
        sys.executable,
        str(REF_DIR / 'deps/clar/generate.py'),
        '-o',
        str(output_directory),
        *(argument for exclude in excludes for argument in ('-x', exclude)),
        '.',
    ]
    check_call(command, cwd=REF_DIR / test_directory)


def main():
    sources = selected_sources()
    write_if_changed(FEATURES_HEADER, feature_header())
    base = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    refs = base.get('ref')
    if not isinstance(refs, list) or not refs:
        raise SystemExit('generated.json must contain at least one libgit2 ref.')

    library_compile_args = [
        '-std=c99',
        '-O2',
        '-fvisibility=hidden',
        '-DNDEBUG',
        '-DGIT_STATIC_BUILD=1',
        '-DCRYPT_OPENSSL',
        '-DNTLM_STATIC=1',
        '-DOPENSSL_API_COMPAT=0x10100000L',
        '-DUNICODE_BUILTIN=1',
        '-D_FILE_OFFSET_BITS=64',
        '-D_GNU_SOURCE',
        '-DSHA1DC_NO_STANDARD_INCLUDES=1',
        '-DSHA1DC_CUSTOM_INCLUDE_SHA1_C="git2_util.h"',
        '-DSHA1DC_CUSTOM_INCLUDE_UBC_CHECK_C="git2_util.h"',
    ]
    common_compile_args = [
        *library_compile_args,
        *(f'-I{directory}' for directory in INCLUDE_DIRECTORIES),
    ]
    static = common_config(refs, sources, 'static', common_compile_args)
    write_if_changed(CONFIG_PATH, json.dumps(static, indent=4) + '\n')

    shared_compile_args = [
        argument for argument in common_compile_args
        if argument not in ('-fvisibility=hidden', '-DGIT_STATIC_BUILD=1')
    ]
    shared_compile_args.append('-fPIC')
    shared = common_config(
        refs,
        sources,
        'shared',
        shared_compile_args,
        version='1.9.0',
        soname='libgit2.so.1.9',
        link_args=['-pthread'],
    )
    write_if_changed(SHARED_CONFIG_PATH, json.dumps(shared, indent=4) + '\n')

    cli_sources = ref_sources(
        source_paths('src/cli', ['*.c', 'unix/*.c']),
        'CLI',
    )
    cli_sources = ensure_unique_objects(cli_sources, 'CLI')
    cli_includes = [
        *INCLUDE_DIRECTORIES,
        '.antel/refs/libgit2/src/cli',
    ]
    cli = common_config(
        refs,
        cli_sources,
        'exe',
        [
            *library_compile_args,
            *(f'-I{directory}' for directory in cli_includes),
        ],
        link_args=['.antel/build/git2_generated/libgit2.a', '-pthread'],
    )
    write_if_changed(CLI_CONFIG_PATH, json.dumps(cli, indent=4) + '\n')

    example_sources = ref_sources(
        source_paths('examples', ['*.c']),
        'example',
    )
    example_sources = ensure_unique_objects(example_sources, 'lg2 example')
    lg2 = common_config(
        refs,
        example_sources,
        'exe',
        [
            '-std=c99',
            '-O2',
            '-DNDEBUG',
            '-DGIT_DEPRECATE_HARD=1',
            *(f'-I{directory}' for directory in [
                *INCLUDE_DIRECTORIES,
                '.antel/refs/libgit2/examples',
            ]),
        ],
        projectName='lg2',
        link_args=[
            '-L.antel/build/git2_shared',
            '-lgit2',
            '-pthread',
        ],
        rpath=['$ORIGIN/../git2_shared'],
    )
    write_if_changed(LG2_CONFIG_PATH, json.dumps(lg2, indent=4) + '\n')

    libgit2_test_sources = source_paths('tests/libgit2', ['**/*.c'])
    util_test_sources = source_paths('tests/util', ['**/*.c'])
    libgit2_test_output = '.antel/build/libgit2-tests'
    util_test_output = '.antel/build/util-tests'
    prepare_clar('tests/libgit2', ROOT / libgit2_test_output,
                 ('online', 'stress', 'perf'))
    prepare_clar('tests/util', ROOT / util_test_output)
    write_if_changed(
        LIBGIT2_TEST_CONFIG_PATH,
        json.dumps(test_config(
            refs, 'tests-libgit2', 'libgit2_tests', libgit2_test_sources,
            'tests/libgit2', libgit2_test_output,
        ), indent=4) + '\n',
    )
    write_if_changed(
        UTIL_TEST_CONFIG_PATH,
        json.dumps(test_config(
            refs, 'tests-util', 'util_tests', util_test_sources,
            'tests/util', util_test_output,
        ), indent=4) + '\n',
    )
    print(
        f'Prepared Antel configs: {len(sources)} library sources, '
        f'{len(cli_sources)} CLI sources, {len(example_sources)} example sources, '
        f'{len(libgit2_test_sources)} libgit2 test sources, '
        f'{len(util_test_sources)} utility test sources.'
    )


if __name__ == '__main__':
    main()

import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / '.antel' / 'refs' / 'libpng'
OUTPUT = ROOT / '.antel' / 'build' / 'libpng-generated'


def run(argv):
    subprocess.run(argv, cwd=ROOT, check=True)


def main():
    if not SOURCE.is_dir():
        raise SystemExit('libpng ref is missing; run antel fetch-ref first.')

    version_header = (SOURCE / 'png.h').read_text(encoding='latin-1')
    match = re.search(
        r'^#define PNG_LIBPNG_VER_STRING "(\d+)\.(\d+)\.(\d+)',
        version_header,
        re.MULTILINE,
    )
    if match is None:
        raise SystemExit('Could not read libpng version from png.h.')

    major, minor, revision = match.groups()
    compiler = shlex.split(os.environ.get('CC', 'cc'))
    awk = shutil.which('awk') or shutil.which('nawk')
    pkg_config = shutil.which('pkg-config')
    if not compiler or shutil.which(compiler[0]) is None:
        raise SystemExit('A C compiler (CC or cc) is required to prepare libpng.')
    if awk is None:
        raise SystemExit('An AWK implementation is required to prepare libpng.')
    if pkg_config is None:
        raise SystemExit('pkg-config is required to locate zlib headers.')

    zlib_cflags = subprocess.check_output(
        [pkg_config, '--cflags-only-I', 'zlib'], text=True).strip()
    include_flags = shlex.split(zlib_cflags)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        SOURCE / 'scripts' / 'pnglibconf.h.prebuilt',
        OUTPUT / 'pnglibconf.h',
    )

    with tempfile.TemporaryDirectory(dir=OUTPUT) as temp_dir:
        preprocessed = Path(temp_dir) / 'vers.i'
        version_script = Path(temp_dir) / 'libpng.vers'
        run(compiler + [
            '-E',
            f'-I{SOURCE}',
            f'-I{OUTPUT}',
            *include_flags,
            f'-DPNGLIB_LIBNAME=PNG{major}{minor}_0',
            f'-DPNGLIB_VERSION={major}.{minor}.{revision}',
            '-DSYMBOL_PREFIX=',
            '-DPNG_NO_USE_READ_MACROS',
            '-DPNG_BUILDING_SYMBOL_TABLE',
            str(SOURCE / 'scripts' / 'vers.c'),
            '-o',
            str(preprocessed),
        ])
        run([
            awk,
            '-f',
            str(SOURCE / 'scripts' / 'dfn.awk'),
            f'out={version_script}',
            str(preprocessed),
        ])
        shutil.copyfile(version_script, OUTPUT / 'libpng.vers')

    print(f'Prepared libpng {major}.{minor}.{revision} headers and version script in {OUTPUT}')


if __name__ == '__main__':
    main()
import json
import shlex
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REF_DIR = ROOT / '.antel' / 'refs' / 'libgit2'
BUILD_DIR = ROOT / '.antel' / 'build' / 'libgit2-config'
COMPILE_DATABASE = BUILD_DIR / 'compile_commands.json'


def map_include(path):
    resolved = Path(path).resolve()
    for base, prefix in ((REF_DIR, '.antel/refs/libgit2'),
                         (BUILD_DIR, '.antel/build/libgit2-config')):
        try:
            relative = resolved.relative_to(base)
            return f'-I{prefix}/{relative.as_posix()}'
        except ValueError:
            pass

    if str(resolved).startswith(('/usr/include/', '/usr/local/include/')):
        return None
    raise ValueError(f'Unsupported include path in compile database: {path}')


def main():
    if not COMPILE_DATABASE.is_file():
        raise SystemExit('Run the libgit2 CMake configure step first.')

    commands = json.loads(COMPILE_DATABASE.read_text())
    sources = set()
    includes = set()
    definitions = set()

    for entry in commands:
        source = Path(entry['file']).resolve()
        try:
            relative_source = source.relative_to(REF_DIR).as_posix()
        except ValueError as error:
            raise SystemExit(f'Source is outside the ref checkout: {source}') from error
        sources.add(f'.antel/refs/libgit2/{relative_source}')

        tokens = shlex.split(entry['command'])
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token == '-I' and index + 1 < len(tokens):
                index += 1
                include = map_include(tokens[index])
                if include is not None:
                    includes.add(include)
            elif token.startswith('-I'):
                include = map_include(token[2:])
                if include is not None:
                    includes.add(include)
            elif token.startswith('-D'):
                definitions.add(token)
            index += 1

    if len(sources) < 100:
        raise SystemExit(f'Expected the full libgit2 target, found {len(sources)} sources.')

    object_names = [source.replace('/', '_').replace('.c', '.o') for source in sources]
    if len(object_names) != len(set(object_names)):
        raise SystemExit('Source paths collide under Antel object naming.')

    config = {
        'projectName': 'git2',
        'target_type': 'static',
        'compiler': 'gxx',
        'ref': [{
            'url': 'https://github.com/libgit2/libgit2.git',
            'branch': 'main',
            'name': 'libgit2',
        }],
        'source': sorted(sources),
        'include_directories': [],
        'compile_args': [
            '-std=c99',
            '-O2',
            '-fvisibility=hidden',
            *sorted(definitions),
            *sorted(includes),
        ],
        'link_args': [],
        'pkg_config': ['openssl', 'libpcre', 'zlib'],
    }
    (ROOT / 'generated.json').write_text(json.dumps(config, indent=4) + '\n')
    print(f'Wrote generated.json with {len(sources)} upstream sources.')


if __name__ == '__main__':
    main()
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REF_DIR = ROOT / '.antel' / 'refs' / 'libuv'
STATIC_CONFIG = ROOT / 'antel.json'

LIB_SOURCES = (
    'src/fs-poll.c',
    'src/idna.c',
    'src/inet.c',
    'src/random.c',
    'src/strscpy.c',
    'src/strtok.c',
    'src/thread-common.c',
    'src/threadpool.c',
    'src/timer.c',
    'src/uv-common.c',
    'src/uv-data-getter-setters.c',
    'src/version.c',
    'src/unix/async.c',
    'src/unix/core.c',
    'src/unix/dl.c',
    'src/unix/fs.c',
    'src/unix/getaddrinfo.c',
    'src/unix/getnameinfo.c',
    'src/unix/loop-watcher.c',
    'src/unix/loop.c',
    'src/unix/pipe.c',
    'src/unix/poll.c',
    'src/unix/process.c',
    'src/unix/random-devurandom.c',
    'src/unix/signal.c',
    'src/unix/stream.c',
    'src/unix/tcp.c',
    'src/unix/thread.c',
    'src/unix/tty.c',
    'src/unix/udp.c',
    'src/unix/linux.c',
    'src/unix/procfs-exepath.c',
    'src/unix/random-getrandom.c',
    'src/unix/random-sysctl-linux.c',
    'src/unix/proctitle.c',
)

BENCHMARK_SOURCES = (
    'benchmark-async-pummel.c',
    'benchmark-async.c',
    'benchmark-fs-stat.c',
    'benchmark-getaddrinfo.c',
    'benchmark-loop-count.c',
    'benchmark-queue-work.c',
    'benchmark-million-async.c',
    'benchmark-million-timers.c',
    'benchmark-multi-accept.c',
    'benchmark-ping-pongs.c',
    'benchmark-ping-udp.c',
    'benchmark-pound.c',
    'benchmark-pump.c',
    'benchmark-sizes.c',
    'benchmark-spawn.c',
    'benchmark-tcp-write-batch.c',
    'benchmark-thread.c',
    'benchmark-udp-pummel.c',
)


def ref_sources(paths):
    missing = [path for path in paths if not (REF_DIR / path).is_file()]
    if missing:
        raise SystemExit('Missing expected libuv sources: ' + ', '.join(missing))
    return [f'.antel/refs/libuv/{path}' for path in paths]


def write_config(filename, config):
    (ROOT / filename).write_text(
        json.dumps(config, indent=4) + '\n',
        encoding='utf-8',
    )


def main():
    if not REF_DIR.is_dir():
        raise SystemExit('libuv ref is missing; run antel fetch-ref first.')

    base = json.loads(STATIC_CONFIG.read_text(encoding='utf-8'))
    if base.get('target_type') != 'static':
        raise SystemExit('antel.json must define the static libuv target.')

    common_flags = base['compile_args']
    shared = {
        **base,
        'target_type': 'shared',
        'compile_args': [*common_flags, '-fPIC', '-DBUILDING_UV_SHARED=1'],
        'link_args': ['-pthread', '-ldl', '-lrt'],
        'version': '1.0.0',
        'soname': 'libuv.so.1',
    }
    write_config('shared.json', shared)

    test_sources = ref_sources([
        *(path.relative_to(REF_DIR).as_posix()
          for path in sorted((REF_DIR / 'test').glob('test-*.c'))),
        'test/blackhole-server.c',
        'test/echo-server.c',
        'test/run-tests.c',
        'test/runner.c',
        'test/runner-unix.c',
    ])
    test_base = {
        **base,
        'target_type': 'exe',
        'source': test_sources,
        'compile_args': [*common_flags, '-I.antel/refs/libuv/test'],
        'link_args': ['.antel/build/uv_antel/libuv.a', '-pthread', '-ldl', '-lrt', '-lm', '-lutil'],
    }
    write_config('tests-static.json', {
        **test_base,
        'projectName': 'uv_run_tests_a',
    })
    write_config('tests-shared.json', {
        **test_base,
        'projectName': 'uv_run_tests',
        'compile_args': [*test_base['compile_args'], '-DUSING_UV_SHARED=1'],
        'link_args': [
            '.antel/build/uv_shared/libuv.so',
            '-pthread',
            '-ldl',
            '-lrt',
            '-lm',
            '-lutil',
        ],
        'rpath': ['$ORIGIN/../uv_shared'],
    })

    benchmark_sources = ref_sources([
        *(f'test/{path}' for path in BENCHMARK_SOURCES),
        'test/blackhole-server.c',
        'test/echo-server.c',
        'test/run-benchmarks.c',
        'test/runner.c',
        'test/runner-unix.c',
    ])
    write_config('benchmarks.json', {
        **test_base,
        'projectName': 'uv_run_benchmarks_a',
        'source': benchmark_sources,
    })

    print(
        f'Prepared Antel configs: uv static/shared, {len(test_sources)} '
        f'test sources, and {len(benchmark_sources) - 5} benchmark sources.'
    )


if __name__ == '__main__':
    main()

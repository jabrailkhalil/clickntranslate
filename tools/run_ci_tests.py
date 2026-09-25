"""Run all test files in bounded processes with isolated application data."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def partition_files(files, parts):
    if parts < 1:
        raise ValueError('parts must be positive')
    files = sorted(files)
    if not files:
        raise ValueError('No test files found')
    size = (len(files) + parts - 1) // parts
    return [files[index:index + size] for index in range(0, len(files), size)]


def run_partitions(partitions, output, timeout):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'plan.json').write_text(json.dumps(partitions, indent=2), encoding='utf-8')
    failed = False
    for index, files in enumerate(partitions, 1):
        print(f'CI part {index}/{len(partitions)}: {len(files)} test files', flush=True)
        command = [sys.executable, str(ROOT / 'tools/run_regression_tests.py'),
                   '--output', str(output / f'part-{index}'), '-vv', *files]
        try:
            result = subprocess.run(command, cwd=ROOT, timeout=timeout)
            failed = failed or result.returncode != 0
        except subprocess.TimeoutExpired:
            print(f'CI part {index} exceeded {timeout} seconds', flush=True)
            failed = True
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parts', type=int, default=2)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/ci-tests')
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    files = [path.relative_to(ROOT).as_posix() for path in (ROOT / 'tests').glob('test_*.py')]
    return run_partitions(partition_files(files, args.parts), args.output.resolve(), args.timeout)


if __name__ == '__main__':
    raise SystemExit(main())

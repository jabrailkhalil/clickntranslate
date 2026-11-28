"""Run all test files in bounded processes with isolated application data."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]

# Slowest modules in Windows/Linux CI run 46134023899, rounded to five seconds.
# The other modules averaged seven seconds. New files are always scheduled.
SLOW_FILE_SECONDS = {
    'test_engine_center_stationary_layout.py': 670,
    'test_guide_setup.py': 260,
    'test_engine_background_jobs.py': 235,
    'test_dynamic_settings_workflow.py': 130,
    'test_settings_categories.py': 95,
    'test_keyboard_navigation.py': 90,
    'test_popup_host_scaling.py': 85,
    'test_settings_sections.py': 80,
    'test_settings_overlay_and_hover.py': 75,
    'test_main_language_flags.py': 70,
    'test_embedded_popup_keys.py': 65,
    'test_history_paging.py': 65,
}


def estimated_seconds(filename):
    return SLOW_FILE_SECONDS.get(Path(filename).name, 7)


def partition_files(files, parts):
    if parts < 1:
        raise ValueError('parts must be positive')
    files = sorted(files)
    if not files:
        raise ValueError('No test files found')
    partitions = [[] for _ in range(min(parts, len(files)))]
    loads = [0] * len(partitions)
    for filename in sorted(files, key=estimated_seconds, reverse=True):
        part = min(range(len(partitions)), key=loads.__getitem__)
        partitions[part].append(filename)
        loads[part] += estimated_seconds(filename)
    return [sorted(part) for part in partitions]


def run_partitions(partitions, output, timeout, *, selected_part=None):
    if selected_part is not None and not 1 <= selected_part <= len(partitions):
        raise ValueError(f'part must be between 1 and {len(partitions)}')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'plan.json').write_text(json.dumps(partitions, indent=2), encoding='utf-8')
    failed = False
    for index, files in enumerate(partitions, 1):
        if selected_part is not None and index != selected_part:
            continue
        estimate = sum(estimated_seconds(filename) for filename in files)
        print(f'CI part {index}/{len(partitions)}: {len(files)} test files, estimated {estimate}s', flush=True)
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
    parser.add_argument('--part', type=int, help='Run only this 1-based part of the full plan')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/ci-tests')
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    files = [path.relative_to(ROOT).as_posix() for path in (ROOT / 'tests').glob('test_*.py')]
    try:
        partitions = partition_files(files, args.parts)
        return run_partitions(partitions, args.output.resolve(), args.timeout, selected_part=args.part)
    except ValueError as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())

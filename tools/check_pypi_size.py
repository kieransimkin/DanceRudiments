#!/usr/bin/env python3
"""Gate unexpectedly large PyPI packages before publishing.

Designed to run without third-party dependencies on all CI platforms.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import tempfile

DEFAULT_BUDGET = Path(__file__).resolve().parents[1] / 'packaging/python-size-budget.json'


def load_budget(path: Path = DEFAULT_BUDGET) -> dict:
    budget = json.loads(Path(path).read_text(encoding='utf-8'))
    if budget.get('schema_version') != 1:
        raise ValueError('Unsupported Python size-budget schema')
    for name in ('max_wheel_mib', 'max_sdist_mib', 'max_total_mib'):
        value = budget.get(name)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(name+' must be finite and positive')
    if type(budget.get('release_wheel_count')) is not int or budget['release_wheel_count'] < 1:
        raise ValueError('release_wheel_count must be a positive integer')
    if not isinstance(budget.get('rationale'), str) or not budget['rationale'].strip():
        raise ValueError('The size budget requires its reviewed rationale')
    return budget


def inspect(directory: Path, wheel_limit: float, sdist_limit: float, total_limit: float | None,
            *, expected_wheels: int | None = None, expected_version: str | None = None) -> int:
    for limit in (wheel_limit, sdist_limit, total_limit):
        if limit is not None and (type(limit) not in (int, float) or not math.isfinite(limit) or limit <= 0):
            raise ValueError('Size limits must be finite and positive')
    files = sorted(set(directory.glob('*.whl')) | set(directory.glob('*.tar.gz')))
    if not files:
        print(f'ERROR: no wheel/sdist files found in {directory}')
        return 1
    failed = False
    total = 0
    if expected_wheels is not None:
        wheels = [file for file in files if file.suffix == '.whl']
        sources = [file for file in files if file.name.endswith('.tar.gz')]
        if len(wheels) != expected_wheels or len(sources) != 1:
            print(f'ERROR: release requires {expected_wheels} wheels and one sdist; '
                  f'found {len(wheels)} wheels and {len(sources)} sdists')
            failed = True
    if expected_version is not None:
        for file in files:
            correct = (file.name.startswith('dancerudiments-'+expected_version+'-')
                       if file.suffix == '.whl' else
                       file.name == 'dancerudiments-'+expected_version+'.tar.gz')
            if not correct:
                print('ERROR: distribution does not match the exact release version: '+file.name)
                failed = True
    for file in files:
        size = file.stat().st_size
        total += size
        limit = (sdist_limit if file.name.endswith('.tar.gz') else wheel_limit) * 1024 ** 2
        ok = size <= limit
        failed |= not ok
        print(f'{"OK" if ok else "OVERSIZED"}: {file.name}: {size / 1024**2:.2f} MiB (limit {limit / 1024**2:.2f} MiB)')
    if total_limit is not None:
        ok = total <= total_limit * 1024 ** 2
        failed |= not ok
        print(f'{"OK" if ok else "OVERSIZED"}: total {total / 1024**2:.2f} MiB (limit {total_limit:.2f} MiB)')
    return int(failed)


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        assert inspect(root, 8, 12, None) == 1
        (root / 'test-1-py3-none-any.whl').write_bytes(b'a' * 1024)
        assert inspect(root, 8, 12, 1) == 0
        assert inspect(root, .0001, 12, None) == 1
        (root / 'test-1.tar.gz').write_bytes(b'b' * 2048)
        assert inspect(root, 8, .0001, None) == 1
        assert inspect(root, 8, 12, .0001) == 1
    print('Size budget tests passed')
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path, nargs='?', default=Path('dist'))
    p.add_argument('--budget', type=Path, default=DEFAULT_BUDGET)
    p.add_argument('--max-wheel-mib', type=float)
    p.add_argument('--max-sdist-mib', type=float)
    p.add_argument('--max-total-mib', type=float)
    p.add_argument('--release-set', action='store_true', help='Require the complete reviewed wheel matrix and one source archive')
    p.add_argument('--expected-version', help='Require every filename to match this exact version')
    p.add_argument('--self-test', action='store_true')
    args = p.parse_args()
    if args.self_test:
        return self_test()
    try:
        budget = load_budget(args.budget)
        print('Python distribution policy: '+str(args.budget))
        return inspect(args.directory,
                       args.max_wheel_mib if args.max_wheel_mib is not None else budget['max_wheel_mib'],
                       args.max_sdist_mib if args.max_sdist_mib is not None else budget['max_sdist_mib'],
                       args.max_total_mib if args.max_total_mib is not None else budget['max_total_mib'],
                       expected_wheels=budget['release_wheel_count'] if args.release_set else None,
                       expected_version=args.expected_version)
    except (OSError, ValueError, TypeError) as error:
        p.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())

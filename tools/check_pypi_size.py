#!/usr/bin/env python3
"""Gate unexpectedly large PyPI packages before publishing.

Designed to run without third-party dependencies on all CI platforms.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import tempfile


def inspect(directory: Path, wheel_limit: float, sdist_limit: float, total_limit: float | None) -> int:
    files = sorted(set(directory.glob('*.whl')) | set(directory.glob('*.tar.gz')))
    if not files:
        print(f'ERROR: no wheel/sdist files found in {directory}')
        return 1
    failed = False
    total = 0
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
    p.add_argument('--max-wheel-mib', type=float, default=8)
    p.add_argument('--max-sdist-mib', type=float, default=12)
    p.add_argument('--max-total-mib', type=float)
    p.add_argument('--self-test', action='store_true')
    args = p.parse_args()
    return self_test() if args.self_test else inspect(args.directory, args.max_wheel_mib, args.max_sdist_mib, args.max_total_mib)


if __name__ == '__main__':
    raise SystemExit(main())

"""Explicit local optional-package operations; never downloads on import."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from ._validation import ScoreError
from .motion import load_rig_motion
from .motion_packages import (MotionPackage, MotionPackageBuilder, discover_motion_packages,
                              export_motion_package, install_motion_package)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect', help='Read a manifest without loading motion payloads')
    inspect.add_argument('package', type=Path)
    listing = commands.add_parser('list', help='List packages in an explicit local install directory')
    listing.add_argument('--root', type=Path, required=True)
    install = commands.add_parser('install', help='Verify and install one independent local package ZIP')
    install.add_argument('archive', type=Path)
    install.add_argument('--root', type=Path, required=True)
    install.add_argument('--sha256')
    export = commands.add_parser('export', help='Export one package directory to a deterministic ZIP')
    export.add_argument('package', type=Path)
    export.add_argument('archive', type=Path)
    create = commands.add_parser('create', help='Package existing rig-motion JSON files with one exact profile')
    create.add_argument('motions', nargs='+', type=Path)
    create.add_argument('--output', type=Path, required=True)
    create.add_argument('--id', required=True)
    create.add_argument('--version', default='1.0.0')
    create.add_argument('--title', required=True)
    create.add_argument('--license', required=True, help='SPDX licence identifier or reviewed custom identifier')
    create.add_argument('--license-url', required=True)
    create.add_argument('--attribution', required=True)
    create.add_argument('--source-url', required=True)
    create.add_argument('--timing-kind', choices=('music', 'time-only'), required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'inspect':
            with MotionPackage(args.package, cache_size=0) as package:
                result = package.manifest
        elif args.command == 'list': result = discover_motion_packages(args.root)
        elif args.command == 'install':
            result = {'installed': str(install_motion_package(args.archive, args.root,
                                                             expected_sha256=args.sha256))}
        elif args.command == 'export':
            result = {'archive': str(export_motion_package(args.package, args.archive))}
        else:
            first = load_rig_motion(args.motions[0])
            builder = MotionPackageBuilder(args.output, package_id=args.id, version=args.version,
                title=args.title, profile=first.profile,
                license={'id': args.license, 'url': args.license_url, 'attribution': args.attribution},
                provenance={'source_url': args.source_url, 'changes': 'Packaged into independent gzip Recording clips.'})
            builder.add(first, metadata={'timing_kind': args.timing_kind})
            for path in args.motions[1:]:
                builder.add(load_rig_motion(path), metadata={'timing_kind': args.timing_kind})
            result = builder.finalize()
        print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
        return 0
    except (ScoreError, OSError, ValueError, KeyError) as exc:
        print(f'dancerudiments-motion-pack: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__': raise SystemExit(main())

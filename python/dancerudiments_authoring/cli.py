"""Compile/validate scores without installing or importing the native runtime."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile
from typing import Optional, Sequence

from ._validation import ScoreError
from .compiler import compile_pack
from .io import emit_cpp, emit_json, read_json


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         dir=path.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('compile', 'validate', 'check'))
    parser.add_argument('input', type=Path, help='Standalone score or score-pack JSON')
    parser.add_argument('--json', type=Path, help='Compiled interchange output')
    parser.add_argument('--cpp', type=Path, help='Standalone generated C++17 header')
    parser.add_argument('--namespace', default='dancerudiments_generated')
    args = parser.parse_args(argv)
    try:
        outputs = [p.resolve() for p in (args.json, args.cpp) if p is not None]
        if args.command != 'validate' and not outputs:
            raise ScoreError('compile/check requires --json and/or --cpp')
        if args.command == 'validate' and outputs:
            raise ScoreError('validate does not write outputs; use compile or check')
        if len(outputs) != len(set(outputs)) or args.input.resolve() in outputs:
            raise ScoreError('Input and output paths must all be different')
        pack = compile_pack(read_json(args.input))
        rendered = []
        if args.json:
            rendered.append((args.json, emit_json(pack)))
        if args.cpp:
            rendered.append((args.cpp, emit_cpp(pack, args.namespace)))
        # Render/validate everything before touching any output file.
        for path, content in rendered:
            if args.command == 'check':
                if not path.exists() or path.read_text(encoding='utf-8') != content:
                    raise ScoreError(f'Generated output is missing or stale: {path}')
            elif args.command == 'compile':
                _write(path, content)
        for pattern in pack.patterns:
            print(f'{pattern.name}: {pattern.period_pips} pips; source {pattern.source_sha256[:12]}')
            for warning in pattern.diagnostics['warnings']:
                print(f'  warning: {warning}', file=sys.stderr)
        return 0
    except (ScoreError, OSError, UnicodeError) as exc:
        print(f'dancerudiments-compile: {exc}', file=sys.stderr)
        return 2

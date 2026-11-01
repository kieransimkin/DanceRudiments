"""Shared explicit options for offline motion evidence and bounded derivatives."""
from __future__ import annotations

import json
from pathlib import Path


def add_completion_arguments(parser):
    parser.add_argument('--no-world-space', action='store_true',
                        help='Use control evidence only; do not evaluate source-world contacts')
    parser.add_argument('--tempo-strategy', choices=('consensus', 'control', 'world', 'contact'),
                        default='consensus', help='Source-motion evidence family selection')
    parser.add_argument('--repair-loops', action='store_true',
                        help='Create separate bounded seam-corrected loop derivatives for review')
    parser.add_argument('--max-repairs', type=int, default=4,
                        help='Maximum bounded loop-correction proposals per action (1..12)')
    parser.add_argument('--repair-options', type=Path,
                        help='JSON LoopRepairOptions; for example root_policy="in_place"')


def completion_options(args):
    if type(args.max_repairs) is not int or not 1 <= args.max_repairs <= 12:
        raise ValueError('--max-repairs must be within 1..12')
    if args.no_world_space and args.tempo_strategy in ('world', 'contact'):
        raise ValueError('--no-world-space cannot select world or contact tempo evidence')
    options = None
    if args.repair_options is not None:
        if not args.repair_loops:
            raise ValueError('--repair-options requires --repair-loops')
        if args.repair_options.stat().st_size > 65536:
            raise ValueError('Loop correction settings exceed 64 KiB')
        options = json.loads(args.repair_options.read_text(encoding='utf-8'))
        if not isinstance(options, dict):
            raise ValueError('Loop correction settings must be a JSON object')
        from dancerudiments_authoring.loop_repair import LoopRepairOptions
        try:
            options = LoopRepairOptions(**options)
        except TypeError as exc:
            raise ValueError('Unknown loop correction setting: '+str(exc)) from exc
    return dict(world_space=not args.no_world_space, tempo_strategy=args.tempo_strategy,
                repair_loops=args.repair_loops, max_repairs=args.max_repairs,
                repair_options=options)

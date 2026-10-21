"""Inspect rig channels and compile captured motion onto the native pip clock."""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import sys

from ._validation import ScoreError
from .io import read_json
from .motion import load_rig_motion, write_rig_motion
from .recording import RecordingClock, _write_json_document, _write_bytes_document, write_recording


def _parser():
    parser = argparse.ArgumentParser(prog='dancerudiments-rig', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('catalogue', help='List pinned Rigify models and component types')
    commands.add_parser('sources', help='Show researched motion sources and their import/licence notes')
    profile = commands.add_parser('profile', help='Export a built-in numbered channel profile')
    profile.add_argument('model', help='Model identifier or syn:// type URL from catalogue')
    profile.add_argument('--kind', choices=('metarig', 'component'), default='metarig')
    profile.add_argument('--output', type=Path)
    profile.add_argument('--overwrite', action='store_true')
    channels = commands.add_parser('channels', help='Export every numbered parameter as CSV')
    channels.add_argument('profile', type=Path)
    channels.add_argument('--output', type=Path)
    channels.add_argument('--overwrite', action='store_true')
    compile_cmd = commands.add_parser('compile', help='Retiming and resampling of an explicit rig capture')
    compile_cmd.add_argument('capture', type=Path)
    compile_cmd.add_argument('output', type=Path)
    compile_cmd.add_argument('--name', default='rig_motion')
    timing = compile_cmd.add_mutually_exclusive_group(required=True)
    timing.add_argument('--source-bpm', type=float)
    timing.add_argument('--source-beat-map', type=Path)
    compile_cmd.add_argument('--source-beat-zero', type=float, help='Source seconds at beat zero; required with source BPM')
    compile_cmd.add_argument('--source-label', default='user-supplied source timing')
    compile_cmd.add_argument('--bpm-status', choices=('estimated', 'confirmed'), default='estimated')
    compile_cmd.add_argument('--phase-status', choices=('unverified', 'estimated', 'supplied'), default='supplied')
    compile_cmd.add_argument('--bpm', type=float, required=True, help='Nominal target BPM for the standard Recording clock')
    compile_cmd.add_argument('--beat-zero', type=float, default=0.0, help='Nominal target beat-zero seconds')
    compile_cmd.add_argument('--start-pip', type=int, default=0)
    compile_cmd.add_argument('--samples', type=int, required=True, help='Number of integer-pip rows (64 per beat)')
    compile_cmd.add_argument('--source-beat-offset', type=str, default='0')
    compile_cmd.add_argument('--motion-rate', type=str, default='1', help='Source beats per target beat; e.g. 1/2 or 2')
    compile_cmd.add_argument('--overwrite', action='store_true')
    inspect = commands.add_parser('inspect', help='Validate a self-contained rig motion and print its identity')
    inspect.add_argument('motion', type=Path)
    recording = commands.add_parser('recording', help='Export its N-dimensional data for the shared recording harness')
    recording.add_argument('motion', type=Path)
    recording.add_argument('output', type=Path)
    recording.add_argument('--overwrite', action='store_true')
    sample = commands.add_parser('sample', help='Sample physical parameters through the installed C++ runtime')
    sample.add_argument('motion', type=Path)
    sample.add_argument('--pip', type=int, required=True)
    sample.add_argument('--channel', type=int, help='Optional one-based parameter number')
    return parser


def _print(document):
    print(json.dumps(document, indent=2, ensure_ascii=True, allow_nan=False))


def _separate_output(output, *inputs):
    if any(path is not None and output.resolve() == path.resolve() for path in inputs):
        raise ScoreError('Output must be separate from the input documents, including when overwriting')


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == 'catalogue':
            from .rigs import rigify_catalogue
            _print(rigify_catalogue())
        elif args.command == 'sources':
            _print(read_json(Path(__file__).with_name('motion_sources') / 'manifest.json'))
        elif args.command == 'profile':
            from .rigs import load_builtin_profile
            profile = load_builtin_profile(args.model, kind=args.kind)
            if args.output:
                _write_json_document(args.output, profile.to_dict(), overwrite=args.overwrite)
            else:
                _print(profile.to_dict())
        elif args.command == 'channels':
            from .rigs import load_profile
            if args.output:
                _separate_output(args.output, args.profile)
            profile = load_profile(args.profile)
            buffer = io.StringIO(newline='')
            writer = csv.DictWriter(buffer, fieldnames=list(profile.channels[0].to_dict()))
            writer.writeheader()
            writer.writerows(channel.to_dict() for channel in profile.channels)
            if args.output:
                _write_bytes_document(args.output, buffer.getvalue().encode('utf-8'), overwrite=args.overwrite)
            else:
                sys.stdout.write(buffer.getvalue())
        elif args.command == 'compile':
            from .motion_clock import BeatMap
            from .motion_import import load_capture, compile_capture
            _separate_output(args.output, args.capture, args.source_beat_map)
            if args.source_bpm is not None:
                if args.source_beat_zero is None:
                    raise ScoreError('--source-bpm requires --source-beat-zero; BPM alone does not establish phase')
                source = BeatMap.from_bpm(args.source_bpm, beat_zero_seconds=args.source_beat_zero,
                                          source=args.source_label, bpm_status=args.bpm_status,
                                          phase_status=args.phase_status)
            else:
                if args.source_beat_zero is not None:
                    raise ScoreError('--source-beat-zero cannot override an explicit source beat map')
                source = BeatMap.from_dict(read_json(args.source_beat_map))
            clock = RecordingClock(args.bpm, 'user-supplied nominal playback tempo',
                                   args.bpm_status, args.beat_zero, 'supplied', args.start_pip)
            motion = compile_capture(load_capture(args.capture), name=args.name,
                                     source_beat_map=source, clock=clock, sample_count=args.samples,
                                     source_beat_offset=args.source_beat_offset, motion_rate=args.motion_rate)
            write_rig_motion(args.output, motion, overwrite=args.overwrite)
            _print(dict(path=str(args.output), type_uri=motion.type_uri,
                        profile_sha256=motion.profile.fingerprint,
                        channels=len(motion.profile.channels), samples=len(motion.recording.samples)))
        else:
            motion = load_rig_motion(args.motion)
            if args.command == 'inspect':
                _print(dict(name=motion.name, type_uri=motion.type_uri,
                            profile_sha256=motion.profile.fingerprint, motion_sha256=motion.fingerprint,
                            model=motion.profile.model, profile_version=motion.profile.version,
                            channel_count=len(motion.profile.channels),
                            sample_count=len(motion.recording.samples),
                            start_pip=motion.recording.clock.start_pip,
                            end_pip_exclusive=motion.recording.clock.start_pip + len(motion.recording.samples),
                            clock=motion.recording.to_dict()['clock'],
                            provenance=motion.recording.provenance))
            elif args.command == 'recording':
                _separate_output(args.output, args.motion)
                write_recording(args.output, motion.recording, overwrite=args.overwrite)
            elif args.command == 'sample':
                values = motion.player().by_channel(args.pip)
                selected = motion.profile.channels if args.channel is None else (motion.profile.channel(args.channel),)
                _print(dict(pip=args.pip, type_uri=motion.type_uri,
                            channels=[dict(number=c.number, name=c.name, value=values[c.number], unit=c.unit)
                                      for c in selected]))
    except (ScoreError, OSError, RuntimeError, IndexError) as exc:
        parser.exit(2, f'{parser.prog}: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

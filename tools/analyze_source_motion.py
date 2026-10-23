#!/usr/bin/env python3
"""Offline source-first StemLab analysis and beat-grid loop preview compilation.

Input is an ORIGINAL .bvh file or an evaluated Blender .capture.json Action,
never an already quantised .motion.json or native optional motion package.
This command does not download models, third-party assets or musical recordings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))

from dancerudiments_authoring._validation import ScoreError
from dancerudiments_authoring.bvh_import import load_bvh, override_bvh_frame_time
from dancerudiments_authoring.motion_import import load_capture
from dancerudiments_authoring.source_loop_analysis import (
    analyse_source_capture, source_capture_from_bvh,
)
from import_motion_collection import preflight


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Original .bvh or unquantised .capture.json')
    parser.add_argument('--output-dir', required=True, type=Path, help='New external analysis directory')
    parser.add_argument('--source-id', default='local_motion',
                        help='Stable source-skeleton identity for a .bvh input')
    parser.add_argument('--calibration-frames', type=int, default=0,
                        help='Exclude known T-pose lead-in frames from motion analysis (BVH only)')
    parser.add_argument('--frame-time-override', type=Path,
                        help='Reviewed JSON with frame_time_seconds and nonempty evidence (BVH only)')
    parser.add_argument('--axis-forward', default='-Z', help='BVH coordinate convention')
    parser.add_argument('--axis-up', default='Y', help='BVH coordinate convention')
    parser.add_argument('--unit-scale', type=float, default=1., help='Original BVH numerical unit scale')
    parser.add_argument('--location-range', type=float, default=10000., help='Source bounds')
    parser.add_argument('--translation-convention',
                        choices=('offset-plus-channel', 'blender-absolute'),
                        default='offset-plus-channel')
    parser.add_argument('--root-offset-policy', choices=('retain', 'motion'), default='retain')
    parser.add_argument('--min-bpm', type=float, default=60.)
    parser.add_argument('--max-bpm', type=float, default=200.)
    parser.add_argument('--target-bpm', type=float, help='Optional nominal audition tempo, NOT evidence')
    parser.add_argument('--max-previews', type=int, default=4,
                        help='Ranked beat-grid loop previews, 0..12; 0 analyses without conversion')
    parser.add_argument('--verify-native', action='store_true',
                        help='Require installed C++ native sampler and compare converted pip samples')
    args = parser.parse_args(argv)
    try:
        if not args.source.is_file():
            raise FileNotFoundError(f'Source file does not exist: {args.source}')
        output = args.output_dir.resolve()
        if output == args.source.resolve() or args.source.resolve().is_relative_to(output):
            raise ValueError('Analysis directory may not replace or contain the original source file')
        if output.exists() or output.is_symlink():
            raise FileExistsError('Analysis output must be a new directory')
        preflight(output.parent)
        raw_digest = hashlib.sha256(args.source.read_bytes()).hexdigest()
        if args.source.suffix.lower() == '.bvh':
            clip = load_bvh(args.source, source_id=args.source_id,
                axis_forward=args.axis_forward, axis_up=args.axis_up,
                unit_scale=args.unit_scale, location_range=args.location_range,
                translation_convention=args.translation_convention,
                root_offset_policy=args.root_offset_policy)
            if args.frame_time_override is not None:
                correction = json.loads(args.frame_time_override.read_text(encoding='utf-8'))
                if (not isinstance(correction, dict)
                        or set(correction) != {'frame_time_seconds', 'evidence'}):
                    raise ValueError('Frame-time override requires exact frame_time_seconds and evidence fields')
                clip = override_bvh_frame_time(clip, **correction)
            capture = source_capture_from_bvh(clip, calibration_frames=args.calibration_frames)
        elif args.source.name.lower().endswith('.capture.json'):
            if args.calibration_frames or args.frame_time_override is not None:
                raise ValueError('Blender capture timing/calibration must be selected during Action extraction')
            capture = load_capture(args.source)
        else:
            raise ValueError('Expected an original BVH or extracted .capture.json; not a compiled rig motion')
        result = analyse_source_capture(capture, output,
            original_source_sha256=raw_digest, min_bpm=args.min_bpm,
            max_bpm=args.max_bpm, target_bpm=args.target_bpm,
            max_previews=args.max_previews, verify_native=args.verify_native)
        print(json.dumps(dict(output=str(output), preview_count=result['preview_count'],
                              source_original_sha256=raw_digest,
                              native_verification_required=args.verify_native,
                              estimated_tempo_only=True), indent=2))
        return 0
    except (ValueError, RuntimeError, ScoreError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())

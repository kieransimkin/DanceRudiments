#!/usr/bin/env python3
"""Batch StemLab analysis of ORIGINAL cached motion-source archives, before conversion.

Reviewed source archives are verified against the existing import plan. Motion
samples are analyzed in source time, and only then are candidate loops compiled
to separate optional 64-pip previews. Original full-action packages are untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))

from dancerudiments_authoring._validation import ScoreError, canonical_json
from dancerudiments_authoring.bvh_import import BVHLimits, override_bvh_frame_time, parse_bvh
from dancerudiments_authoring.source_loop_analysis import (
    analyse_source_capture, source_capture_from_bvh,
)
from import_motion_collection import asset_path, preflight, slug, verify_archive


def analyze_collection(sources, cache_root, output_root, *, max_actions=100,
                       max_previews=4, min_bpm=60., max_bpm=200.,
                       target_bpm=None, verify_native=False):
    """Read only existing pinned ZIP members; create a new external report tree."""
    if type(max_actions) is not int or not 1 <= max_actions <= 1000:
        raise ValueError('max_actions must be 1..1000')
    output_root = Path(output_root).expanduser().absolute()
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError(f'Use a new analysis output directory: {output_root}')
    preflight(output_root.parent)
    limits = BVHLimits()
    index = dict(format='dancerudiments.source-motion-collection-analysis', schema_version=1,
                 max_actions=max_actions, input_sources=[source['id'] for source in sources],
                 motion_candidate_timing='source seconds, estimated beats only',
                 actions=[], failures=[], duplicates=[], truncated=False,
                 audio_beat_alignment_verified=False)
    seen = {}
    with tempfile.TemporaryDirectory(prefix='.source-collection-', dir=output_root.parent) as temp:
        staged = Path(temp) / 'result'
        staged.mkdir()
        stop = False
        for source in sources:
            options = source.get('conversion', {})
            profile_options = {k: options[k] for k in (
                'unit_scale', 'axis_forward', 'axis_up', 'location_range',
                'translation_convention', 'root_offset_policy') if k in options}
            plan_sha = hashlib.sha256(canonical_json(source).encode('ascii')).hexdigest()
            for asset in source['archives']:
                archive_path = asset_path(asset, cache_root)
                archive_sha = verify_archive(archive_path, asset)  # local only; no download
                with zipfile.ZipFile(archive_path) as archive:
                    members = sorted((x for x in archive.infolist()
                                      if x.filename.lower().endswith('.bvh')
                                      and not x.is_dir() and '__MACOSX/' not in x.filename
                                      and not PurePosixPath(x.filename).name.startswith('._')),
                                     key=lambda x: x.filename)
                    for member in members:
                        if len(index['actions']) + len(index['failures']) >= max_actions:
                            index['truncated'] = True
                            stop = True
                            break
                        provenance = dict(source_id=source['id'], source_plan_sha256=plan_sha,
                                          archive=asset['cache_path'], archive_sha256=archive_sha,
                                          member=member.filename, source_license=source['license'])
                        try:
                            if member.file_size > limits.max_file_bytes:
                                raise ScoreError('Source BVH exceeds bounded original import limits')
                            content = archive.read(member)
                            digest = hashlib.sha256(content).hexdigest()
                            provenance['source_sha256'] = digest
                            record = asset.get('members', {}).get(member.filename, {})
                            if record and record.get('sha256') != digest:
                                raise ScoreError('Member checksum differs from reviewed source plan')
                            if digest in seen:
                                index['duplicates'].append(dict(provenance, same_as=seen[digest]))
                                continue
                            clip = parse_bvh(content, source_id=source['id'],
                                             source_name=member.filename, **profile_options)
                            if record.get('frame_time_override') is not None:
                                correction = record['frame_time_override']
                                if not isinstance(correction, dict) or set(correction) != {
                                        'frame_time_seconds', 'evidence'}:
                                    raise ScoreError('Only an explicitly evidenced frame time override is supported')
                                clip = override_bvh_frame_time(clip, **correction)
                            omitted = record.get('calibration_frame_count', 0)
                            capture = source_capture_from_bvh(clip, calibration_frames=omitted)
                            name = (slug(source['id'], 20) + '_' +
                                    slug(PurePosixPath(member.filename).stem, 65) + '_' + digest[:10])
                            folder = staged / source['id'] / name
                            result = analyse_source_capture(capture, folder,
                                original_source_sha256=digest, min_bpm=min_bpm, max_bpm=max_bpm,
                                target_bpm=target_bpm, max_previews=max_previews,
                                verify_native=verify_native)
                            seen[digest] = member.filename
                            index['actions'].append(dict(provenance,
                                relative_output=folder.relative_to(staged).as_posix(),
                                profile_sha256=clip.profile.fingerprint,
                                original_duration_seconds=clip.duration_seconds,
                                preview_count=result['preview_count']))
                        except (ScoreError, ValueError, RuntimeError, OSError, zipfile.BadZipFile) as exc:
                            index['failures'].append(dict(provenance, error=str(exc)))
                    if stop:
                        break
                if stop:
                    break
            if stop:
                break
        index['analysed_action_count'] = len(index['actions'])
        index['failed_action_count'] = len(index['failures'])
        (staged / 'index.json').write_text(json.dumps(index, indent=2, allow_nan=False) + '\n',
                                           encoding='utf-8')
        if output_root.exists() or output_root.is_symlink():
            raise FileExistsError(f'Output appeared during analysis: {output_root}')
        staged.rename(output_root)
    return index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=ROOT / 'motion-packages/sources.json')
    parser.add_argument('--sources', nargs='+', required=True,
                        help='Reviewed sources from existing motion-packages/sources.json')
    parser.add_argument('--cache-root', type=Path, default=ROOT / '.cache/motion-sources')
    parser.add_argument('--output-root', type=Path, default=ROOT / '.cache/source-loop-candidates')
    parser.add_argument('--max-actions', type=int, default=100)
    parser.add_argument('--max-previews', type=int, default=4)
    parser.add_argument('--min-bpm', type=float, default=60.)
    parser.add_argument('--max-bpm', type=float, default=200.)
    parser.add_argument('--target-bpm', type=float)
    parser.add_argument('--verify-native', action='store_true')
    args = parser.parse_args(argv)
    try:
        plan = json.loads(args.plan.read_text(encoding='utf-8'))
        if (plan.get('format') != 'dancerudiments.motion-source-plan'
                or plan.get('schema_version') != 1):
            raise ValueError('Expected the current reviewed motion-source plan schema')
        available = {source['id']: source for source in plan['sources']}
        if len(set(args.sources)) != len(args.sources) or any(i not in available for i in args.sources):
            raise ValueError('Each --sources entry must be a distinct reviewed plan source ID')
        summary = analyze_collection([available[i] for i in args.sources], args.cache_root,
            args.output_root, max_actions=args.max_actions, max_previews=args.max_previews,
            min_bpm=args.min_bpm, max_bpm=args.max_bpm, target_bpm=args.target_bpm,
            verify_native=args.verify_native)
        print(json.dumps(dict(output=str(args.output_root),
                              analysed_action_count=summary['analysed_action_count'],
                              failed_action_count=summary['failed_action_count'],
                              truncated=summary['truncated']), indent=2))
        return 2 if summary['failures'] or summary['truncated'] else 0
    except (ValueError, RuntimeError, ScoreError, OSError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())

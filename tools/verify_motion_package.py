#!/usr/bin/env python3
"""Verify explicit optional packages, native playback, and complete pip chunks.

Each selected clip is decoded and semantically validated in full, one at a time.
Only its first, middle and last pips are compared through native SampledRecording.
Select all package shards belonging to a split original action: absent chunks
are reported as incomplete, never silently treated as independent whole clips.
No downloads, extraction, installs, registration or package changes occur.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from dancerudiments_authoring._validation import ScoreError, canonical_json, integer
from dancerudiments_authoring.motion_packages import MotionPackage
from dancerudiments_authoring.recording import _write_bytes_document
from import_motion_collection import file_hash, preflight


def _verify_clip(package, descriptor):
    motion = package.load(descriptor['id'])
    recording = motion.recording
    native = motion.to_native()
    start, count = recording.clock.start_pip, len(recording.samples)
    checked = sorted({start, start + count // 2, start + count - 1})
    for pip in checked:
        if tuple(native.sample(pip)) != recording.samples[pip - start]:
            raise ScoreError(f'Native sample differs from the stored float64 row at pip {pip}')
    outside = []
    for pip in (start - 1, start + count):
        if not -2147483648 <= pip <= 2147483647:
            continue  # This integer is outside the native pip API's domain.
        try:
            native.sample(pip)
        except IndexError:
            outside.append(pip)
        else:
            raise ScoreError(f'Native playback accepted out-of-range pip {pip}')
    metadata = recording.provenance
    chunk_fields = ('original_clip_id', 'chunk_index', 'chunk_count', 'total_sample_count',
                    'chunk_start_pip', 'chunk_sample_count')
    descriptor_metadata = descriptor.get('metadata', {})
    for key in chunk_fields:
        if key in descriptor_metadata and key in metadata and descriptor_metadata[key] != metadata[key]:
            raise ScoreError(f'Manifest and Recording disagree on {key}')
    # Packages may add grouping metadata to an existing standalone Recording.
    # Compare duplicate declarations, then use either documented location;
    # original_clip_id alone is descriptive provenance, not a chunk contract.
    grouping = dict(metadata, **descriptor_metadata)
    result = dict(clip_id=motion.name, profile_sha256=motion.profile.fingerprint,
                  start_pip=start, sample_count=count, checked_pips=checked,
                  checked_out_of_range_pips=outside, clock_bpm=recording.clock.bpm,
                  clock_beat_zero_seconds=recording.clock.beat_zero_seconds)
    if any(key in grouping for key in ('chunk_index', 'chunk_count')):
        if any(key not in grouping for key in ('original_clip_id', 'chunk_index', 'chunk_count')):
            raise ScoreError('Incomplete original-action chunk metadata')
        original = grouping['original_clip_id']
        if not isinstance(original, str) or not original or len(original) > 512:
            raise ScoreError('Invalid original_clip_id')
        chunk_count = integer(grouping['chunk_count'], 1, 2147483647, 'chunk_count')
        chunk_index = integer(grouping['chunk_index'], 0, chunk_count - 1, 'chunk_index')
        total = grouping.get('total_sample_count')
        if total is not None:
            integer(total, 1, 4294967295, 'total_sample_count')
        if 'chunk_start_pip' in grouping:
            integer(grouping['chunk_start_pip'], -2147483648, 2147483647, 'chunk_start_pip')
            if grouping['chunk_start_pip'] != start:
                raise ScoreError('Chunk metadata does not match actual Recording bounds')
        if 'chunk_sample_count' in grouping:
            integer(grouping['chunk_sample_count'], 1, 4294967295, 'chunk_sample_count')
            if grouping['chunk_sample_count'] != count:
                raise ScoreError('Chunk metadata does not match actual Recording bounds')
        result.update(original_clip_id=original, chunk_index=chunk_index, chunk_count=chunk_count,
                      total_sample_count=total, chunk_start_pip=start, chunk_sample_count=count)
    if package.cached_clip_ids:
        raise ScoreError('Verification must not retain decoded clips in a package cache')
    return result


def verify_packages(paths):
    # Fail once, before the full validation pass, if the native runtime is absent.
    from dancerudiments import SampledRecording  # noqa: F401

    packages, failures, groups = [], [], defaultdict(list)
    profiles = set()
    verified_clips = standalone = 0
    seen_paths = set()
    for path_value in paths:
        path = Path(path_value)
        manifest_path = (path / 'manifest.json' if path.is_dir() else path).resolve()
        if manifest_path in seen_paths:
            raise ScoreError(f'Package was selected twice: {manifest_path}')
        seen_paths.add(manifest_path)
        item = dict(path=str(manifest_path), verified_clips=0, failures=[])
        try:
            with MotionPackage(manifest_path, cache_size=0) as package:
                manifest = package.manifest
                profile = package.profile
                profiles.add(profile.fingerprint)
                item.update(package_id=manifest['id'], version=manifest['version'],
                    manifest_sha256=file_hash(manifest_path), profile_sha256=profile.fingerprint,
                    profile_asset_sha256=manifest['profile']['sha256'],
                    clip_asset_set_sha256=hashlib.sha256(canonical_json([
                        dict(id=c['id'], sha256=c['sha256']) for c in manifest['clips']
                    ]).encode('ascii')).hexdigest(), declared_clips=len(manifest['clips']))
                for descriptor in manifest['clips']:
                    try:
                        clip = _verify_clip(package, descriptor)
                        verified_clips += 1
                        item['verified_clips'] += 1
                        if 'original_clip_id' in clip:
                            key = (clip['original_clip_id'], clip['profile_sha256'],
                                   clip['clock_bpm'], clip['clock_beat_zero_seconds'])
                            groups[key].append(dict(clip, package_id=manifest['id']))
                        else:
                            standalone += 1
                    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
                        failure = dict(package=str(manifest_path), clip_id=descriptor['id'], error=str(exc))
                        item['failures'].append(failure)
                        failures.append(failure)
                    if (item['verified_clips'] + len(item['failures'])) % 10 == 0:
                        print(json.dumps(dict(package=manifest['id'], verified=item['verified_clips'],
                                              failed=len(item['failures']))), file=sys.stderr, flush=True)
        except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
            failure = dict(package=str(manifest_path), error=str(exc))
            item['failures'].append(failure)
            failures.append(failure)
        item['passed'] = not item['failures']
        packages.append(item)
    complete_groups = []
    for key, chunks in sorted(groups.items()):
        original, profile, bpm, phase = key
        try:
            chunk_counts = {c['chunk_count'] for c in chunks}
            totals = {c['total_sample_count'] for c in chunks if c['total_sample_count'] is not None}
            if len(chunk_counts) != 1 or len(totals) > 1:
                raise ScoreError('Original-action chunks disagree on counts')
            count = next(iter(chunk_counts))
            total = next(iter(totals)) if totals else sum(c['sample_count'] for c in chunks)
            ordered = sorted(chunks, key=lambda c: c['chunk_index'])
            if len(ordered) != count or [c['chunk_index'] for c in ordered] != list(range(count)):
                raise ScoreError('Original action is missing chunks or has duplicate chunk indices')
            for previous, current in zip(ordered, ordered[1:]):
                if previous['start_pip'] + previous['sample_count'] != current['start_pip']:
                    raise ScoreError('Original action has a gap or overlap between pip chunks')
            if sum(c['sample_count'] for c in ordered) != total:
                raise ScoreError('Original-action sample total differs from its complete chunks')
            complete_groups.append(dict(original_clip_id=original, profile_sha256=profile,
                chunk_count=count, sample_count=total, start_pip=ordered[0]['start_pip'],
                last_pip=ordered[-1]['start_pip'] + ordered[-1]['sample_count'] - 1,
                bpm=bpm, beat_zero_seconds=phase))
        except ValueError as exc:
            failures.append(dict(original_clip_id=original, profile_sha256=profile, error=str(exc)))
    return dict(format='dancerudiments.motion-package-verification', schema_version=1,
        checked_utc=datetime.now(timezone.utc).isoformat(), python=platform.python_version(),
        passed=not failures, package_count=len(packages), verified_clips=verified_clips,
        profile_count=len(profiles), complete_original_actions=len(complete_groups),
        standalone_clips=standalone, packages=packages, actions=complete_groups, failures=failures,
        scope='Every selected clip: integrity, full Recording/profile semantics and quaternion validation; '
              'native first/middle/last samples plus out-of-range checks; original-action chunk completeness')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packages', nargs='+', type=Path, help='Explicit package directories or manifest paths')
    parser.add_argument('--report', type=Path, help='Write a JSON validation receipt; packages remain unchanged')
    args = parser.parse_args(argv)
    if args.report:
        preflight(args.report.parent)
    report = verify_packages(args.packages)
    if args.report:
        _write_bytes_document(args.report, canonical_json(report).encode('ascii'), overwrite=True)
        print(json.dumps({key: report[key] for key in ('passed', 'package_count', 'verified_clips',
              'profile_count', 'complete_original_actions', 'standalone_clips', 'failures')}))
    else:
        print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())

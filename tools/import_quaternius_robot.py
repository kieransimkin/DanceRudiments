#!/usr/bin/env python3
"""Rebuild the optional CC0 Robot package from an explicitly supplied local ZIP.

No downloads, embedded scripts, inferred beats or default-catalogue registration.
Run with the pinned bpy 5.2.2 environment and matching native extension.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))

from dancerudiments_authoring._validation import ScoreError, canonical_json
from dancerudiments_authoring.blender_import import (
    main as import_main, rebind_source_capture, union_source_profile,
)
from dancerudiments_authoring.io import read_json
from dancerudiments_authoring.motion_clock import BeatMap
from dancerudiments_authoring.motion_import import compile_capture, load_capture
from dancerudiments_authoring.motion_packages import (
    MotionPackage, MotionPackageBuilder, export_motion_package,
)
from dancerudiments_authoring.recording import RecordingClock

SOURCE_URL = 'https://opengameart.org/content/animated-lowpoly-robot'
DOWNLOAD_URL = 'https://opengameart.org/sites/default/files/Animated%20Robot%20-%20Oct%202018.zip'
ARCHIVE_SHA256 = '5128d2cf906835895b931f6c1e764296ba2e01d3a30d809035fc6c1ee8a1c1ee'
ARCHIVE_BYTES = 7_015_900
FILES = (
    ('Animated Robot - Oct 2018/Blend/Robot.blend', 'sources/Robot.blend', 1_899_312,
     '06689f194aba7af110b10cb0a3fb8d42bfd70dd6dc6f4bc9a231c51f314a84b0'),
    ('Animated Robot - Oct 2018/FBX/Robot.fbx', 'sources/Robot.fbx', 3_297_804,
     '38afb56db7fb17a74d30f0afc8adb5f00441a94e65d6b8ac1958732480f79eb8'),
    ('Animated Robot - Oct 2018/License.txt', 'LICENSE.txt', 364,
     '83d8959f9fc56353ed571fbe2dc52e4bcd64508e2399501cd45ac2ce3df0bf8c'),
)
TIME_SOURCE = ('Time-only duration coordinate: 60 BPM means one second per beat; '
               'musical tempo and phase are unverified')
README = '''# Quaternius Robot motion package

This optional package contains all 14 original Robot Actions, including Robot_Dance, from quaternius's CC0 Animated Lowpoly Robot. The source archive, original Robot.blend/Robot.fbx and licence have been preserved separately. The source mesh is not embedded in this motion-only package.

The package uses one exact 178-channel source skeleton profile, including fingers and the original rest basis. It is not a Rigify retarget. The profile contains enough named hierarchy/rest metadata to reconstruct a compatible carrier with `dancerudiments_authoring.blender_import.create_source_armature`.

Import only the package needed by a scene. `MotionPackage(path).load("quaternius_robot_dance")` loads one recording; its `.player().sample(pip)` uses the native C++ sampler. The default package cache holds one clip, and importing DanceRudiments does not discover or load this data.

Timing is explicitly **time-only**: 60 BPM represents one second per beat and 64 pips per second. Musical tempo, downbeat and phase have not been inferred or verified. Each original Action starts at source frame zero, captured at 24 fps; the compiler retains pips at or before the last captured endpoint. Use explicit beat annotations and recompile for musical alignment. No looping or foot-contact correction is implicit.

Source: https://opengameart.org/content/animated-lowpoly-robot
Licence: CC0-1.0; see LICENSE.txt and SOURCES.json for exact provenance/hashes.
'''
NOTICES = ('# Third-party motion notice\n\nThe robot model and original animations are by quaternius, '
           'distributed under CC0 1.0 on the creator-uploaded OpenGameArt page: '
           'https://opengameart.org/content/animated-lowpoly-robot . The original licence text is preserved '
           'in LICENSE.txt.\n\nOnly the original BLEND Actions were imported; the equivalent FBX is not '
           'counted again. No music, inferred beats, learned motion or generated dance has been added.\n')


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def extract_known_archive(archive, work, source_record=None):
    if archive.stat().st_size != ARCHIVE_BYTES or digest(archive.read_bytes()) != ARCHIVE_SHA256:
        raise ScoreError('Source ZIP differs from the verified creator archive; review the new source before importing')
    record = dict(source_url=SOURCE_URL, download_url=DOWNLOAD_URL, author='quaternius',
                  license='CC0-1.0', license_url='https://creativecommons.org/publicdomain/zero/1.0/',
                  sha256=ARCHIVE_SHA256, bytes=ARCHIVE_BYTES, source_verified_on='2026-10-21',
                  extracted_files=[dict(archive_path=member, local_path=local, sha256=sha, bytes=size)
                                   for member, local, size, sha in FILES])
    if source_record is not None:
        supplied = read_json(source_record)
        # Retain the original ingestion date without pretending a local rerun
        # downloaded anything. Every source identity field must still agree.
        for key, value in record.items():
            if key != 'source_verified_on' and supplied.get(key) != value:
                raise ScoreError(f'Supplied source record differs at {key}')
        canonical_json(supplied)
        record = supplied
    with zipfile.ZipFile(archive) as zipped:
        names = [info.filename for info in zipped.infolist()]
        for member, local, size, sha in FILES:
            if names.count(member) != 1 or zipped.getinfo(member).file_size != size:
                raise ScoreError('Source archive has a missing, duplicated or unexpectedly sized member')
            payload = zipped.read(member)
            if digest(payload) != sha:
                raise ScoreError(f'Source member checksum differs: {member}')
            target = work / local
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    shutil.copyfile(archive, work / 'Animated_Robot_Oct_2018.zip')
    (work / 'source-record.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def build(archive, work, output, *, package_archive=None, source_record=None):
    if work.exists() or output.exists() or (package_archive is not None and package_archive.exists()):
        raise ScoreError('Work, package and archive outputs must all name new paths')
    if work == output or work in output.parents or output in work.parents:
        raise ScoreError('Work and optional package directories must be separate siblings or independent paths')
    parents = {work.parent, output.parent}
    if package_archive is not None:
        if package_archive == archive or work in package_archive.parents or output in package_archive.parents:
            raise ScoreError('Package ZIP must be a separate new artifact outside work and package directories')
        parents.add(package_archive.parent)
    for parent in parents:
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='preflight-', dir=parent) as directory:
            path = Path(directory) / 'probe'
            path.write_bytes(b'probe')
            assert path.read_bytes() == b'probe'
            renamed = path.with_name('renamed')
            path.rename(renamed)
            assert renamed.read_bytes() == b'probe'
            renamed.unlink()
    work.mkdir()
    record = extract_known_archive(archive, work, source_record)
    import bpy
    if tuple(bpy.app.version) != (5, 2, 2):
        raise ScoreError('This verified import recipe requires bpy 5.2.2; changed runtimes produce a new profile identity')
    import_main(['extract', str(work / 'sources/Robot.blend'), '--source-id', 'quaternius_robot',
                 '--output-dir', str(work / 'extracted')])
    index = read_json(work / 'extracted/index.json')
    if len(index['captures']) != 14 or index['failures'] or index['source_fps'] != 24:
        raise ScoreError('Expected exactly 14 successful original Actions at 24 fps')
    captures = [load_capture(work / 'extracted' / item['capture']) for item in index['captures']]
    profile = union_source_profile(capture.profile for capture in captures)
    if len(profile.channels) != 178:
        raise ScoreError('Source evaluation changed the verified 178-channel union; inspect before packaging')
    builder = MotionPackageBuilder(
        output, package_id='quaternius_robot', version='1.0.0',
        title='Quaternius Robot: 14 source skeleton actions', profile=profile,
        license=dict(spdx='CC0-1.0', author='quaternius', source_url=SOURCE_URL,
                     commercial_use=True, raw_redistribution=True, notice='LICENSE.txt'),
        provenance=dict(source_record=record, import_source_sha256=index['source']['sha256'],
                        importer='dancerudiments_authoring.blender_import', blender_version=index['blender_version'],
                        source_capture_method='Creator-authored animation imported from the original BLEND Actions',
                        source_fps=24, timing_kind='time-only', timing_note=TIME_SOURCE,
                        source_action_count=14, retargeting='none; original source skeleton, not Rigify controls',
                        portable_skeleton='profile.json source.skeleton',
                        mesh='Original licensed Robot.blend/Robot.fbx retained in the separate original asset bundle; no mesh inside this motion package',
                        compiler='dancerudiments_authoring.motion_import.compile_capture',
                        sample_grid='64 native integer pips per second under the explicit time-only 60 BPM coordinate',
                        endpoint_policy='Last pip at or before the original captured endpoint; no endpoint extension or looping'))
    clock = RecordingClock(60, TIME_SOURCE)
    beat_map = BeatMap.from_bpm(60, beat_zero_seconds=0, source=TIME_SOURCE)
    for item, capture in zip(index['captures'], captures):
        count = int(Fraction(str(capture.frame_times_seconds[-1])) * 64) + 1
        motion = compile_capture(rebind_source_capture(capture, profile), name='quaternius_' + item['action'].lower(),
                                 source_beat_map=beat_map, clock=clock, sample_count=count)
        metadata = dict(title=item['action'], source_action=item['action'], source_binding_id=item['binding_id'],
                        original_clip_id=item['action'], chunk_index=0, chunk_count=1, timing_kind='time-only',
                        source_frame_count=item['frame_count'], source_duration_seconds=item['duration_seconds'],
                        source_frame_start=capture.provenance['blender_frame_start'],
                        source_frame_end=capture.provenance['blender_frame_end'], source_fps=24,
                        capture_sha256=capture.fingerprint, source_profile_sha256=capture.profile.fingerprint,
                        category='dance' if item['action'] == 'Robot_Dance' else 'general animation',
                        last_sample_seconds=(count - 1) / 64, musical_beat_annotations=None,
                        unsupported_animation=item['unsupported_animation'], retargeting='none')
        builder.add(motion, metadata=metadata)
    manifest = builder.finalize()
    shutil.copyfile(work / 'LICENSE.txt', output / 'LICENSE.txt')
    shutil.copyfile(work / 'source-record.json', output / 'SOURCES.json')
    (output / 'README.md').write_text(README)
    (output / 'THIRD_PARTY_NOTICES.md').write_text(NOTICES)
    verified = 0
    with MotionPackage(output, expected_profile=profile, cache_size=1) as package:
        for item in package.catalogue():
            motion = package.load(item['id'])
            player = motion.player()
            for index, row in enumerate(motion.recording.samples):
                actual = player.sample(motion.recording.clock.start_pip + index)
                expected = profile.decode(row)
                if max(abs(a - b) for a, b in zip(actual, expected)) > 1e-10:
                    raise ScoreError('Native playback differs from the validated package recording')
                verified += 1
            assert package.cached_clip_ids == (item['id'],)
    report = dict(status='passed', package=str(output), clip_count=len(manifest['clips']),
                  profile_sha256=profile.fingerprint, channels=len(profile.channels),
                  native_samples_verified=verified,
                  manifest_sha256=digest((output / 'manifest.json').read_bytes()))
    if package_archive is not None:
        export_motion_package(output, package_archive)
        report.update(archive=str(package_archive), archive_sha256=digest(package_archive.read_bytes()),
                      archive_bytes=package_archive.stat().st_size)
    (work / 'package-report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path, help='Previously downloaded original public ZIP')
    parser.add_argument('--work-dir', required=True, type=Path, help='New retained source/capture/evidence directory')
    parser.add_argument('--output-dir', required=True, type=Path, help='New optional motion package directory')
    parser.add_argument('--package-archive', type=Path, help='Optional new deterministic package ZIP')
    parser.add_argument('--source-record', type=Path, help='Original verified source-record.json for identical ingestion provenance')
    args = parser.parse_args(argv)
    report = build(args.archive.resolve(), args.work_dir.resolve(), args.output_dir.resolve(),
                   package_archive=args.package_archive.resolve() if args.package_archive else None,
                   source_record=args.source_record.resolve() if args.source_record else None)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    raise SystemExit(main(arguments))

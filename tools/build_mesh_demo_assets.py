#!/usr/bin/env python3
"""Build two explicit, pinned optional motion packages for the mesh showcase.

Only --download permits missing source downloads. The reviewed recipe names two
small original BVH files, not the bulk CMU archive. Original frames, calibration,
licence and source timing evidence are retained. Offline compilation uses the
existing BVH importer, MotionPackageBuilder and native Recording verifier.
No renderer, live sampler, installation or network request runs on import.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
sys.path.insert(0, str(ROOT / 'tools'))

from acquire_cmu_dance import _ensure_file
from dancerudiments_authoring._validation import ScoreError, canonical_json
from dancerudiments_authoring.bvh_import import compile_bvh, parse_bvh, override_bvh_frame_time
from dancerudiments_authoring.io import _pairs
from dancerudiments_authoring.motion_packages import MotionPackage, MotionPackageBuilder
from import_motion_collection import preflight
from verify_motion_package import verify_packages

DEFAULT_SOURCES = ROOT / 'tools/mesh_demo_sources.json'
MAX_SOURCE_BYTES = 8 * 1024 * 1024
CONVERSION = dict(axis_forward='-Z', axis_up='Y', location_range=10000.,
                  root_offset_policy='motion', translation_convention='offset-plus-channel',
                  unit_scale=1.)
TIMING_LABEL = ('Time-only capture playback; musical BPM and beat phase are unverified. '
                '60 BPM is a seconds coordinate, not the source music tempo.')


def _bytes(value):
    return canonical_json(value).encode('ascii')


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _hash(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ScoreError(f'{label} requires a pinned lowercase SHA-256')


def _relative(value):
    if (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_./-]+', value)
            or PurePosixPath(value).is_absolute()
            or any(part in ('', '.', '..') for part in value.split('/'))):
        raise ScoreError('Expected a safe relative source path')
    return value


def validate_sources(document):
    """Validate the reviewed two-scene recipe before any cache/output mutation."""
    if (not isinstance(document, dict) or document.get('schema_version') != 1
            or document.get('format') != 'dancerudiments.mesh-demo-sources'
            or document.get('source_id') != 'cmu_dance'):
        raise ScoreError('Unsupported mesh demo source recipe')
    commit = document.get('mirror_commit')
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ScoreError('Source mirror commit must be immutable')
    if document.get('conversion') != CONVERSION:
        raise ScoreError('Mesh demo conversion must retain the reviewed coordinate policy')
    licence = document.get('license', {})
    if licence.get('id') != 'LicenseRef-CMU-Mocap':
        raise ScoreError('These motions retain the custom CMU source terms')
    _relative(licence.get('local_text'))
    _hash(licence.get('local_text_sha256'), 'Licence text')
    scenes = document.get('scenes')
    if (not isinstance(scenes, list) or len(scenes) != 2
            or {s.get('id') for s in scenes if isinstance(s, dict)} != {'boxbot', 'prism'}):
        raise ScoreError('The demo recipe must select boxbot and prism exactly once')
    total, source_ids, package_ids = 0, set(), set()
    prefix = 'https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/' + commit + '/'
    for scene in scenes:
        if scene.get('characterKind') != scene['id']:
            raise ScoreError('A scene must use its explicitly selected procedural character')
        package_id = scene.get('packageId')
        if (not isinstance(package_id, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,127}', package_id)
                or package_id in package_ids):
            raise ScoreError('Demo package IDs must be valid and distinct')
        package_ids.add(package_id)
        if scene.get('version') != '1.0.0':
            raise ScoreError('Review the mesh demo recipe before changing package versions')
        for key in ('title', 'description'):
            if not isinstance(scene.get(key), str) or not scene[key].strip():
                raise ScoreError(f'Scene {key} is required')
        source = scene.get('source', {})
        identifier = source.get('id')
        if (not isinstance(identifier, str) or not re.fullmatch(r'[0-9]{2,3}_[0-9]{2}', identifier)
                or identifier in source_ids):
            raise ScoreError('Each demo needs a distinct pinned original motion ID')
        source_ids.add(identifier)
        if (source.get('cache_path') != f'raw/{identifier}.bvh'
                or source.get('member') != f'bvh/{identifier}.bvh'):
            raise ScoreError('BVH source paths must match the reviewed motion ID')
        repository_path = _relative(source.get('repository_path'))
        if source.get('download_url') != prefix + repository_path:
            raise ScoreError('Only the exact immutable source BVH URL may be downloaded')
        size = source.get('byte_length')
        if type(size) is not int or not 1 <= size <= 4 * 1024 * 1024:
            raise ScoreError('Selected BVH exceeds the 4 MiB per-file budget')
        total += size
        _hash(source.get('sha256'), 'Source BVH')
        if not isinstance(source.get('git_blob_sha1'), str) or not re.fullmatch(r'[0-9a-f]{40}', source['git_blob_sha1']):
            raise ScoreError('Source Git blob identity is required')
        if source.get('calibration_frame_count') != 1 or source.get('first_frame_kind') != 'converter-added-calibration-t-pose':
            raise ScoreError('The converter calibration frame must be retained and labelled')
        if source.get('timing_kind') != 'time-only' or source.get('music_beat_metadata') is not None:
            raise ScoreError('The selected source has no established musical beat mapping')
        target = scene.get('expectedProfile', {})
        _hash(target.get('fingerprint'), 'Expected scene profile')
        _hash(scene.get('sceneRigSha256'), 'Expected scene rig')
        if not isinstance(target.get('type_uri'), str) or not target['type_uri'].startswith('syn://type/danceflow/motion/skeletal/source/cmu_dance/'):
            raise ScoreError('Expected profile must be a separately typed CMU source skeleton')
        dims = target.get('dimensions')
        if (not isinstance(dims, list) or not 1 <= len(dims) <= 256
                or any(not isinstance(d, str) for d in dims) or len(set(dims)) != len(dims)):
            raise ScoreError('Expected scene dimensions must be independently pinned and ordered')
    if total > MAX_SOURCE_BYTES:
        raise ScoreError('Selected sources exceed the explicit 8 MiB download budget')
    return json.loads(canonical_json(document))


def load_sources(path=DEFAULT_SOURCES):
    path = Path(path)
    if path.stat().st_size > 256 * 1024:
        raise ScoreError('Demo source recipe exceeds 256 KiB')
    return validate_sources(json.loads(path.read_text('utf-8'), object_pairs_hook=_pairs))


def profile_identity(profile):
    return dict(type_uri=profile.type_uri, fingerprint=profile.fingerprint,
                dimensions=list(profile.dimensions))


def scene_rig(profile, *, scene_id, character_kind):
    """Export static bind geometry and physical channel indices, never samples."""
    import numpy as np

    source = profile.source
    skeleton = source['skeleton']
    by_name = {bone['name']: i for i, bone in enumerate(skeleton)}
    matrices = [np.asarray(b['rest_matrix'], dtype=np.float64).reshape(4, 4) for b in skeleton]
    bvh = {joint['name']: joint for joint in source['bvh']['joints']}
    conversion = np.asarray(source['bvh']['source_to_blender']).reshape(3, 3)
    scale = source['bvh']['source_unit_to_blender_unit']
    joints, points = [], []
    for i, bone in enumerate(skeleton):
        parent = by_name[bone['parent']] if bone['parent'] is not None else -1
        if parent >= i:
            raise ScoreError('Scene bind hierarchy must be in parent-before-child order')
        local = np.linalg.inv(matrices[parent]) @ matrices[i] if parent >= 0 else matrices[i]
        if not np.allclose(local[:3, :3], np.eye(3), rtol=0, atol=1e-12):
            raise ScoreError('This procedural mesh recipe requires identity BVH rest rotations')
        indices = {}
        for path, size in (('location', 3), ('rotation_quaternion', 4), ('scale', 3)):
            found = {c.array_index: column for column, c in enumerate(profile.channels)
                     if c.bone == bone['name'] and c.data_path == path}
            if found and set(found) != set(range(size)):
                raise ScoreError('The scene needs complete physical transform channel groups')
            indices[path] = [found[j] for j in range(size)] if found else None
        ends = [(conversion @ np.asarray(v) * scale).tolist() for v in bvh[bone['name']]['end_sites']]
        points.append(matrices[i][:3, 3])
        points.extend(matrices[i][:3, 3] + np.asarray(v) for v in ends)
        joints.append(dict(name=bone['name'], parentIndex=parent,
            offset=local[:3, 3].tolist(), restMatrix=bone['rest_matrix'], length=bone['length'],
            endSites=ends, positionChannelIndices=indices['location'],
            rotationChannelIndices=indices['rotation_quaternion'], scaleChannelIndices=indices['scale']))
    minimum, maximum = np.min(points, axis=0), np.max(points, axis=0)
    return dict(format='dancerudiments.mesh-demo-rig', schema_version=1, sceneId=scene_id,
        characterKind=character_kind, expectedProfile=profile_identity(profile),
        coordinateSystem=dict(up='+Z', forward='+Y', handedness='right',
                              unitPolicy=source['bvh']['unit_policy']),
        matrixLayout='row-major', quaternionOrder='wxyz', rootOffsetPolicy=source['bvh']['root_offset_policy'],
        channels=[c.to_dict() for c in profile.channels], joints=joints,
        sourceSkeleton=skeleton, omittedNeutralGroups=source['omitted_neutral_groups'],
        restBounds=dict(minimum=minimum.tolist(), maximum=maximum.tolist(), size=(maximum-minimum).tolist()))


def _prepare_clip(document, scene, cache_root):
    source = scene['source']
    clip = parse_bvh((cache_root / source['cache_path']).read_bytes(), source_id=document['source_id'],
                    source_name=source['member'], **document['conversion'])
    if (clip.source_sha256 != source['sha256'] or clip.frame_count != source['frame_count']
            or clip.frame_time_seconds != Fraction(source['frame_time_seconds'])):
        raise ScoreError('Parsed source frame identity differs from the reviewed recipe')
    if source.get('frame_time_override') is not None:
        clip = override_bvh_frame_time(clip, **source['frame_time_override'])
    if (clip.frame_time_seconds != Fraction(source['effective_frame_time_seconds'])
            or not math.isclose(clip.duration_seconds, source['effective_duration_seconds'], rel_tol=0, abs_tol=1e-10)):
        raise ScoreError('Effective source timing differs from the reviewed recipe')
    if profile_identity(clip.profile) != scene['expectedProfile']:
        raise ScoreError('Compiled profile differs from the independently pinned scene identity')
    metadata = dict(clip.metadata, source_url=source['source_url'], source_download_url=source['download_url'],
        source_git_blob_sha1=source['git_blob_sha1'], source_mirror_commit=document['mirror_commit'],
        original_motion_id=source['id'], source_title=source['title'],
        calibration_frame_count=source['calibration_frame_count'], first_frame_kind=source['first_frame_kind'],
        trimmed_source_frames=0, timing_kind='time-only', music_timing_verified=False,
        scene_id=scene['id'], character_kind=scene['characterKind'])
    return replace(clip, metadata_json=canonical_json(metadata))


def _write_notices(directory, document, scene, licence):
    source = scene['source']
    text = ('# Source motion notice\n\n' + document['license']['attribution'] + '\n\n' +
        document['license']['conversion_attribution'] + '\n\n' +
        f"Motion: CMU {source['id']} — {source['title']}\n\nSource: {source['source_url']}\n\n" +
        'Custom CMU terms apply to the motion data, including no direct resale of original or converted data. '
        'The procedural mesh and software licence do not replace these source terms. See LICENSE.txt.\n\n' +
        'All source frames remain, including the converter-added first calibration T-pose. '
        'Finger/thumb convenience joints are not measured finger motion. '
        'Original numerical units are retained without claiming metres.\n\n' + TIMING_LABEL + '\n\n' +
        'Changes: explicit source axes and root-origin policy; local Euler rotations converted to '
        'unit quaternions; offline resampling across the complete valid 64-pip time grid; gzip packaging. '
        'No Rigify retarget, cropping, loop synthesis or automatic beat detection. '
        'Any evidenced frame-rate correction is preserved in SOURCES.json and clip provenance.\n')
    (directory / 'LICENSE.txt').write_bytes(licence)
    (directory / 'THIRD_PARTY_NOTICES.md').write_text(text, encoding='utf-8')
    (directory / 'README.md').write_text(f"# {scene['title']}\n\n{scene['description']}\n\n" +
        'This optional, character-specific motion package uses the original source skeleton. '
        'See THIRD_PARTY_NOTICES.md for attribution, calibration and timing.\n', encoding='utf-8')
    (directory / 'SOURCES.json').write_bytes(_bytes(dict(format='dancerudiments.mesh-demo-source-record',
        schema_version=1, source_id=document['source_id'], source=source, license=document['license'],
        conversion=document['conversion'], mirror_commit=document['mirror_commit'],
        scene_id=scene['id'], source_plan_sha256=_sha(_bytes(document)))))


def _reference_world_matrices(profile, physical_values):
    """Offline reference FK from saved rest matrices, independent of browser code.

    The native engine supplies every sample. This routine only evaluates that
    selected pose for cross-language QA; it is not a motion sampler or renderer.
    """
    import numpy as np

    skeleton = profile.source['skeleton']
    controls = {b['name']: dict(location=np.zeros(3), rotation_quaternion=np.array([1., 0., 0., 0.]),
                                scale=np.ones(3)) for b in skeleton}
    for group in profile.source['omitted_neutral_groups']:
        controls[group['bone']][group['data_path']] = np.asarray(group['values'], dtype=np.float64)
    for channel, value in zip(profile.channels, physical_values):
        controls[channel.bone][channel.data_path][channel.array_index] = value
    rest = {b['name']: np.asarray(b['rest_matrix'], dtype=np.float64).reshape(4, 4) for b in skeleton}
    world = {}
    for bone in skeleton:
        values = controls[bone['name']]
        quaternion = values['rotation_quaternion']
        quaternion = quaternion / np.linalg.norm(quaternion)
        w, x, y, z = quaternion
        cross = np.asarray(((0., -z, y), (z, 0., -x), (-y, x, 0.)))
        rotation = np.eye(3) + 2*w*cross + 2*(cross @ cross)
        basis = np.eye(4)
        basis[:3, :3] = rotation @ np.diag(values['scale'])
        basis[:3, 3] = values['location']
        if bone['parent'] is None:
            matrix = rest[bone['name']] @ basis
        else:
            parent = bone['parent']
            matrix = world[parent] @ np.linalg.inv(rest[parent]) @ rest[bone['name']] @ basis
        world[bone['name']] = matrix
    return [world[b['name']].reshape(-1).tolist() for b in skeleton]


def browser_reference(directory, scene):
    """Capture a few actual Python-native physical poses and independent matrices."""
    pips = {scene['startPip'], scene['startPip'] + scene['sampleCount']//2, scene['endPip']}
    if scene['startPip'] + 64 <= scene['endPip']:
        pips.add(scene['startPip'] + 64)
    samples = []
    with MotionPackage(directory, cache_size=0) as package:
        profile = package.profile
        for descriptor in package.manifest['clips']:
            selected = sorted(p for p in pips if descriptor['start_pip'] <= p <
                              descriptor['start_pip'] + descriptor['sample_count'])
            if not selected:
                continue
            player = package.load(descriptor['id']).player()
            for pip in selected:
                physical = player.sample(pip)
                samples.append(dict(pip=pip, clipId=descriptor['id'], physicalValues=list(physical),
                                    jointWorldMatrices=_reference_world_matrices(profile, physical)))
        if len(samples) != len(pips):
            raise ScoreError('Browser reference could not cover all requested complete-action pips')
        return dict(format='dancerudiments.mesh-demo-browser-reference', schema_version=1,
            sceneId=scene['id'], expectedProfile=scene['expectedProfile'], sourceSha256=scene['sourceSha256'],
            manifestSha256=scene['manifestSha256'], sceneRigSha256=scene['sceneRigSha256'],
            matrixLayout='row-major', coordinateSystem='source rig space before presentation group transform',
            sampler='Python native SampledRecording with existing RigMotion physical channel decoding',
            evaluator='Independent offline NumPy rest-matrix and local-TRS products; unit quaternion rotations',
            jointNames=[b['name'] for b in profile.source['skeleton']],
            tolerances=dict(physicalAbsolute=1e-8, worldMatrixAbsolute=1e-7),
            samples=sorted(samples, key=lambda sample:sample['pip']))


def build_assets(document, output_dir, *, cache_root, download=False, license_root=ROOT):
    """Publish a fresh directory only after both complete native checks succeed."""
    from dancerudiments import SampledRecording  # noqa: F401 — fail before downloads if runtime is absent

    document = validate_sources(document)
    output_dir, cache_root = Path(output_dir), Path(cache_root)
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError('Use a fresh mesh demo output directory; existing output is not overwritten')
    licence = (Path(license_root) / document['license']['local_text']).read_bytes()
    if _sha(licence) != document['license']['local_text_sha256']:
        raise ScoreError('Local source licence differs from the pinned recipe')
    preflight(output_dir.parent)
    preflight(cache_root / 'raw')
    for scene in document['scenes']:
        _ensure_file(cache_root, scene['source'], download=download)
    prepared = [(scene, _prepare_clip(document, scene, cache_root)) for scene in document['scenes']]
    with tempfile.TemporaryDirectory(prefix='.mesh-demo-build-', dir=output_dir.parent) as temporary:
        stage = Path(temporary) / 'assets'
        stage.mkdir()
        entries, package_paths = [], []
        for scene, clip in prepared:
            relative = PurePosixPath('motions') / scene['id']
            directory = stage / relative
            rig_data = _bytes(scene_rig(clip.profile, scene_id=scene['id'], character_kind=scene['characterKind']))
            if _sha(rig_data) != scene['sceneRigSha256']:
                raise ScoreError('Scene bind rig differs from the independently pinned rig hash')
            builder = MotionPackageBuilder(directory, package_id=scene['packageId'], version=scene['version'],
                title=scene['title'], profile=clip.profile, license=document['license'],
                provenance=dict(source_id=document['source_id'], source=scene['source'],
                    source_plan_sha256=_sha(_bytes(document)), scene_id=scene['id'],
                    conversion=document['conversion'], timing_kind='time-only', music_timing_verified=False))
            for chunk in compile_bvh(clip, name=f"mesh_{scene['id']}_{scene['source']['id']}"):
                builder.add_bvh_chunk(chunk)
            manifest = builder.finalize()
            (directory / 'scene-rig.json').write_bytes(rig_data)
            _write_notices(directory, document, scene, licence)
            # This is a finished public build, not a resumable private workspace.
            (directory / '.motion-package-build.json').unlink(missing_ok=True)
            package_paths.append(directory)
            clips = manifest['clips']
            entries.append(dict(id=scene['id'], title=scene['title'], description=scene['description'],
                characterKind=scene['characterKind'], packageId=scene['packageId'],
                expectedProfile=scene['expectedProfile'], manifestPath=str(relative / 'manifest.json'),
                manifestSha256=_sha((directory / 'manifest.json').read_bytes()),
                rigPath=str(relative / 'scene-rig.json'), sceneRigSha256=scene['sceneRigSha256'],
                clipIds=[c['id'] for c in clips], originalClipId=clip.source_sha256,
                startPip=clips[0]['start_pip'], endPip=clips[-1]['start_pip'] + clips[-1]['sample_count'] - 1,
                sampleCount=sum(c['sample_count'] for c in clips), secondsPerPip=1/64,
                sourceDurationSeconds=clip.duration_seconds, sourceFrameCount=clip.frame_count,
                sourceFps=clip.source_fps, sourceTitle=scene['source']['title'], sourceUrl=scene['source']['source_url'],
                sourceSha256=clip.source_sha256, attribution=document['license']['attribution'],
                timingKind='time-only', timingLabel=TIMING_LABEL, musicTimingVerified=False,
                calibrationFrameCount=scene['source']['calibration_frame_count'], trimmedSourceFrames=0,
                compressedClipBytes=sum(c['byte_length'] for c in clips),
                noticePath=str(relative / 'THIRD_PARTY_NOTICES.md'), licensePath=str(relative / 'LICENSE.txt')))
        verification = verify_packages(package_paths)
        if not verification['passed'] or verification['complete_original_actions'] != len(entries):
            raise ScoreError('Native demo verification failed: ' + canonical_json(verification['failures']))
        for entry, directory in zip(entries, package_paths):
            reference_data = _bytes(browser_reference(directory, entry))
            (directory / 'browser-reference.json').write_bytes(reference_data)
            entry['browserReferencePath'] = f"motions/{entry['id']}/browser-reference.json"
            entry['browserReferenceSha256'] = _sha(reference_data)
        for item in verification['packages']:
            item['path'] = Path(item['path']).relative_to(stage.resolve()).as_posix()
        catalogue = dict(format='dancerudiments.mesh-demo-catalogue', schema_version=1,
            sourcePlanSha256=_sha(_bytes(document)), scenes=entries, timingLabel=TIMING_LABEL)
        (stage / 'catalogue.json').write_bytes(_bytes(catalogue))
        (stage / 'verification.json').write_bytes(_bytes(verification))
        stage.rename(output_dir)
    return catalogue


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, default=DEFAULT_SOURCES)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'generated/mesh-demo-assets')
    parser.add_argument('--cache-root', type=Path, default=ROOT / '.cache/motion-sources/cmu-dance')
    parser.add_argument('--download', action='store_true', help='Explicitly fetch only missing pinned BVH source bytes')
    args = parser.parse_args(argv)
    catalogue = build_assets(load_sources(args.sources), args.output_dir,
                             cache_root=args.cache_root, download=args.download)
    print(json.dumps(dict(output=str(args.output_dir), scenes=[dict(id=s['id'], clips=len(s['clipIds']),
        source_seconds=s['sourceDurationSeconds'], samples=s['sampleCount'],
        compressed_bytes=s['compressedClipBytes']) for s in catalogue['scenes']]), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

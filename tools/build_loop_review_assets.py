"""Prepare one explicit portable source Action for the existing Kandi renderer.

All transforms are validated by the canonical offline world evaluator. This
builder records a supplied calibration pose and exact bone map; it does not
infer a rig, fetch media or alter the public two-source release gallery.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

from dancerudiments_authoring._validation import ScoreError, canonical_json
from dancerudiments_authoring.motion_clock import BeatMap
from dancerudiments_authoring.motion_import import (
    RigCapture,
    compile_capture,
    load_capture,
)
from dancerudiments_authoring.motion_packages import MotionPackageBuilder
from dancerudiments_authoring.recording import RecordingClock
from dancerudiments_authoring.world_motion import (
    evaluate_world_motion,
    source_valid_segments,
)

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def descriptor(path):
    return {'sha256': digest(path), 'byte_length': Path(path).stat().st_size}


def write_json(path, document):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(canonical_json(document) + '\n', encoding='ascii')


def default_retarget_map():
    # Read the actual renderer's canonical map, rather than maintaining a
    # second Python copy of anatomical names.
    result = subprocess.run(['node', '--input-type=module', '-e',
        ("import {KANDI_RETARGET_MAP} from './tools/mesh_demo_assets/kandi-boom.js';"
         "process.stdout.write(JSON.stringify(KANDI_RETARGET_MAP));")],
        cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def portable_scene_rig(capture, calibration, *, calibration_seconds, retarget_map,
                       target_keys, source_sha256, calibration_file_sha256,
                       scene_id='review-action'):
    import numpy as np

    # Using a one-frame capture validates the exact carrier semantics without
    # allocating a whole-Action matrix cache solely to prepare static geometry.
    probe = RigCapture(capture.profile, (capture.frame_times_seconds[0],), (capture.frames[0],))
    world = evaluate_world_motion(probe)
    if calibration.profile.fingerprint != capture.profile.fingerprint:
        raise ScoreError('Calibration capture must have the exact source profile')
    matches = [i for i, time in enumerate(calibration.frame_times_seconds)
               if math.isclose(time, calibration_seconds, rel_tol=0, abs_tol=1e-9)]
    if len(matches) != 1:
        raise ScoreError('Calibration seconds must identify one actual captured frame')
    row = calibration.frames[matches[0]]
    evaluate_world_motion(RigCapture(calibration.profile, (calibration_seconds,), (row,)))
    if (not isinstance(retarget_map, dict) or set(retarget_map) != set(target_keys)
            or any(not isinstance(name, str) or name not in world.bone_names
                   for name in retarget_map.values())
            or len(set(retarget_map.values())) != len(retarget_map)):
        raise ScoreError('Supply a complete one-to-one Kandi target-to-source bone map; names are never guessed')
    pending = list(range(len(world.bone_names)))
    order = []
    while pending:
        ready = [i for i in pending if world.parents[i] < 0 or world.parents[i] in order]
        if not ready:
            raise ScoreError('Source hierarchy is cyclic')
        order.extend(ready)
        pending = [i for i in pending if i not in ready]
    remap = {old: new for new, old in enumerate(order)}
    skeleton = {item['name']: item for item in capture.profile.source['skeleton']}
    joints = []
    for old in order:
        name = world.bone_names[old]
        parent = world.parents[old]
        rest = world.rest_matrices[old]
        local = rest if parent < 0 else np.linalg.inv(world.rest_matrices[parent]) @ rest
        indices = {}
        for kind, width in [('location', 3), ('rotation_quaternion', 4), ('scale', 3)]:
            found = {c.array_index: index for index, c in enumerate(capture.profile.channels)
                     if c.bone == name and c.data_path == kind}
            indices[kind] = [found[i] for i in range(width)] if found else None
        joints.append({'name': name, 'parentIndex': remap.get(parent, -1),
            'offset': local[:3, 3].tolist(), 'localRestMatrix': local.reshape(-1).tolist(),
            'restMatrix': rest.reshape(-1).tolist(), 'length': skeleton[name]['length'], 'endSites': [],
            'positionChannelIndices': indices['location'], 'rotationChannelIndices': indices['rotation_quaternion'],
            'scaleChannelIndices': indices['scale']})
    points = world.rest_matrices[:, :3, 3]
    minimum, maximum = np.min(points, axis=0), np.max(points, axis=0)
    if maximum[2] - minimum[2] <= 0:
        raise ScoreError('A supported Kandi source needs a nonzero Blender Z-up body extent')
    identity = {'type_uri': capture.profile.type_uri, 'fingerprint': capture.profile.fingerprint,
                    'dimensions': list(capture.profile.dimensions)}
    calibration_record = {'profile_sha256': capture.profile.fingerprint, 'values': list(row),
        'source_capture_sha256': calibration_file_sha256, 'source_time_seconds': calibration_seconds}
    rig = {'format': 'dancerudiments.mesh-demo-rig', 'schema_version': 1, 'sceneId': scene_id,
        'characterKind': 'kandi-boom', 'expectedProfile': identity, 'matrixLayout': 'row-major',
        'quaternionOrder': 'wxyz', 'coordinateSystem': {'up': '+Z', 'handedness': 'right',
            'unitPolicy': 'validated evaluated portable Blender carrier; source units retained'},
        'rootOffsetPolicy': 'saved-rest-matrix-times-carrier-TRS',
        'channels': [c.to_dict() for c in capture.profile.channels], 'joints': joints,
        'sourceSkeleton': [skeleton[world.bone_names[i]] for i in order],
        'omittedNeutralGroups': capture.profile.source['omitted_neutral_groups'],
        'restBounds': {'minimum': minimum.tolist(), 'maximum': maximum.tolist(), 'size': (maximum-minimum).tolist()},
        'retargetMap': retarget_map, 'sourceHeightAxis': 2,
        'sourceToTargetQuaternion': [math.sqrt(.5), -math.sqrt(.5), 0., 0.],
        'calibrationPose': calibration_record, 'originalSourceSha256': source_sha256}
    return rig


def prepare_review_assets(capture_path, output, *, start_seconds, end_seconds,
                          original_source_sha256, calibration_capture_path,
                          calibration_seconds, license, retarget_map=None,
                          title='Imported Action loop review'):
    """Write a new local scene; return its exact target/calibration identity."""
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    capture, calibration = load_capture(capture_path), load_capture(calibration_capture_path)
    coverage = next(((a, b) for a, b in source_valid_segments(capture)
                     if a <= start_seconds < end_seconds <= b), None)
    if coverage is None:
        raise ScoreError('The selected interval must lie within one observed source segment')
    mapping = default_retarget_map()
    rig = portable_scene_rig(capture, calibration, calibration_seconds=calibration_seconds,
        retarget_map=retarget_map if retarget_map is not None else mapping, target_keys=mapping,
        source_sha256=original_source_sha256, calibration_file_sha256=digest(calibration_capture_path))
    lo, hi = (Fraction(str(x)) for x in coverage)
    first = math.ceil(lo * 64)
    last = math.floor(hi * 64)
    if last <= first:
        raise ScoreError('Source segment has fewer than two native source-time samples')
    # Only the selected continuous source segment enters the preview package.
    # A complete source Action with gaps is never silently interpolated.
    source_map = BeatMap.from_bpm(60, beat_zero_seconds=0,
        source='Source-time coordinate: one second per beat; musical timing unknown')
    clock = RecordingClock(60, 'Source-time coordinate only; no musical BPM estimate',
                           'estimated', 0, 'unverified', first)
    motion = compile_capture(capture, name='source_action', source_beat_map=source_map,
        clock=clock, sample_count=last-first+1)
    provenance = dict(motion.recording.provenance, original_source_sha256=original_source_sha256,
        source_capture_file_sha256=digest(capture_path), timing_kind='time-only', music_timing_verified=False)
    motion = replace(motion, recording=replace(motion.recording, provenance_json=canonical_json(provenance)))
    output.mkdir(parents=True)
    base = output / 'motions' / 'review-action'
    builder = MotionPackageBuilder(base, package_id='local_review_action', version='1.0.0',
        title=title, profile=capture.profile, license=license,
        provenance={'original_source_sha256': original_source_sha256,
                        'source_capture_sha256': digest(capture_path), 'source': capture.provenance})
    clip = builder.add(motion, metadata={'timing_kind': 'time-only', 'original_clip_id': original_source_sha256,
        'chunk_index': 0, 'chunk_count': 1, 'source_seconds_range': list(coverage)})
    builder.finalize()
    notices = json.dumps(license, indent=2, ensure_ascii=True)
    (base/'LICENSE.txt').write_text(notices+'\n', encoding='ascii')
    (base/'THIRD_PARTY_NOTICES.md').write_text(notices+'\n', encoding='ascii')
    (base/'README.md').write_text(title+'\n\nLocal source-time review only.\n\nhttps://kieransimkin.co.uk/my-songs/\n', encoding='utf-8')
    write_json(base/'SOURCES.json', provenance)
    write_json(base/'scene-rig.json', rig)
    source = ROOT/'harness/kandi-boom'
    target_rig_bytes = (source/'source-rig.json').read_bytes()
    target_rig = json.loads(target_rig_bytes)
    audit = json.loads((source/'rig-audit.json').read_text('utf-8'))
    if (target_rig['fingerprint_sha256'] != audit['deep_validation']['source_rig_fingerprint_sha256']
            or target_rig['fbx_asset_sha256'] != audit['assets']['kandi-boom.fbx']['sha256']):
        raise ScoreError('Kandi target audit and source rig disagree')
    target_dir = output/'characters/kandi-boom'
    target_dir.mkdir(parents=True)
    assets = {}
    for kind, name in [('fbx','kandi-boom.fbx'),('albedo','albedo.png'),('normal','normal.png'),
                       ('roughness','roughness.png'),('metallic','metallic.png')]:
        item = source/'assets'/name
        desc = descriptor(item)
        if desc != {'sha256': audit['assets'][name]['sha256'], 'byte_length': audit['assets'][name]['bytes']}:
            raise ScoreError('Kandi asset changed: '+name)
        shutil.copyfile(item, target_dir/name)
        assets[kind] = dict(path=f'characters/kandi-boom/{name}', **desc)
    (target_dir/'source-rig.json').write_bytes(target_rig_bytes)
    assets['rig'] = dict(path='characters/kandi-boom/source-rig.json', **descriptor(target_dir/'source-rig.json'))
    calibration_evidence = {'source_rig_sha256': digest(base/'scene-rig.json'),
        'retarget_implementation_sha256': digest(ROOT/'tools/mesh_demo_assets/kandi-boom.js'),
        'target_rig_sha256': assets['rig']['sha256']}
    calibration_sha = hashlib.sha256(canonical_json(calibration_evidence).encode('ascii')).hexdigest()
    target = {'id': 'kandi-boom', 'asset_sha256': assets['fbx']['sha256'],
                  'rig_sha256': assets['rig']['sha256'], 'calibration_sha256': calibration_sha}
    scene = {'id': 'review-action', 'title': title, 'description': 'Review an explicitly imported Action on Kandi Boom.',
        'sourceTitle': title, 'sourceUrl': 'https://kieransimkin.co.uk/danceflow/',
        'attribution': license.get('attribution', 'See the source notices'), 'characterKind': 'kandi-boom',
        'packageId': 'local_review_action', 'expectedProfile': rig['expectedProfile'],
        'manifestPath': 'motions/review-action/manifest.json', 'manifestSha256': digest(base/'manifest.json'),
        'rigPath': 'motions/review-action/scene-rig.json', 'sceneRigSha256': digest(base/'scene-rig.json'),
        'sourceSha256': original_source_sha256, 'originalClipId': original_source_sha256,
        'sourceDurationSeconds': float(hi), 'sourceFps': 1/(capture.frame_times_seconds[1]-capture.frame_times_seconds[0]),
        'sourceFrameCount': len(capture.frames), 'startPip': first, 'endPip': last, 'sampleCount': last-first+1,
        'clipIds': ['source_action'], 'compressedClipBytes': clip['byte_length'], 'calibrationFrameCount': 0,
        'calibrationLabel': 'Explicit saved source calibration pose; visual fit awaits review',
        'timingKind': 'time-only', 'musicTimingVerified': False, 'secondsPerPip': 1/64,
        'noticePath': 'motions/review-action/THIRD_PARTY_NOTICES.md', 'licensePath': 'motions/review-action/LICENSE.txt'}
    character = {'id': 'kandi-boom', 'name': 'Kandi Boom', 'series': 'Bass Ben & Friends',
        'typeUri': target_rig['type_uri'], 'rigFingerprint': target_rig['fingerprint_sha256'],
        'fbxAssetSha256': target_rig['fbx_asset_sha256'], 'assets': assets,
        'sourceInfluenceStats': {'runtimeInfluenceLimit': 4,
            'maxInfluencesPerVertex': audit['deep_validation']['skin']['max_influences_per_vertex'],
            'verticesWithOverFourInfluences': audit['deep_validation']['skin']['vertices_with_over_four_influences'],
            'maxDiscardedWeightAtFour': audit['deep_validation']['skin']['max_discarded_weight_if_four_influences']}}
    config = {'reviewWorkspace': True, 'scenes': [scene], 'character': character, 'reviewTarget': target,
                  'reviewCalibrationEvidence': calibration_evidence}
    write_json(output/'config.json', config)
    inventory = {path.relative_to(output).as_posix(): descriptor(path)
                 for path in sorted(output.rglob('*')) if path.is_file() and path.name != 'config.json'}
    write_json(output/'assets.json', {'format': 'dancerudiments.loop-review-assets.v1', 'files': inventory})
    return {'scene_id': scene['id'], 'target': target, 'source_seconds_range': list(coverage),
                'config': config, 'assets': inventory}

#!/usr/bin/env python3
"""Build a deterministic, explicitly unapproved local Kandi review fixture.

Uses the checked-in audited target rest layout, generated motion and WAV bytes,
and actual StemLab alignment APIs. No motion, model or audio is downloaded.
"""
from __future__ import annotations

import argparse
import json
import math
import wave
from pathlib import Path

from build_loop_review_assets import (
    ROOT,
    default_retarget_map,
    descriptor,
    digest,
    write_json,
)
from dancerudiments_authoring._validation import canonical_json
from dancerudiments_authoring.motion_import import RigCapture, write_capture
from dancerudiments_authoring.rigs import RigChannel, RigProfile
from dancerudiments_authoring.world_motion import evaluate_world_motion
from review_motion_loop import preflight, prepare_workspace

LICENSE = {
    'id': 'MIT',
    'url': 'https://github.com/kieransimkin/DanceRudiments/blob/main/LICENSE',
    'attribution': 'Copyright (c) 2026 Kieran Simkin. Generated regression movement; '
                   'rest layout derives from the checked-in Kandi Boom rig. '
                   'No human musical, seam, foot-contact or skin approval.',
}
MOTION_DURATION = 4.
AUDIO_DURATION = 6.
ANNOTATIONS = (.1, .23333333333333334, .43333333333333335, .6333333333333333,
               .9, 1.0666666666666667, 1.3, 1.6333333333333333, 1.8333333333333333)


def synthetic_capture():
    """Create a complete portable Z-up carrier with explicit source bone names.

    Bind matrices are column-major in the audited target document. The fixture
    explicitly converts its centimetre Y-up layout to metre Z-up coordinates
    and removes floating-point scale roundoff from each saved rest rotation.
    Forward kinematics is supplied only by the canonical world evaluator.
    """
    import numpy as np

    mapping = default_retarget_map()
    rig_path = ROOT / 'harness/kandi-boom/source-rig.json'
    target = json.loads(rig_path.read_text(encoding='utf-8'))
    bones = {bone['name']: bone for bone in target['bones']}
    conversion = np.array([[1., 0., 0., 0.], [0., 0., -1., 0.],
                           [0., 1., 0., 0.], [0., 0., 0., 1.]])
    matrices = {}
    for name in mapping:
        matrix = conversion @ np.array(bones[name]['world_bind_matrix']).reshape(4, 4).T
        matrix[:3, 3] *= .01
        left, _, right = np.linalg.svd(matrix[:3, :3])
        rotation = left @ right
        if np.linalg.det(rotation) <= 0:
            raise ValueError('The audited target rest layout has an improper rotation')
        matrix[:3, :3] = rotation
        matrices[name] = matrix
    skeleton, channels, omitted = [], [], []
    for target_name, source_name in mapping.items():
        parent = bones[target_name]['parent_name']
        children = [name for name in mapping if bones[name]['parent_name'] == target_name]
        length = min((float(np.linalg.norm(matrices[name][:3, 3] - matrices[target_name][:3, 3]))
                      for name in children), default=.05)
        skeleton.append({'name': source_name, 'parent': mapping.get(parent),
                         'rest_matrix': matrices[target_name].reshape(-1).tolist(),
                         'length': max(length, .001), 'use_deform': True})
        for axis, neutral in enumerate((1., 0., 0., 0.)):
            number = len(channels) + 1
            channels.append(RigChannel(number, f'channel_{number}', source_name,
                'rotation_quaternion', axis, 'unitless', -1., 1., neutral,
                interpolation='quaternion', rotation_mode='QUATERNION'))
        omitted.extend([{'bone': source_name, 'data_path': 'location', 'values': [0., 0., 0.]},
                        {'bone': source_name, 'data_path': 'scale', 'values': [1., 1., 1.]}])
    source = {'adapter': 'dancerudiments.skeletal-source-v1', 'skeleton': skeleton,
              'object_motion_root': mapping['Hips'], 'scene_unit_scale_length': 1.,
              'omitted_neutral_groups': omitted,
              'carrier_inheritance': 'FULL; local location; inherit rotation',
              'coordinate_system': 'Blender right-handed +Z up, +Y forward',
              'fixture_target_layout_sha256': digest(rig_path),
              'fixture_transform': 'Y-up centimetres to Z-up metres; proper rigid rest rotation'}
    profile = RigProfile('syn://type/danceflow/motion/skeletal/source/synthetic/loop-review',
                         'Synthetic Kandi review carrier', tuple(channels),
                         source_json=canonical_json(source))
    times = tuple(frame / 30 for frame in range(int(MOTION_DURATION * 30) + 1))
    amplitudes = {'LeftArm': .10, 'RightArm': -.10, 'LeftForeArm': .06,
                  'RightForeArm': -.06, 'Spine01': .025}
    rows = []
    for seconds in times:
        poses = {}
        for target_name, source_name in mapping.items():
            angle = amplitudes.get(target_name, 0.) * math.sin(math.tau * seconds / 2)
            poses[source_name] = (math.cos(angle / 2), math.sin(angle / 2), 0., 0.)
        rows.append(tuple(poses[channel.bone][channel.array_index] for channel in channels))
    capture = RigCapture(profile, times, tuple(rows), canonical_json({
        'source': 'deterministic synthetic authoring regression',
        'generator': 'tools/build_loop_review_test_fixture.py',
        'target_layout_sha256': digest(rig_path), 'human_approved': False,
        'annotations': 'Controlled test landmarks, not detector or human performance evidence'}))
    evaluate_world_motion(capture)
    return capture


def synthetic_audio(path, event_times):
    """Write short original click tones at the declared fixture annotations."""
    import numpy as np

    rate = 16000
    samples = np.zeros(round(AUDIO_DURATION * rate), dtype=np.float64)
    offsets = np.arange(round(.035 * rate)) / rate
    click = 12000 * np.sin(math.tau * 880 * offsets) * np.exp(-offsets * 140)
    for seconds in event_times:
        start = round(seconds * rate)
        samples[start:start + len(click)] += click
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(np.rint(samples).astype('<i2').tobytes())


def build_fixture(output):
    """Prepare a new full workspace through the production authoring path."""
    from stemlab.analysis.motion_alignment import (
        align_motion_audio,
        create_alignment_revision,
        make_event_evidence,
        write_document,
    )

    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    preflight(output.parent)
    output.mkdir()
    capture_path, audio_path = output / 'source.capture.json', output / 'synthetic-master.wav'
    write_capture(capture_path, synthetic_capture())
    annotations = [time + cycle * 2 for cycle in range(2) for time in ANNOTATIONS]
    audio_annotations = [time + .25 for time in annotations]
    synthetic_audio(audio_path, audio_annotations)

    def evidence(kind, path, times, duration):
        return make_event_evidence(kind=kind, source_sha256=digest(path),
            clock_id=f'synthetic_{kind}_source_seconds', seconds_range=[0., duration],
            streams=[{'id': 'controlled_test_annotations', 'family': 'automated_test_annotation',
                      'event_type': 'human_annotation',
                      'events': [{'seconds': time, 'strength': 1.} for time in times]}])

    motion = evidence('motion', capture_path, annotations, MOTION_DURATION)
    audio = evidence('audio', audio_path, audio_annotations, AUDIO_DURATION)
    clock = {'format': 'stemlab.motion-clock-map.v1', 'schema_version': 1,
             'relationship': 'creative_retiming',
             'motion_source_sha256': digest(capture_path), 'audio_source_sha256': digest(audio_path),
             'motion_clock_id': 'synthetic_motion_source_seconds',
             'audio_clock_id': 'synthetic_audio_source_seconds',
             'motion_origin_seconds': 0., 'audio_origin_seconds': 0., 'seconds_scale': 1.}
    report = align_motion_audio(motion, audio, clock, motion_source=capture_path,
        audio_source=audio_path, variable_tempo=False, max_offset_seconds=.5, rate_multipliers=[1.])
    if not report['source_bytes_verified'] or not report['candidates']:
        raise ValueError('Synthetic fixture produced no source-verified alignment proposal')
    report_path = output / 'alignment.json'
    write_document(report_path, report)
    revision = create_alignment_revision(report, report_sha256=digest(report_path),
        candidate_id=report['candidates'][0]['candidate_id'], reviewer='Automated synthetic fixture generator',
        manual_anchors=[{'motion_seconds': 0., 'audio_seconds': .25},
                        {'motion_seconds': MOTION_DURATION, 'audio_seconds': MOTION_DURATION + .25}])
    write_document(output / 'timing-test-revision.json', revision)
    write_json(output / 'fixture-evidence.json', {
        'format': 'dancerudiments.loop-review-synthetic-evidence.v1', 'schema_version': 1,
        'human_approved': False, 'motion': motion, 'audio': audio, 'clock': clock,
        'annotation_scope': 'Generated test correspondences; never human listening or visual approval',
        'capture': descriptor(capture_path), 'audio_file': descriptor(audio_path)})
    workspace = prepare_workspace(capture=capture_path, audio=audio_path, alignment_report=report_path,
        output=output / 'workspace', start_seconds=0., end_seconds=2., beats=4,
        original_source_sha256=digest(capture_path), calibration_capture=capture_path,
        calibration_seconds=0., license=LICENSE, repair_options={'translation_scale': 1.},
        title='Synthetic loop review regression — no human approval', automated_test=True)
    result = {'format': 'dancerudiments.loop-review-test-fixture.v1', 'schema_version': 1,
              'human_approved': False, **workspace}
    write_json(output / 'fixture.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, help='A new ignored fixture directory')
    args = parser.parse_args(argv)
    print(json.dumps(build_fixture(args.output_dir), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

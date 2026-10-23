"""Source-first offline loop analysis; only synthetic poses, never third-party assets."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from dancerudiments_authoring.bvh_import import load_bvh
from dancerudiments_authoring.motion import load_rig_motion
from dancerudiments_authoring.motion_import import RigCapture, write_capture
from dancerudiments_authoring.rigs import RigChannel, RigProfile
from dancerudiments_authoring.source_loop_analysis import (
    analyse_source_capture, source_capture_from_bvh,
)


def fixture(*, static=False, drift=0.0):
    """120-BPM foot/arm impulses over a repeated two-second synthetic phrase."""
    spec = (
        ('root_x', 'root', 'location', 0, -100, 100, 'linear', 'float'),
        ('hand_x', 'hand', 'location', 0, -2, 2, 'linear', 'float'),
        ('knee_x', 'knee', 'rotation_euler', 0, -4, 4, 'linear', 'float'),
        ('qw', 'spine', 'rotation_quaternion', 0, -1, 1, 'quaternion', 'float'),
        ('qx', 'spine', 'rotation_quaternion', 1, -1, 1, 'quaternion', 'float'),
        ('qy', 'spine', 'rotation_quaternion', 2, -1, 1, 'quaternion', 'float'),
        ('qz', 'spine', 'rotation_quaternion', 3, -1, 1, 'quaternion', 'float'),
        ('ik', 'hand', '["IK_parent"]', -1, 0, 2, 'step', 'integer'),
    )
    channels = tuple(RigChannel(i+1, name, bone, path, axis, 'units', lower, upper,
                                1. if name == 'qw' else 0., interpolation=interpolation,
                                value_type=value_type,
                                rotation_mode='QUATERNION' if interpolation == 'quaternion' else '')
                     for i, (name, bone, path, axis, lower, upper, interpolation, value_type)
                     in enumerate(spec))
    profile = RigProfile('syn://type/danceflow/motion/rigify/custom/synthetic',
                         'synthetic', channels, source_json='{"synthetic":true}')
    frames, times = [], []
    for i in range(16*60+1):
        t = i/60
        primary = (0 if static else .85 * math.exp(-((t % .5 - .12) / .065)**2)
                   + .12 * math.sin(math.tau * t / 2))
        secondary = 0 if static else .10 * math.sin(math.tau * t / 2 + .4)
        angle = 0 if static else .15 * math.sin(math.tau*t/2)
        frames.append((drift*t, primary, secondary, math.cos(angle/2), 0., 0.,
                       math.sin(angle/2), 0))
        times.append(t)
    return RigCapture(profile, tuple(times), tuple(frames), '{"origin":"synthetic"}')


def fake_stemlab(*, score=.9, pose_only=False, missing_grid=False,
                 pose_mismatch=.01, root_drift=0.):
    def analyze(path, *, min_bpm, max_bpm):
        data = json.loads(Path(path).read_text())
        assert not Path(path).parent.joinpath('previews').exists(), 'Conversion ran before analysis'
        return dict(format='stemlab.rig-motion-analysis', schema_version=1,
            source_kind='capture', source_file_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            type_uri=data['type_uri'], profile_sha256=data['profile_sha256'],
            recommended_tempo=dict(bpm=120., beat_zero_seconds=.0, score=.95),
            estimated_beat_map=None if missing_grid else dict(format='dancerudiments.beat-map',
                schema_version=1, pips_per_beat=64, interpolation='linear',
                anchors=[dict(seconds=0, beat=0), dict(seconds=.5, beat=1)],
                bpm_status='estimated',
                phase_status='estimated', extrapolate=False,
                source='StemLab motion-only estimate: '+hashlib.sha256(Path(path).read_bytes()).hexdigest()),
            loop_candidates=[dict(start_seconds=2.0, end_seconds=4.0,
                                  beats=None if pose_only else 4,
                                  alignment='pose_recurrence_only' if pose_only else 'estimated_motion_beat_grid',
                                  requires_review=True, repaired=False,
                                  evidence='repeated_and_seam', score=score,
                                  pose_mismatch=pose_mismatch, velocity_mismatch=.02,
                                  root_drift_relative=root_drift)])

    def write(path, report, *, beat_map_path=None):
        Path(path).write_text(json.dumps(report))
    a, b, c = types.ModuleType('stemlab'), types.ModuleType('stemlab.analysis'), types.ModuleType('stemlab.analysis.rig_motion')
    c.analyze_rig_capture, c.write_rig_analysis = analyze, write
    return {'stemlab': a, 'stemlab.analysis': b, 'stemlab.analysis.rig_motion': c}


class SourceFirstLoopTests(unittest.TestCase):
    def test_capture_to_loop_compiles_after_stemlab_and_keeps_time_identity(self):
        original = fixture()
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules, fake_stemlab()):
            path = Path(directory) / 'analysis'
            report = analyse_source_capture(original, path, min_bpm=100, max_bpm=140,
                                           target_bpm=124, max_previews=2)
            self.assertEqual(report['preview_count'], 1)
            self.assertFalse(report['inferred_tempo_verified'])
            loop = report['previews'][0]
            self.assertEqual(loop['source_beats'], 4)
            self.assertEqual(loop['start_pip'], 0)
            self.assertEqual(loop['end_pip_exclusive'], 256)
            self.assertEqual(loop['source_start_seconds'], 2.0)
            self.assertEqual(loop['source_end_seconds'], 4.0)
            self.assertTrue(loop['requires_review'])
            self.assertFalse(loop['native_samples_verified'])
            compiled = load_rig_motion(path / loop['filename'])
            self.assertEqual(compiled.profile.fingerprint, original.profile.fingerprint)
            self.assertEqual(len(compiled.recording.samples), 256)
            self.assertEqual(compiled.recording.clock.bpm, 124)
            self.assertEqual(compiled.recording.clock.bpm_status, 'estimated')
            self.assertEqual(compiled.recording.provenance['source_time_range_seconds'][0], 2.0)
            self.assertEqual(compiled.recording.provenance['loop_policy'], 'non_looping')
            self.assertEqual(json.loads((path/'stemlab-analysis.json').read_text())['source_kind'], 'capture')
            with self.assertRaises(FileExistsError):
                analyse_source_capture(original, path)

    def test_no_implicit_tempo_for_pose_only_candidate(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules, fake_stemlab(pose_only=True)):
            report = analyse_source_capture(fixture(), Path(directory)/'analysis')
            self.assertEqual(report['preview_count'], 0)
            self.assertEqual(report['rejected_candidates'][0]['reason'], 'not_an_unverified_beat_grid_loop')
            self.assertEqual(list((Path(directory)/'analysis'/'previews').glob('*.json')), [])

    def test_missing_stemlab_beat_map_cannot_promote_loop_to_beat_grid(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
                sys.modules, fake_stemlab(missing_grid=True)):
            report = analyse_source_capture(fixture(), Path(directory)/'analysis')
            self.assertEqual(report['preview_count'], 0)
            self.assertEqual(report['rejected_candidates'][0]['reason'], 'missing_source_grid_evidence')
            self.assertFalse(list((Path(directory)/'analysis'/'previews').glob('*.json')))

    def test_invalid_pose_or_root_drift_is_never_compiled(self):
        for metric in ({'pose_mismatch': .85}, {'root_drift': .50}):
            with self.subTest(metric=metric), tempfile.TemporaryDirectory() as directory, mock.patch.dict(
                    sys.modules, fake_stemlab(**metric)):
                report = analyse_source_capture(fixture(), Path(directory)/'analysis')
                self.assertEqual(report['preview_count'], 0)
                self.assertEqual(report['rejected_candidates'][0]['reason'],
                                 'unsafe_or_missing_seam_evidence')
                self.assertFalse(list((Path(directory)/'analysis'/'previews').glob('*.json')))

    def test_invalid_bpm_or_previews_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules, fake_stemlab()):
            folder = Path(directory)/'output'
            for params in ({'target_bpm': 0}, {'min_bpm': 180, 'max_bpm': 100},
                           {'max_previews': 13}):
                with self.assertRaises(ValueError):
                    analyse_source_capture(fixture(), folder, **params)
                self.assertFalse(folder.exists())

    @unittest.skipUnless(importlib.util.find_spec('numpy') is not None,
                         'Original BVH conversion needs optional NumPy')
    def test_bvh_source_original_frames_survive_source_first_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bvh = root/'dance.bvh'
            rows = [' '.join(map(str, (math.sin(i/10), 0, 0, 0, 0, 0))) for i in range(161)]
            bvh.write_text('HIERARCHY\nROOT Hips\n{\n OFFSET 0 0 0\n'
                           ' CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation\n'
                           ' End Site\n {\n OFFSET 0 1 0\n }\n}\nMOTION\n'
                           'Frames: 161\nFrame Time: 0.025\n' + '\n'.join(rows) + '\n')
            original = load_bvh(bvh, source_id='synthetic')
            capture = source_capture_from_bvh(original, calibration_frames=1)
            self.assertEqual(len(capture.frames), original.frame_count-1)
            self.assertEqual(capture.frame_times_seconds[0], .025)
            self.assertEqual(capture.profile.fingerprint, original.profile.fingerprint)
            self.assertEqual(capture.provenance['source_file_sha256'], original.source_sha256)
            self.assertEqual(capture.provenance['calibration_frames_excluded_from_analysis'], 1)
            path = root/'source.capture.json'
            write_capture(path, capture)
            self.assertEqual(json.loads(path.read_text())['type_uri'], capture.profile.type_uri)

    def test_stemlab_real_synthetic_motion_when_available(self):
        try:
            from stemlab.analysis.rig_motion import analyze_rig_capture  # noqa: F401
        except ImportError as exc:
            if os.environ.get('DANCERUDIMENTS_REQUIRE_STEMLAB') == '1':
                self.fail(f'StemLab rig-motion integration is required in this CI job: {exc}')
            self.skipTest('Compatible StemLab is an optional offline dependency')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'loop-analysis'
            report = analyse_source_capture(fixture(), output, min_bpm=100, max_bpm=140)
            evidence = json.loads((output/'stemlab-analysis.json').read_text())
            self.assertTrue(evidence['bpm_candidates'])
            self.assertLess(abs(evidence['recommended_tempo']['bpm']-120), 5)
            self.assertTrue(evidence['loop_candidates'])
            self.assertGreater(report['preview_count'], 0, 'A known periodic fixture must produce compiled previews')
            self.assertEqual(report['source_capture_sha256'], evidence['source_file_sha256'])
            self.assertTrue(all(item['requires_review'] for item in report['previews']))


if __name__ == '__main__':
    unittest.main()

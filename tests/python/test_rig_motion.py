import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from dancerudiments_authoring._validation import ScoreError
from dancerudiments_authoring.motion import RigMotion, load_rig_motion, write_rig_motion
from dancerudiments_authoring.motion_clock import BeatMap
from dancerudiments_authoring.recording import Recording, RecordingClock
from dancerudiments_authoring.rigs import RigChannel, RigProfile, rig_type_uri


def fixture():
    profile = RigProfile(rig_type_uri('test', kind='custom'), 'test', (
        RigChannel(1, 'root_x', 'root', 'location', 0, 'metre', -2, 2, 0),
        RigChannel(2, 'ik_parent', 'hand_ik', '["IK_parent"]', -1, 'index', 0, 4, 0,
                   value_type='integer', interpolation='step'),
    ), source_json=json.dumps({'rest_basis': 'synthetic identity'}))
    recording = Recording('synthetic', profile.dimensions, ((-1, -1), (0, -0.5), (1, 1)),
                          RecordingClock(120, 'synthetic', start_pip=-1))
    return RigMotion(recording, profile)


class RigMotionTests(unittest.TestCase):
    def test_serialization_identity_and_aliases(self):
        motion = fixture()
        self.assertEqual(RigMotion.from_dict(motion.to_dict()), motion)
        data = motion.to_dict()
        data['type_uri'] = data['type_uri'].replace('syn://', 'synny://')
        data['profile']['type_uri'] = data['profile']['type_uri'].replace('syn://', 'synny://')
        self.assertEqual(RigMotion.from_dict(data).fingerprint, motion.fingerprint)
        self.assertEqual(len(motion.fingerprint), 64)

    def test_tampered_profile_and_wrong_columns_are_rejected(self):
        motion = fixture()
        original = motion.to_dict()
        for mutate in (
            lambda d: d['profile']['channels'][0].update(bone='other_root'),
            lambda d: d['profile']['source'].update(rest_basis='changed'),
            lambda d: d['recording'].update(dimensions=list(reversed(motion.profile.dimensions))),
            lambda d: d.update(type_uri='syn://type/other'),
            lambda d: d.update(schema_version=True),
            lambda d: d.update(extra='unknown'),
        ):
            data = copy.deepcopy(original)
            mutate(data)
            with self.assertRaises(ScoreError):
                RigMotion.from_dict(data)
        altered = motion.profile.to_dict()
        altered['source']['rest_basis'] = 'different skeleton'
        with self.assertRaises(ScoreError):
            motion.require_profile(RigProfile.from_dict(altered))
        motion.require_profile(motion.profile)

    def test_invalid_discrete_samples_rejected_even_inside_normalized_bounds(self):
        data = fixture().to_dict()
        data['recording']['samples'][0][1] = -0.9
        with self.assertRaises(ScoreError):
            RigMotion.from_dict(data)

    def test_quaternion_cannot_be_zero_or_nonunit_in_loaded_motion(self):
        channels = tuple(RigChannel(i + 1, 'q' + 'wxyz'[i], 'root', 'rotation_quaternion', i,
                                    'unitless', -1, 1, 1 if i == 0 else 0,
                                    interpolation='quaternion', rotation_mode='QUATERNION') for i in range(4))
        profile = RigProfile(rig_type_uri('quaternion_test', kind='custom'), 'quaternion_test', channels)
        for values in ((0, 0, 0, 0), (1, 1, 0, 0)):
            recording = Recording('invalid_rotation', profile.dimensions, (values,), RecordingClock(120, 'test'))
            with self.assertRaises(ScoreError):
                RigMotion(recording, profile)

    def test_atomic_io_preserves_existing_motion_and_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'motion.json'
            write_rig_motion(path, fixture())
            before = path.read_bytes()
            self.assertEqual(load_rig_motion(path), fixture())
            with self.assertRaises(FileExistsError):
                write_rig_motion(path, fixture())
            self.assertEqual(path.read_bytes(), before)
            path.write_text('{"format": 1, "format": 2}', encoding='utf-8')
            with self.assertRaises(ScoreError):
                load_rig_motion(path)

    def test_real_native_sampling_seek_and_variable_target_tempo(self):
        try:
            import dancerudiments
        except ImportError:
            if os.environ.get('DANCERUDIMENTS_REQUIRE_NATIVE') == '1':
                raise
            self.skipTest('Native extension is required for playback verification')
        motion = fixture()
        player = motion.player()
        self.assertIsInstance(motion.to_native(), dancerudiments.SampledRecording)
        self.assertEqual(player.start_pip, -1)
        self.assertEqual(player.sample_count, 3)
        self.assertEqual(player.sample(-1), (-2, 0))
        self.assertEqual(player.by_channel(0), {1: 0, 2: 1})
        self.assertEqual(player.sample(1), (2, 4))
        self.assertEqual(player.sample(0), (0, 1))  # backwards seek has no hidden phase
        mapping = BeatMap(((-1, -1), (0, 0), (1, 2)), 'synthetic variable target tempo')
        self.assertEqual(player.sample_time('1/128', mapping), (2, 4))
        self.assertEqual(player.sample_time('-1/128', mapping), (-2, 0))
        for pip in (-2, 2):
            with self.assertRaises(IndexError):
                player.sample(pip)
        for pip in (True, 0.5):
            with self.assertRaises(ScoreError):
                player.sample(pip)


if __name__ == '__main__':
    unittest.main()

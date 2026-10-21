"""Verifier metadata contracts; native sampling itself has separate real gates."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from verify_motion_package import _verify_clip

from dancerudiments_authoring._validation import ScoreError, canonical_json
from dancerudiments_authoring.motion import RigMotion
from dancerudiments_authoring.motion_packages import MotionPackage, MotionPackageBuilder
from dancerudiments_authoring.recording import Recording, RecordingClock
from dancerudiments_authoring.rigs import RigChannel, RigProfile, rig_type_uri


class MetadataOnlyNative:
    def __init__(self, recording):
        self.recording = recording

    def sample(self, pip):
        index = pip - self.recording.clock.start_pip
        if not 0 <= index < len(self.recording.samples):
            raise IndexError(pip)
        return self.recording.samples[index]


class MotionPackageVerifierMetadataTests(unittest.TestCase):
    def verify(self, *, recording_metadata=None, package_metadata=None):
        profile = RigProfile(rig_type_uri('verifier', kind='custom'), 'verifier', (
            RigChannel(1, 'root_x', 'root', 'location', 0, 'unitless', -1, 1, 0),))
        recording = Recording('synthetic', profile.dimensions, ((-1.,), (0.,), (1.,)),
            RecordingClock(60, 'synthetic regression'), canonical_json(recording_metadata or {}))
        motion = RigMotion(recording, profile)
        with tempfile.TemporaryDirectory() as directory:
            builder = MotionPackageBuilder(directory, package_id='synthetic', version='1.0.0',
                title='Verifier metadata regression', profile=profile,
                license={'id': 'CC0-1.0'}, provenance={'synthetic': True})
            builder.add(motion, metadata=package_metadata or {})
            builder.finalize()
            with MotionPackage(directory, cache_size=0) as package:
                with patch.object(RigMotion, 'to_native', return_value=MetadataOnlyNative(recording)):
                    return _verify_clip(package, package.catalogue()[0])

    def test_standalone_recording_can_have_package_only_action_group_metadata(self):
        result = self.verify(package_metadata={'original_clip_id': 'Robot_Dance',
                                               'chunk_index': 0, 'chunk_count': 1})
        self.assertEqual(result['original_clip_id'], 'Robot_Dance')
        self.assertEqual(result['chunk_count'], 1)
        self.assertEqual(result['chunk_sample_count'], 3)
        self.assertIsNone(result['total_sample_count'])
        self.assertEqual(result['checked_out_of_range_pips'], [-1, 3])

    def test_descriptive_original_id_alone_does_not_require_chunk_fields(self):
        result = self.verify(package_metadata={'original_clip_id': 'source_action'})
        self.assertNotIn('chunk_count', result)

    def test_conflicting_shared_group_metadata_is_rejected(self):
        with self.assertRaisesRegex(ScoreError, 'disagree on original_clip_id'):
            self.verify(recording_metadata={'original_clip_id': 'actual', 'chunk_index': 0, 'chunk_count': 1},
                        package_metadata={'original_clip_id': 'different', 'chunk_index': 0, 'chunk_count': 1})

    def test_declared_group_bounds_still_match_actual_recording(self):
        with self.assertRaisesRegex(ScoreError, 'Recording bounds'):
            self.verify(package_metadata={'original_clip_id': 'source', 'chunk_index': 0,
                                          'chunk_count': 1, 'chunk_sample_count': 4})


if __name__ == '__main__':
    unittest.main()

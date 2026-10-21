import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from dancerudiments_authoring.motion import load_rig_motion
from dancerudiments_authoring.motion_cli import main
from dancerudiments_authoring.motion_clock import BeatMap
from dancerudiments_authoring.motion_import import RigCapture, write_capture
from dancerudiments_authoring.recording import _write_json_document, load_recording
from dancerudiments_authoring.rigs import RigChannel, RigProfile, rig_type_uri


class RigMotionCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.profile = RigProfile(rig_type_uri('cli_test', kind='custom'), 'cli_test', (
            RigChannel(1, 'root_x', 'root', 'location', 0, 'metre', -1, 1, 0),))
        self.capture = self.root / 'capture.json'
        write_capture(self.capture, RigCapture(self.profile, (0, 1), ((-1,), (1,))))

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main([str(arg) for arg in args]), 0)
        return output.getvalue()

    def test_compile_explicit_bpm_and_export_shared_recording(self):
        motion_path = self.root / 'motion.json'
        result = json.loads(self.run_cli('compile', self.capture, motion_path,
                                        '--source-bpm', '60', '--source-beat-zero', '0',
                                        '--bpm', '120', '--samples', '65'))
        self.assertEqual(result['samples'], 65)
        motion = load_rig_motion(motion_path)
        self.assertEqual(motion.recording.samples[32], (0,))
        identity = json.loads(self.run_cli('inspect', motion_path))
        self.assertEqual(identity['profile_sha256'], self.profile.fingerprint)
        recording_path = self.root / 'recording.json'
        self.run_cli('recording', motion_path, recording_path)
        self.assertEqual(load_recording(recording_path), motion.recording)

    def test_source_phase_is_required_and_input_is_preserved(self):
        for args in (
            ('compile', self.capture, self.root / 'out.json', '--source-bpm', '60', '--bpm', '120', '--samples', '1'),
            ('compile', self.capture, self.capture, '--source-bpm', '60', '--source-beat-zero', '0',
             '--bpm', '120', '--samples', '1', '--overwrite'),
        ):
            before = self.capture.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                main([str(a) for a in args])
            self.assertEqual(exc.exception.code, 2)
            self.assertEqual(self.capture.read_bytes(), before)

    def test_explicit_variable_source_map_and_channel_csv(self):
        beat_path = self.root / 'beats.json'
        beat_map = BeatMap(((0, 0), (0.5, 1), (1, 3)), 'measured source')
        _write_json_document(beat_path, beat_map.to_dict())
        motion_path = self.root / 'motion.json'
        self.run_cli('compile', self.capture, motion_path, '--source-beat-map', beat_path,
                     '--bpm', '100', '--samples', '193')
        motion = load_rig_motion(motion_path)
        self.assertEqual(motion.recording.samples[64], (0,))
        self.assertEqual(motion.recording.samples[192], (1,))
        profile_path = self.root / 'profile.json'
        _write_json_document(profile_path, self.profile.to_dict())
        output = self.root / 'channels.csv'
        self.run_cli('channels', profile_path, '--output', output)
        with output.open(newline='', encoding='utf-8') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]['number'], '1')
        self.assertEqual(rows[0]['bone'], 'root')
        before = output.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['channels', str(profile_path), '--output', str(output)])
        self.assertEqual(output.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()

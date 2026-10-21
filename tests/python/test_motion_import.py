import copy
from fractions import Fraction
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dancerudiments_authoring._validation import ScoreError
from dancerudiments_authoring.motion_clock import BeatMap
from dancerudiments_authoring.motion_import import RigCapture, compile_capture, load_capture, write_capture
from dancerudiments_authoring.recording import RecordingClock
from dancerudiments_authoring.rigs import RigChannel, RigProfile, rig_type_uri


def profile():
    channels = [RigChannel(1, "root_x", "root", "location", 0, "metre", -2, 2, 0)]
    for axis in range(4):
        channels.append(RigChannel(axis + 2, "root_q" + "wxyz"[axis], "root", "rotation_quaternion",
                                   axis, "unitless", -1, 1, 1 if axis == 0 else 0,
                                   interpolation="quaternion", rotation_mode="QUATERNION"))
    channels += [RigChannel(6, "parent", "root", '["parent"]', -1, "index", 0, 4, 1,
                            value_type="integer", interpolation="step"),
                 RigChannel(7, "enabled", "root", '["enabled"]', -1, "boolean", 0, 1, 0,
                            value_type="boolean", interpolation="step"),
                 RigChannel(8, "ik_blend", "root", '["IK_FK"]', -1, "unitless", 0, 1, 0)]
    return RigProfile(rig_type_uri("synthetic", kind="custom"), "synthetic", tuple(channels))


def capture():
    return RigCapture(profile(), (0, 1),
                      ((0, 1, 0, 0, 0, 1, 0, 0),
                       (2, math.sqrt(0.5), 0, 0, math.sqrt(0.5), 3, 1, 1)),
                      json.dumps({"author": "DanceRudiments", "license": "MIT", "source": "synthetic"}))


def compile_motion(source=None, **kwargs):
    options = dict(name="synthetic_dance",
                   source_beat_map=BeatMap.from_bpm(60, beat_zero_seconds=0, source="synthetic one-second beat"),
                   clock=RecordingClock(120, "target tempo", phase_status="supplied"), sample_count=65)
    options.update(kwargs)
    return compile_capture(capture() if source is None else source, **options)


class MotionImportTests(unittest.TestCase):
    def test_resamples_all_channels_and_preserves_control_semantics(self):
        motion = compile_motion()
        self.assertEqual(len(motion.recording.samples), 65)
        self.assertEqual(motion.recording.dimensions, motion.profile.dimensions)
        middle = motion.profile.decode(motion.recording.samples[32])
        self.assertAlmostEqual(middle[0], 1)
        self.assertAlmostEqual(middle[1], math.cos(math.pi / 8), places=11)
        self.assertAlmostEqual(middle[4], math.sin(math.pi / 8), places=11)
        self.assertEqual(middle[5:7], (1, False))
        self.assertAlmostEqual(middle[7], 0.5)
        last = motion.profile.decode(motion.recording.samples[64])
        self.assertEqual(last[5:7], (3, True))
        self.assertEqual(motion.recording.clock.bpm, 120)
        self.assertEqual(motion.recording.provenance["source_capture_sha256"], capture().fingerprint)
        self.assertEqual(motion.recording.provenance["loop_policy"], "non_looping")
        for row in motion.recording.samples:
            physical = motion.profile.decode(row)
            self.assertAlmostEqual(sum(value * value for value in physical[1:5]), 1, places=10)

    def test_antipodal_quaternions_do_not_turn_or_flip_at_endpoint(self):
        src = capture()
        frames = ((0, 1, 0, 0, 0, 1, 0, 0), (0, -1, 0, 0, 0, 1, 0, 0))
        src = RigCapture(src.profile, (0, 1), frames)
        result = compile_motion(src)
        for row in result.recording.samples:
            self.assertEqual(result.profile.decode(row)[1:5], (1, 0, 0, 0))

    def test_half_double_rate_and_explicit_phase(self):
        slow = compile_motion(motion_rate="1/2", sample_count=129)
        fast = compile_motion(motion_rate=2, sample_count=33)
        ordinary = compile_motion()
        self.assertEqual(slow.recording.samples[64], ordinary.recording.samples[32])
        self.assertEqual(fast.recording.samples[16], ordinary.recording.samples[32])
        self.assertEqual(slow.recording.samples[-1], fast.recording.samples[-1])
        cropped = compile_motion(source_beat_offset="1/3", sample_count=1)
        self.assertAlmostEqual(cropped.profile.decode(cropped.recording.samples[0])[0], 2 / 3, places=11)

    def test_variable_source_tempo_and_negative_absolute_pips(self):
        src = capture()
        src = RigCapture(src.profile, (-1, 0, 1),
                         ((-1, 1, 0, 0, 0, 1, 0, 0),
                          (0, 1, 0, 0, 0, 1, 0, 0),
                          (1, 1, 0, 0, 0, 1, 0, 0)))
        beat_map = BeatMap(((-1, -1), (0, 0), (1, 2)), "measured variable tempo")
        motion = compile_motion(src, source_beat_map=beat_map,
                                clock=RecordingClock(100, "target", start_pip=-64), sample_count=193)
        for index, expected in ((0, -1), (64, 0), (128, 0.5), (192, 1)):
            self.assertAlmostEqual(motion.profile.decode(motion.recording.samples[index])[0], expected)
        self.assertEqual(motion.recording.clock.start_pip, -64)
        self.assertEqual(motion.recording.provenance["source_beat_map"], beat_map.to_dict())

    def test_rejects_overshoot_and_never_clamps_or_loops(self):
        for kwargs in [dict(sample_count=66), dict(sample_count=1, source_beat_offset=-1),
                       dict(sample_count=0), dict(sample_count=True), dict(motion_rate=0),
                       dict(motion_rate=-1), dict(motion_rate=float("nan")),
                       dict(clock=RecordingClock(120, "test", start_pip=2147483647), sample_count=1),
                       dict(source_beat_map=None)]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ScoreError):
                compile_motion(**kwargs)
        with self.assertRaises(ScoreError):
            compile_motion(source_beat_map=BeatMap(((0.1, 0.1), (1, 1)), "bounded"))

    def test_static_one_frame_capture_requires_exact_time(self):
        src = capture()
        still = RigCapture(src.profile, (0,), (src.frames[0],))
        self.assertEqual(len(compile_motion(still, sample_count=1).recording.samples), 1)
        with self.assertRaises(ScoreError):
            compile_motion(still, sample_count=2)

    def test_strict_capture_json_and_atomic_no_clobber(self):
        src = capture()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "capture.json"
            write_capture(target, src)
            self.assertEqual(load_capture(target), src)
            before = target.read_bytes()
            with self.assertRaises(FileExistsError):
                write_capture(target, src)
            self.assertEqual(before, target.read_bytes())
            target.write_text('{"format": 1, "format": 2}', encoding="utf-8")
            with self.assertRaises(ScoreError):
                load_capture(target)
        for key, value in [("schema_version", True), ("format", "pickle"), ("extra", 1),
                           ("profile_sha256", "0" * 64), ("type_uri", "syn://type/other"),
                           ("frame_times_seconds", [0, 0]), ("frame_times_seconds", [0, float("nan")]),
                           ("frames", [[0]]), ("provenance", [])]:
            doc = copy.deepcopy(src.to_dict())
            doc[key] = value
            with self.subTest(key=key), self.assertRaises(ScoreError):
                RigCapture.from_dict(doc)
        alias = src.to_dict()
        alias["type_uri"] = alias["type_uri"].replace("syn://", "synny://", 1)
        self.assertEqual(RigCapture.from_dict(alias), src)

    def test_physical_ranges_switches_and_quaternion_validity(self):
        src = capture()
        for index, value in [(0, 100), (1, 0), (5, 1.5), (6, 0.5), (7, 1.1), (7, True)]:
            frames = [list(row) for row in src.frames]
            frames[0][index] = value
            with self.subTest(index=index, value=value), self.assertRaises(ScoreError):
                RigCapture(src.profile, src.frame_times_seconds, frames)
        # Float32 capture noise is accepted, then normalized in compilation.
        frames = [list(row) for row in src.frames]
        frames[0][1] = 0.9999999
        perturbed = RigCapture(src.profile, src.frame_times_seconds, frames)
        compiled = compile_motion(perturbed)
        self.assertEqual(compiled.profile.decode(compiled.recording.samples[0])[1], 1)

    def test_scalar_resource_limit_is_checked_before_compilation(self):
        src = capture()
        with patch("dancerudiments_authoring.motion_import.MAX_RECORDING_VALUES", 16):
            with self.assertRaises(ScoreError):
                compile_motion(src, sample_count=3)
            with self.assertRaises(ScoreError):
                RigCapture(src.profile, (0, 1, 2), (src.frames[0], src.frames[0], src.frames[0]))

    def test_euler_values_preserve_explicit_sampled_winding(self):
        ch = RigChannel(1, "spin", "root", "rotation_euler", 2, "radian", -4 * math.pi, 4 * math.pi,
                        0, rotation_mode="XYZ")
        rig = RigProfile(rig_type_uri("euler", kind="custom"), "euler", (ch,))
        src = RigCapture(rig, (0, 1), ((0,), (2 * math.pi,)))
        motion = compile_motion(src)
        self.assertAlmostEqual(rig.decode(motion.recording.samples[32])[0], math.pi)


if __name__ == "__main__":
    unittest.main()

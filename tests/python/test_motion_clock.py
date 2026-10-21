import copy
from fractions import Fraction
import unittest

from dancerudiments_authoring._validation import ScoreError
from dancerudiments_authoring.motion_clock import BeatAnchor, BeatMap


class MotionClockTests(unittest.TestCase):
    def test_piecewise_tempo_map_and_inverse(self):
        clock = BeatMap(((0, 0), (0.5, 1), (1.5, 2), (2, 4)),
                        "manually checked beat anchors", phase_status="supplied")
        self.assertEqual(clock.beat_at(1), 1.5)
        self.assertEqual(clock.seconds_at(1.5), 1)
        self.assertEqual(clock.pip_at(1), 96)
        self.assertEqual(clock.pip_at(1.75), 192)
        for anchor in clock.anchors:
            self.assertEqual(clock.beat_fraction(anchor.seconds), anchor.beat)
            self.assertEqual(clock.seconds_fraction(anchor.beat), anchor.seconds)

    def test_absolute_constant_tempo_has_no_accumulated_hop_error(self):
        clock = BeatMap.from_bpm(123.456789, beat_zero_seconds=0.12345,
                                 source="explicit tempo", phase_status="supplied")
        restored = BeatMap.from_dict(clock.to_dict())
        self.assertEqual(clock, restored)
        for pip in (-64000, -1, 0, 1, 64, 10000000):
            seconds = restored.seconds_fraction(Fraction(pip, 64))
            self.assertEqual(clock.pip_at(seconds), pip)
            self.assertEqual(seconds, Fraction("0.12345") + Fraction(pip, 64) * 60 / Fraction("123.456789"))

    def test_negative_positions_floor_and_do_not_loop(self):
        clock = BeatMap.from_bpm(120, beat_zero_seconds=0, source="test")
        self.assertEqual(clock.pip_at(-0.001), -1)
        self.assertEqual(clock.pip_at(-0.5), -64)
        self.assertEqual(clock.pip_at(0.5), 64)
        with self.assertRaises(ScoreError):
            clock.pip_at(100000000)

    def test_measured_extent_is_enforced_in_both_directions(self):
        clock = BeatMap(((1, 0), (2, 2)), "measured")
        for seconds in (0.9, 2.1):
            with self.assertRaises(ScoreError):
                clock.beat_at(seconds)
        for beat in (-0.1, 2.1):
            with self.assertRaises(ScoreError):
                clock.seconds_at(beat)
        extended = BeatMap(clock.anchors, "explicit extrapolation", extrapolate=True)
        self.assertEqual(extended.beat_at(0), -2)

    def test_rejects_noninvertible_or_ambiguous_maps(self):
        for anchors in [(), ((0, 0),), ((0, 0), (0, 1)), ((0, 0), (1, 0)),
                        ((1, 1), (0, 2)), ((0, 0), (1, -1)), ((0, 0), (float("inf"), 1)),
                        ((True, 0), (1, 1))]:
            with self.subTest(anchors=anchors), self.assertRaises(ScoreError):
                BeatMap(anchors, "test")
        for tempo in (0, -1, True, float("nan")):
            with self.subTest(tempo=tempo), self.assertRaises(ScoreError):
                BeatMap.from_bpm(tempo, beat_zero_seconds=0, source="test")
        for kwargs in [dict(source=""), dict(bpm_status="unknown"),
                       dict(phase_status="confirmed"), dict(extrapolate=1)]:
            with self.assertRaises(ScoreError):
                BeatMap(((0, 0), (1, 1)), **dict(dict(source="test"), **kwargs))

    def test_strict_schema_and_exact_rational_serialization(self):
        clock = BeatMap((BeatAnchor("1/3", "-1/3"), BeatAnchor("7/3", "5/3")), "rational anchors")
        self.assertEqual(BeatMap.from_dict(clock.to_dict()), clock)
        self.assertEqual(clock.seconds_fraction(0), Fraction(2, 3))
        for key, value in [("format", "other"), ("schema_version", True),
                           ("pips_per_beat", 16), ("interpolation", "cubic"), ("extra", 1)]:
            doc = copy.deepcopy(clock.to_dict())
            doc[key] = value
            with self.subTest(key=key), self.assertRaises(ScoreError):
                BeatMap.from_dict(doc)
        doc = clock.to_dict()
        doc["anchors"][0]["unused"] = 1
        with self.assertRaises(ScoreError):
            BeatMap.from_dict(doc)


if __name__ == "__main__":
    unittest.main()

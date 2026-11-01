"""Independent numeric/physical checks for bounded offline loop finishing."""
from dataclasses import replace
import copy
import importlib.util
import json
import math
import unittest
from unittest.mock import patch

from dancerudiments_authoring._validation import ScoreError
from dancerudiments_authoring.loop_repair import (
    FootContact, LoopRepairOptions, contacts_from_world_report, propose_loop_repairs, repair_loop,
    verify_compiled_loop_seam,
)
from dancerudiments_authoring.motion_clock import BeatMap
from dancerudiments_authoring.motion_import import RigCapture, compile_capture
from dancerudiments_authoring.recording import RecordingClock
from dancerudiments_authoring.rigs import RigChannel, RigProfile, rig_type_uri
from dancerudiments_authoring.world_motion import source_valid_segments


def fixture(*, flip=False, root_drift=.10, rotation_drift=.15, count=129, start=0.):
    channels = [RigChannel(i+1, "root_"+axis, "Root", "location", i, "source_unit", -2, 2, 0)
                for i, axis in enumerate("xyz")]
    channels += [RigChannel(i+4, "arm_q"+axis, "Arm", "rotation_quaternion", i,
                            "unitless", -1, 1, 1 if i == 0 else 0,
                            interpolation="quaternion", rotation_mode="QUATERNION")
                 for i, axis in enumerate("wxyz")]
    channels += [RigChannel(8, "enabled", "Arm", '["enabled"]', -1, "boolean", 0, 1, 1,
                            value_type="boolean", interpolation="step")]
    profile = RigProfile(rig_type_uri("loop_fixture", kind="custom"), "loop fixture", tuple(channels))
    times, rows = [], []
    for i in range(count):
        u = i/(count-1)
        angle = .6*math.sin(2*math.pi*u)+rotation_drift*u*u
        q = [math.cos(angle/2), 0., 0., math.sin(angle/2)]
        if flip and i % 2:
            q = [-v for v in q]
        times.append(start+2*u)
        rows.append((root_drift*u+.02*math.sin(2*math.pi*u), 0., 0., *q, 1))
    return RigCapture(profile, times, rows, json.dumps({"source": "synthetic", "licence": "MIT"}))


def portable(*, slip=.1, conflicting=False):
    # The independently supplied skeleton has explicit rest frames and units.
    # An arm keeps moving when foot stabilization removes root drift.
    from dancerudiments_authoring.bvh_import import parse_bvh
    hierarchy = """HIERARCHY
ROOT Root
{
 OFFSET 0 0 1
 CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation
 JOINT LeftFoot
 {
  OFFSET -0.3 0 -1
  CHANNELS 3 Xposition Yposition Zposition
  End Site { OFFSET 0 0.2 0 }
 }
 JOINT RightFoot
 {
  OFFSET 0.3 0 -1
  CHANNELS 3 Xposition Yposition Zposition
  End Site { OFFSET 0 0.2 0 }
 }
 JOINT Arm
 {
  OFFSET 0 0 0.7
  CHANNELS 3 Zrotation Xrotation Yrotation
  End Site { OFFSET 0.5 0 0 }
 }
}
MOTION
Frames: 129
Frame Time: 0.015625
"""
    rows = []
    for i in range(129):
        s = math.sin(2*math.pi*i/128)
        root = 0. if conflicting else slip*s
        left = slip*s if conflicting else 0.
        right = -slip*s if conflicting else 0.
        rows.append((root, 0, 0, 0, 0, 0, left, 0, 0, right, 0, 0, 30*s, 0, 0))
    clip = parse_bvh(hierarchy+"\n".join(" ".join(map(str, row)) for row in rows)+"\n",
                     source_id="loop_contact_fixture", axis_forward="Y", axis_up="Z", location_range=2)
    return RigCapture(clip.profile, tuple(i/64 for i in range(129)), tuple(map(tuple, clip.frames)))


class LoopRepairTests(unittest.TestCase):
    def options(self, **kwargs):
        return replace(LoopRepairOptions(translation_scale=1.), **kwargs)

    def test_closes_pose_and_tangent_without_changing_source(self):
        source = fixture()
        before = copy.deepcopy(source.to_dict())
        result = repair_loop(source, start_seconds=0, end_seconds=2, options=self.options())
        self.assertTrue(result.accepted, result.report)
        self.assertEqual(source.to_dict(), before)
        self.assertEqual(result.capture.profile.fingerprint, source.profile.fingerprint)
        self.assertNotEqual(result.capture.fingerprint, source.fingerprint)
        self.assertGreater(result.report["before"]["max_rotation_seam_radians"], .1)
        self.assertLess(result.report["after"]["max_rotation_seam_radians"], 1e-10)
        self.assertLess(result.report["after"]["max_rotation_velocity_jump_radians_per_second"], 1e-10)
        self.assertLess(result.report["after"]["max_translation_velocity_jump"], 1e-10)
        self.assertGreater(result.report["activity_retention"], .65)
        self.assertFalse(result.report["loop_seam_approved"])
        self.assertFalse(result.report["audio_beat_alignment_verified"])
        self.assertEqual(result.capture.provenance["source_capture_sha256"], source.fingerprint)
        self.assertTrue(result.capture.provenance["repair"]["accepted"])

    def test_sign_changes_do_not_change_corrected_rotations(self):
        ordinary, flipped = fixture(), fixture(flip=True)
        a = repair_loop(ordinary, start_seconds=0, end_seconds=2, options=self.options())
        b = repair_loop(flipped, start_seconds=0, end_seconds=2, options=self.options())
        self.assertTrue(a.accepted and b.accepted)
        for x, y in zip(a.capture.frames, b.capture.frames):
            self.assertAlmostEqual(abs(sum(p*q for p, q in zip(x[3:7], y[3:7]))), 1., places=11)
            self.assertEqual(x[:3], y[:3])
        self.assertAlmostEqual(a.report["corrections"]["max_rotation_radians"],
                               b.report["corrections"]["max_rotation_radians"], places=11)

    def test_full_turn_preserves_motion_with_antipodal_closing_quaternion(self):
        source = fixture(root_drift=0, rotation_drift=0)
        frames = []
        for index, row in enumerate(source.frames):
            angle = 2*math.pi*index/(len(source.frames)-1)
            frames.append((*row[:3], math.cos(angle/2), 0., 0., math.sin(angle/2), 1))
        source = RigCapture(source.profile, source.frame_times_seconds, frames)
        result = repair_loop(source, start_seconds=0, end_seconds=2, options=self.options())
        self.assertTrue(result.accepted, result.report)
        self.assertAlmostEqual(result.report["activity_retention"], 1., places=9)
        # Same orientation, opposite representation: the interior still reaches
        # the half-turn instead of unwinding the entire performance to identity.
        self.assertAlmostEqual(result.capture.frames[0][3], -result.capture.frames[-1][3], places=9)
        self.assertAlmostEqual(abs(result.capture.frames[64][6]), 1., places=9)

    def test_in_place_root_is_explicit_and_entire_change_is_bounded(self):
        source = fixture()
        options = self.options(root_policy="in_place", root_bone="Root")
        result = repair_loop(source, start_seconds=0, end_seconds=2, options=options)
        self.assertTrue(result.accepted, result.report)
        self.assertAlmostEqual(result.report["root_travel_removed"][0], .1)
        self.assertAlmostEqual(result.capture.frames[0][0], 0., places=10)
        self.assertAlmostEqual(result.capture.frames[-1][0], 0., places=10)
        self.assertGreaterEqual(result.report["corrections"]["max_translation"], .0999)
        rejected = repair_loop(source, start_seconds=0, end_seconds=2,
                               options=replace(options, max_translation_correction_fraction=.03))
        self.assertFalse(rejected.accepted)
        self.assertIn("translation_correction_limit", rejected.report["rejection_reasons"])

    def test_discrete_selector_seam_is_rejected_without_blending(self):
        source = fixture()
        rows = [list(row) for row in source.frames]
        rows[-1][-1] = 0
        changed = RigCapture(source.profile, source.frame_times_seconds, rows)
        result = repair_loop(changed, start_seconds=0, end_seconds=2, options=self.options())
        self.assertFalse(result.accepted)
        self.assertIn("discrete_selector_seam_mismatch", result.report["rejection_reasons"])
        self.assertEqual(changed.frames[-1][-1], 0)

    def test_correction_budget_and_idle_rejection(self):
        source = fixture(rotation_drift=.9)
        result = repair_loop(source, start_seconds=0, end_seconds=2,
                             options=self.options(max_rotation_correction_radians=.1))
        self.assertIsNone(result.capture)
        self.assertIn("rotation_correction_limit", result.report["rejection_reasons"])
        still = RigCapture(source.profile, (0., 2.), (source.frames[0], source.frames[0]))
        result = repair_loop(still, start_seconds=0, end_seconds=2, options=self.options())
        self.assertIn("insufficient_meaningful_motion", result.report["rejection_reasons"])

    def test_unknown_translation_units_require_explicit_scale(self):
        result = repair_loop(fixture(), start_seconds=0, end_seconds=2)
        self.assertFalse(result.accepted)
        self.assertIn("translation_scale_required", result.report["rejection_reasons"])

    def test_proposal_is_separate_and_exactly_on_native_pip_grid(self):
        source = fixture(start=3.)
        results = propose_loop_repairs(source, bpm=120, beat_zero_seconds=3., beat_counts=(4,),
                                       max_candidates=2, options=self.options())
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertTrue(result.accepted, result.report)
        self.assertEqual(result.report["proposal"]["beats"], 4)
        self.assertEqual(len(result.capture.frames), 4*64+1)
        motion = compile_capture(result.capture, name="corrected_loop",
            source_beat_map=BeatMap.from_bpm(120, beat_zero_seconds=0, source="synthetic supplied hypothesis"),
            clock=RecordingClock(120, "synthetic preview", bpm_status="estimated", phase_status="estimated"),
            sample_count=4*64)
        frames = [motion.profile.decode(row) for row in motion.recording.samples]
        # Independent scalar finite differences around the actual half-open seam.
        self.assertAlmostEqual(frames[0][0]-frames[-1][0], frames[1][0]-frames[0][0], places=10)
        self.assertEqual(motion.recording.provenance["loop_policy"], "non_looping")
        check = verify_compiled_loop_seam(motion, result.capture, result.report)
        self.assertTrue(check["passed"], check)
        # A different sampler rate can preserve a valid RigMotion container and
        # every hash in its compiler provenance while changing the actual clip.
        wrong = compile_capture(result.capture, name="incorrect_rate",
            source_beat_map=BeatMap.from_bpm(120, beat_zero_seconds=0, source="synthetic"),
            clock=RecordingClock(120, "synthetic preview"), sample_count=4*64, motion_rate=.5)
        check = verify_compiled_loop_seam(wrong, result.capture, result.report)
        self.assertFalse(check["passed"])
        self.assertIn("compiled_samples_differ_from_corrected_capture", check["rejection_reasons"])

    def test_invalid_parameters_and_bounds_fail(self):
        source = fixture()
        for params in ({"sample_count": True}, {"blend_fraction": float("nan")},
                       {"root_policy": "invent"}, {"translation_scale": 0}, {"root_axes": (1, 1)}):
            with self.subTest(params=params), self.assertRaises(ScoreError):
                LoopRepairOptions(**params)
        for start, end in ((-1, 2), (0, 3), (1, 1)):
            with self.assertRaises(ScoreError):
                repair_loop(source, start_seconds=start, end_seconds=end)

    def test_timestamp_holes_are_rejected_before_interpolating_any_pose(self):
        original = fixture()
        keep = [i for i,t in enumerate(original.frame_times_seconds) if t <= .75 or t >= 1.25]
        source = RigCapture(original.profile,
            tuple(original.frame_times_seconds[i] for i in keep),
            tuple(original.frames[i] for i in keep))
        self.assertEqual(source_valid_segments(source), ((0.,.75),(1.25,2.)))
        with patch('dancerudiments_authoring.loop_repair._frame_at',
                   side_effect=AssertionError('No gap-crossing interpolation may run')) as sampler:
            for start,end in ((0.,2.),(.8,.9),(.5,1.),(.75,1.25)):
                with self.subTest(start=start,end=end), self.assertRaisesRegex(ScoreError,'timestamp gap'):
                    repair_loop(source,start_seconds=start,end_seconds=end,options=self.options())
            sampler.assert_not_called()

    def test_proposals_use_only_continuous_windows_even_when_no_world_evidence_exists(self):
        from dancerudiments_authoring.motion_import import _frame_at
        cycle = fixture()
        source = RigCapture(cycle.profile,
            cycle.frame_times_seconds+tuple(t+100. for t in cycle.frame_times_seconds),
            cycle.frames+cycle.frames)
        original = copy.deepcopy(source.to_dict())
        with patch('dancerudiments_authoring.loop_repair._frame_at', wraps=_frame_at) as sampler:
            results = propose_loop_repairs(source,bpm=120.,beat_counts=(4,),
                max_candidates=2,max_windows=2,options=self.options())
        self.assertEqual(len(results),2)
        self.assertTrue(all(result.accepted for result in results))
        self.assertEqual({(r.report['source_start_seconds'],r.report['source_end_seconds']) for r in results},
                         {(0.,2.),(100.,102.)})
        self.assertTrue(all(0. <= float(call.args[1]) <= 2. or 100. <= float(call.args[1]) <= 102.
                            for call in sampler.call_args_list))
        self.assertEqual(source.to_dict(),original)

    def test_legitimate_irregular_sampling_is_not_rejected_as_missing_coverage(self):
        source = fixture()
        irregular = replace(source, frame_times_seconds=tuple(
            t+(.003 if i % 2 else 0.) for i,t in enumerate(source.frame_times_seconds)))
        self.assertEqual(source_valid_segments(irregular),((0.,2.),))
        result = repair_loop(irregular,start_seconds=0.,end_seconds=2.,options=self.options())
        self.assertTrue(result.accepted,result.report)
        # Exactly three median intervals remains covered; strictly larger gaps
        # split, matching the existing world-evidence threshold without a floor.
        times = (0.,1/64,2/64,5/64,6/64,7/64,8/64)
        boundary = RigCapture(source.profile,times,source.frames[:len(times)])
        self.assertEqual(source_valid_segments(boundary),((0.,8/64),))
        hole = replace(boundary,frame_times_seconds=(*times[:3],times[3]+1e-6,*times[4:]))
        self.assertEqual(source_valid_segments(hole),((0.,2/64),(5/64+1e-6,8/64)))

    def test_single_frame_is_a_point_and_needs_no_numpy_for_coverage(self):
        source = fixture()
        point = RigCapture(source.profile,(5.,),(source.frames[0],))
        with patch('dancerudiments_authoring.world_motion._numpy',
                   side_effect=AssertionError('Coverage does not require NumPy')):
            self.assertEqual(source_valid_segments(point),((5.,5.),))
        self.assertEqual(propose_loop_repairs(point,bpm=120.,options=self.options()),())
        with self.assertRaisesRegex(ScoreError,'Loop bounds'):
            repair_loop(point,start_seconds=5.,end_seconds=5.1,options=self.options())


@unittest.skipUnless(importlib.util.find_spec("numpy") is not None, "optional NumPy authoring extra unavailable")
class LoopContactTests(unittest.TestCase):
    def test_world_coverage_keeps_isolated_frames_without_inventing_contacts(self):
        from dancerudiments_authoring.world_motion import analyze_world_motion
        original = portable(slip=0.)
        source = RigCapture(original.profile,(0.,1/64,2/64,1.),
                            (original.frames[0],original.frames[1],original.frames[2],original.frames[64]))
        report = analyze_world_motion(source)
        self.assertEqual(report['validity_segments_seconds'],[[0.,2/64],[1.,1.]])
        self.assertEqual(report['derivative_validity_segments_seconds'],[[0.,2/64]])
        self.assertEqual(report['envelopes']['root_speed'][-1],0.)
        self.assertFalse(report['contact_events'])
        self.assertFalse(report['contact_intervals'])
        point = RigCapture(original.profile,(1.,),(original.frames[64],))
        report = analyze_world_motion(point)
        self.assertTrue(report['supported'])
        self.assertEqual(report['validity_segments_seconds'],[[1.,1.]])
        self.assertEqual(report['derivative_validity_segments_seconds'],[])
        self.assertFalse(report['motion_accents'])
        self.assertFalse(report['contact_intervals'])

    def test_sliding_contact_rejected_and_root_stabilization_measured(self):
        source = portable()
        contacts = (FootContact("LeftFoot", 0., 2.), FootContact("RightFoot", 0., 2.))
        result = repair_loop(source, start_seconds=0, end_seconds=2, contacts=contacts)
        self.assertFalse(result.accepted)
        self.assertIn("foot_contact_slip_limit", result.report["rejection_reasons"])
        corrected = repair_loop(source, start_seconds=0, end_seconds=2, contacts=contacts,
                                 options=LoopRepairOptions(contact_policy="root_stabilize"))
        self.assertTrue(corrected.accepted, corrected.report)
        self.assertTrue(corrected.report["contacts"]["constraints_satisfied"])
        self.assertFalse(corrected.report["contacts"]["foot_plant_verified"])
        self.assertGreater(corrected.report["contacts"]["max_root_correction"], .09)
        for item in corrected.report["contacts"]["after"]:
            self.assertLess(item["max_slip"], 1e-8)
        self.assertLess(corrected.report["after"]["max_translation_velocity_jump"], 1e-8)
        motion = compile_capture(corrected.capture, name="planted_loop",
            source_beat_map=BeatMap.from_bpm(60, beat_zero_seconds=0, source="synthetic"),
            clock=RecordingClock(60, "synthetic preview"), sample_count=128)
        check = verify_compiled_loop_seam(motion, corrected.capture, corrected.report)
        self.assertTrue(check["passed"], check)
        self.assertEqual(len(check["contacts"]), 2)

    def test_conflicting_feet_fail_instead_of_stretching_skeleton(self):
        source = portable(conflicting=True)
        result = repair_loop(source, start_seconds=0, end_seconds=2,
            contacts=(FootContact("LeftFoot", 0., 2.), FootContact("RightFoot", 0., 2.)),
            options=LoopRepairOptions(contact_policy="root_stabilize"))
        self.assertFalse(result.accepted)
        self.assertIn("conflicting_foot_contacts", result.report["rejection_reasons"])

    def test_contact_correction_uses_rotated_root_rest_basis(self):
        import numpy as np
        source = portable()
        metadata = source.profile.source
        rotation = np.array(((0., -1., 0., 0.), (1., 0., 0., 0.),
                             (0., 0., 1., 0.), (0., 0., 0., 1.)))
        for bone in metadata["skeleton"]:
            bone["rest_matrix"] = (rotation @ np.array(bone["rest_matrix"]).reshape(4, 4)).ravel().tolist()
        profile = replace(source.profile, source_json=json.dumps(metadata))
        source = RigCapture(profile, source.frame_times_seconds, source.frames)
        result = repair_loop(source, start_seconds=0, end_seconds=2,
            contacts=(FootContact("LeftFoot", 0., 2.),),
            options=LoopRepairOptions(contact_policy="root_stabilize"))
        self.assertTrue(result.accepted, result.report)
        self.assertLess(result.report["contacts"]["after"][0]["max_slip"], 1e-8)

    def test_explicit_nested_root_uses_evaluated_parent_rotation_and_scale(self):
        import numpy as np
        from dancerudiments_authoring.world_motion import evaluate_world_motion
        source = portable()
        metadata = source.profile.source
        metadata['skeleton'].insert(0, {'name': 'Object', 'parent': None,
            'rest_matrix': np.eye(4).ravel().tolist(), 'length': .1, 'use_deform': False})
        next(b for b in metadata['skeleton'] if b['name'] == 'Root')['parent'] = 'Object'
        metadata['object_motion_root'] = 'Object'
        metadata['omitted_neutral_groups'].append(
            {'bone': 'Object', 'data_path': 'location', 'values': [0., 0., 0.]})
        channels = list(source.profile.channels)
        for path, defaults, bound in (('rotation_quaternion', (1., 0., 0., 0.), 1.),
                                       ('scale', (1., 1., 1.), 2.)):
            for axis, default in enumerate(defaults):
                channels.append(RigChannel(len(channels)+1, f'object_{path}_{axis}',
                    'Object', path, axis, 'unitless', -bound, bound, default,
                    interpolation='quaternion' if path == 'rotation_quaternion' else 'linear',
                    rotation_mode='QUATERNION' if path == 'rotation_quaternion' else ''))
        profile = replace(source.profile, channels=tuple(channels), source_json=json.dumps(metadata))
        # The wrapper rest frame is identity. Its evaluated pose rotates and
        # scales the selected root, which a rest-only conversion cannot undo.
        parent_pose = (math.cos(math.pi/8), 0., 0., math.sin(math.pi/8), 1.3, .75, 1.)
        source = RigCapture(profile, source.frame_times_seconds,
                            tuple((*row, *parent_pose) for row in source.frames))
        contacts = (FootContact('LeftFoot', 0., 2.), FootContact('RightFoot', 0., 2.))
        defaults = repair_loop(source, start_seconds=0, end_seconds=2, contacts=contacts,
                              options=LoopRepairOptions(contact_policy='root_stabilize'))
        self.assertIn('contact_stabilization_requires_complete_root_translation',
                      defaults.report['rejection_reasons'])
        result = repair_loop(source, start_seconds=0, end_seconds=2, contacts=contacts,
            options=LoopRepairOptions(contact_policy='root_stabilize', root_bone='Root'))
        self.assertTrue(result.accepted, result.report)
        self.assertEqual(result.capture.profile.fingerprint, source.profile.fingerprint)
        self.assertEqual(result.report['contacts']['correction_root_parent_bone'], 'Object')
        world = evaluate_world_motion(result.capture)
        for name in ('LeftFoot', 'RightFoot'):
            foot = world.positions[:, world.bone_names.index(name)]
            self.assertLess(float(np.linalg.norm(foot-foot[0], axis=1).max()), 1e-8)
        self.assertGreater(result.report['contacts']['max_world_root_correction'],
                           result.report['contacts']['max_root_correction'])
        invalid = repair_loop(source, start_seconds=0, end_seconds=2, contacts=contacts,
            options=LoopRepairOptions(contact_policy='root_stabilize', root_bone='LeftFoot'))
        self.assertFalse(invalid.accepted)
        self.assertIn('contact_stabilization_root_must_be_ancestor_of_all_contacts',
                      invalid.report['rejection_reasons'])

    def test_missing_contact_evidence_and_unsupported_rig_fail_explicitly(self):
        result = repair_loop(portable(), start_seconds=0, end_seconds=2,
                             options=LoopRepairOptions(require_contacts=True))
        self.assertIn("foot_contact_evidence_required", result.report["rejection_reasons"])
        result = repair_loop(fixture(), start_seconds=0, end_seconds=2,
                             contacts=(FootContact("Arm", 0., 2.),),
                             options=LoopRepairOptions(translation_scale=1.))
        self.assertIn("contacts_require_portable_world_evaluation", result.report["rejection_reasons"])

    def test_contact_report_identity_and_interval_clipping(self):
        source = portable(slip=0.)
        report = dict(format="dancerudiments.world-motion-evidence", schema_version=1, supported=True,
                      capture_sha256=source.fingerprint, profile_sha256=source.profile.fingerprint,
                      contact_intervals=[dict(bone="LeftFoot", start_seconds=0., end_seconds=2., confidence=.9)])
        contacts = contacts_from_world_report(source, report)
        self.assertEqual(contacts[0].evidence, "world_kinematic_hypothesis")
        stale = dict(report, capture_sha256="0"*64)
        with self.assertRaises(ScoreError):
            contacts_from_world_report(source, stale)
        result = repair_loop(source, start_seconds=.25, end_seconds=1.75, contacts=contacts,
                             options=LoopRepairOptions(max_rotation_correction_radians=1.))
        # This may fail the pose correction budget, but the contact domain must
        # be exactly the selected source window rather than guessed local time.
        self.assertEqual(result.report["contacts"]["before"][0]["source_start_seconds"], .25)
        self.assertEqual(result.report["contacts"]["before"][0]["source_end_seconds"], 1.75)


if __name__ == "__main__":
    unittest.main()

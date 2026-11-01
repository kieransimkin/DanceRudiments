"""Analytic FK/contact checks; no model or third-party motion downloads."""
from dataclasses import replace
import importlib.util
import json
import math
import unittest
from unittest.mock import patch

try:
    import numpy as np
except ImportError:
    np = None

from dancerudiments_authoring._validation import ScoreError, canonical_json
from dancerudiments_authoring.motion_import import RigCapture
from dancerudiments_authoring.rigs import RigChannel, RigProfile
from dancerudiments_authoring.world_motion import (
    ContactThresholds, UnsupportedWorldMotion, analyze_world_motion, evaluate_world_motion,
)


def rest_matrix(x=0., y=0., z=0.):
    value = np.eye(4)
    value[:3, 3] = (x, y, z)
    return value


def portable_capture(*, fps=60, duration=4., static=False, drift=0., flip=False,
                     foot_names=('LeftFoot', 'RightFoot'), times=None):
    """Independent translated foot points with alternating true held plateaux."""
    names = ('Hips', *foot_names, 'Chest')
    rest = [rest_matrix(z=1.), rest_matrix(-.2, 0, 0),
            rest_matrix(.2, 0, 0), rest_matrix(z=1.7)]
    skeleton = [dict(name=name, parent=None if i == 0 else 'Hips',
                     rest_matrix=rest[i].ravel().tolist(), length=.3, use_deform=True)
                for i, name in enumerate(names)]
    channels = []
    omitted = []
    for name in names:
        for path, default in (('location', (0., 0., 0.)),
                              ('rotation_quaternion', (1., 0., 0., 0.)),
                              ('scale', (1., 1., 1.))):
            if path == 'scale' or (path == 'rotation_quaternion' and name != 'Hips'):
                omitted.append(dict(bone=name, data_path=path, values=list(default)))
                continue
            for axis, neutral in enumerate(default):
                number = len(channels) + 1
                channels.append(RigChannel(number, f'channel_{number}', name, path, axis,
                    'unitless' if path == 'rotation_quaternion' else 'blender_unit',
                    -1. if path == 'rotation_quaternion' else -100.,
                    1. if path == 'rotation_quaternion' else 100., neutral,
                    interpolation='quaternion' if path == 'rotation_quaternion' else 'linear',
                    rotation_mode='QUATERNION' if path == 'rotation_quaternion' else ''))
    source = dict(adapter='dancerudiments.skeletal-source-v1', skeleton=skeleton,
                  object_motion_root='Hips', scene_unit_scale_length=1.,
                  omitted_neutral_groups=omitted,
                  carrier_inheritance='FULL; local location; inherit rotation',
                  coordinate_system='Blender right-handed +Z up, +Y forward')
    profile = RigProfile('syn://type/danceflow/motion/skeletal/source/synthetic/world',
                         'synthetic', tuple(channels), source_json=canonical_json(source))
    if times is None:
        times = [i/fps for i in range(round(duration*fps)+1)]
    rows = []
    for frame, time in enumerate(times):
        poses = {name: {'location': [0., 0., 0.], 'rotation_quaternion': [1., 0., 0., 0.]}
                 for name in names}
        poses['Hips']['location'][0] = time*drift
        if flip:
            poses['Hips']['rotation_quaternion'][0] = -1. if frame % 2 else 1.
        if not static:
            for offset, name in zip((0., .5), foot_names):
                phase = (time + offset) % 1.
                poses[name]['location'][2] = (0. if phase < .5 else
                                               .2*math.sin(math.tau*(phase-.5))**2)
            poses['Chest']['location'][2] = .04*(1.-math.cos(4*math.pi*time))
        rows.append(tuple(poses[c.bone][c.data_path][c.array_index] for c in channels))
    return RigCapture(profile, tuple(times), tuple(rows), '{"source":"synthetic analytic fixture"}')


def changed_source(capture, mutate):
    source = capture.profile.source
    mutate(source)
    return replace(capture, profile=replace(capture.profile, source_json=canonical_json(source)))


@unittest.skipIf(np is None, 'optional motion-import NumPy dependency unavailable')
class WorldMotionTests(unittest.TestCase):
    def test_rest_head_geometry_and_unchanged_source_identity(self):
        capture = portable_capture(static=True)
        before = capture.to_dict()
        result = evaluate_world_motion(capture)
        np.testing.assert_allclose(result.positions[0], [[0, 0, 1], [-.2, 0, 0],
                                                        [.2, 0, 0], [0, 0, 1.7]], atol=1e-12)
        self.assertEqual(capture.to_dict(), before)
        self.assertEqual(result.capture_sha256, capture.fingerprint)
        self.assertEqual(result.profile_sha256, capture.profile.fingerprint)
        self.assertFalse(result.positions.flags.writeable)
        self.assertFalse(result.world_matrices.flags.writeable)

    def test_global_travel_is_separate_from_root_relative_gestures(self):
        capture = portable_capture(static=True, drift=3.5)
        result = evaluate_world_motion(capture)
        np.testing.assert_allclose(result.positions[-1, :, 0] - result.positions[0, :, 0], 14.)
        np.testing.assert_allclose(result.root_relative_positions,
                                   np.broadcast_to(result.root_relative_positions[0], result.root_relative_positions.shape))
        evidence = analyze_world_motion(capture)
        np.testing.assert_allclose(evidence['envelopes']['root_speed'], 3.5, atol=1e-10)
        np.testing.assert_allclose(evidence['envelopes']['root_relative_speed'], 0., atol=1e-10)
        self.assertFalse(evidence['motion_accents'])
        self.assertFalse(evidence['contact_events'])
        self.assertGreater(evidence['foot_keypoints'][0]['maximum_low_height_stance_drift_relative'], 1.)

    def test_quaternion_signs_do_not_produce_motion(self):
        original = portable_capture(static=True)
        flipped = portable_capture(static=True, flip=True)
        a, b = evaluate_world_motion(original), evaluate_world_motion(flipped)
        np.testing.assert_array_equal(a.positions, b.positions)
        report = analyze_world_motion(flipped)
        self.assertFalse(report['motion_accents'])
        self.assertFalse(report['contact_events'])
        self.assertEqual(len(report['contact_intervals']), 2)

    def test_blender_alphabetical_order_is_not_mistaken_for_parent_order(self):
        source = portable_capture(static=True, drift=.2)
        reordered = changed_source(source, lambda data: data['skeleton'].reverse())
        a, b = evaluate_world_motion(source), evaluate_world_motion(reordered)
        for index, name in enumerate(a.bone_names):
            np.testing.assert_allclose(a.positions[:, index], b.positions[:, b.bone_names.index(name)])
        self.assertEqual(b.root_index, 3)

    def test_noncommuting_rest_bases_and_scaled_parent_have_analytic_position(self):
        # Rest root rotates +90 Z, child rest rotates +90 X relative to root.
        # Root basis translates +2 local X, rotates +90 Z and scales (-2,3,1).
        root = np.array([[0, -1, 0, 1], [1, 0, 0, 2], [0, 0, 1, 3], [0, 0, 0, 1.]])
        relative = np.array([[1, 0, 0, 0], [0, 0, -1, 1], [0, 1, 0, 0], [0, 0, 0, 1.]])
        source = dict(adapter='dancerudiments.skeletal-source-v1', object_motion_root='root',
            scene_unit_scale_length=1., carrier_inheritance='FULL; local location; inherit rotation',
            skeleton=[dict(name='child', parent='root', rest_matrix=(root@relative).ravel().tolist(), length=1.),
                      dict(name='root', parent=None, rest_matrix=root.ravel().tolist(), length=1.)],
            omitted_neutral_groups=[dict(bone='child', data_path='scale', values=[1,1,1]),
                                    dict(bone='child', data_path='rotation_quaternion', values=[1,0,0,0])])
        specs = [('root','location', (2.,0.,0.)),
                 ('root','rotation_quaternion', (math.sqrt(.5),0.,0.,math.sqrt(.5))),
                 ('root','scale', (-2.,3.,1.)), ('child','location',(0.,0.,.5))]
        channels, row = [], []
        for bone, path, values in specs:
            for axis, value in enumerate(values):
                i = len(channels)+1
                quaternion = path == 'rotation_quaternion'
                channels.append(RigChannel(i, f'channel_{i}', bone, path, axis, 'units',
                    -1. if quaternion else -10., 1. if quaternion else 10.,
                    1. if (quaternion and axis == 0) or path == 'scale' else 0.,
                    interpolation='quaternion' if quaternion else 'linear',
                    rotation_mode='QUATERNION' if quaternion else ''))
                row.append(value)
        profile = RigProfile('syn://type/danceflow/motion/skeletal/source/analytic/rest',
                             'analytic', tuple(channels), source_json=canonical_json(source))
        capture = RigCapture(profile, (0., .1, .2), (tuple(row),)*3)
        motion = evaluate_world_motion(capture)
        np.testing.assert_allclose(motion.positions[0, 1], (1,4,3), atol=1e-12)
        np.testing.assert_allclose(motion.positions[0, 0], (1,2.5,3), atol=1e-12)
        np.testing.assert_allclose(motion.root_relative_positions[0, 0], (0,.5,0), atol=1e-12)

    def test_alternating_contact_events_are_stable_at_30_60_120_fps(self):
        measured = []
        for fps in (30, 60, 120):
            capture = portable_capture(fps=fps)
            report = analyze_world_motion(capture, source_file_sha256='a'*64)
            plant = [event for event in report['contact_events'] if event['kind'] == 'foot_plant']
            left = [event['seconds'] for event in plant if event['bone'] == 'LeftFoot']
            right = [event['seconds'] for event in plant if event['bone'] == 'RightFoot']
            self.assertGreaterEqual(len(left), 3)
            self.assertGreaterEqual(len(right), 3)
            self.assertLess(abs(left[0] - 1.), .10)
            self.assertLess(abs(right[0] - .5), .10)
            self.assertEqual(report['source_file_sha256'], 'a'*64)
            self.assertEqual(report['capture_sha256'], capture.fingerprint)
            self.assertFalse(report['contacts_verified'])
            self.assertFalse(report['musical_timing_verified'])
            self.assertEqual(report['coordinate_basis']['units'], 'source_units')
            measured.append(left[:3])
        np.testing.assert_allclose(measured[0], measured[2], atol=1/30)

    def test_explicit_foot_mapping_handles_unconventional_names(self):
        capture = portable_capture(foot_names=('contact_a', 'contact_b'))
        self.assertFalse(analyze_world_motion(capture)['contact_events'])
        report = analyze_world_motion(capture, foot_bones=('contact_a', 'contact_b'))
        self.assertTrue(report['contact_events'])
        self.assertEqual(report['foot_selection_policy'], 'explicit_caller_bone_names')
        for bad in (['missing'], ['contact_a','contact_a'], 'contact_a'):
            with self.assertRaises(ScoreError):
                analyze_world_motion(capture, foot_bones=bad)

    def test_source_clock_and_gap_are_preserved_without_contact_bridge(self):
        times = [5+i/60 for i in range(61)] + [9+i/60 for i in range(61)]
        capture = portable_capture(static=True, times=times)
        report = analyze_world_motion(capture)
        self.assertEqual(report['frame_times_seconds'], times)
        self.assertEqual(report['validity_segments_seconds'], [[5.,6.],[9.,10.]])
        self.assertFalse(report['contact_events'])
        self.assertEqual(len(report['contact_intervals']), 4)
        self.assertTrue(all(c['end_seconds'] <= 6. or c['start_seconds'] >= 9.
                            for c in report['contact_intervals']))

    def test_missing_or_corrupt_skeleton_information_is_not_defaulted(self):
        capture = portable_capture()
        mutations = [lambda s: s['skeleton'][1].update(parent='nonexistent'),
                     lambda s: s['skeleton'][1].update(parent='LeftFoot'),
                     lambda s: s['skeleton'][2].update(name='LeftFoot'),
                     lambda s: s['skeleton'][0]['rest_matrix'].__setitem__(0,0.),
                     lambda s: s['omitted_neutral_groups'].pop(),
                     lambda s: s.update(omitted_neutral_groups=None),
                     lambda s: s['omitted_neutral_groups'][0].update(data_path=[]),
                     lambda s: s.update(scene_unit_scale_length=0.),
                     lambda s: s.update(object_motion_root='Chest')]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ScoreError):
                evaluate_world_motion(changed_source(capture, mutation))

    def test_raw_rigify_controls_explicitly_require_evaluation(self):
        capture = portable_capture()
        unsupported = changed_source(capture, lambda s: s.pop('adapter'))
        with self.assertRaisesRegex(UnsupportedWorldMotion, 'Blender evaluation'):
            evaluate_world_motion(unsupported)

    def test_report_is_finite_json_and_positions_are_opt_in(self):
        capture = portable_capture()
        result = analyze_world_motion(capture)
        self.assertNotIn('joint_positions', result)
        json.dumps(result, allow_nan=False)
        detailed = analyze_world_motion(capture, include_positions=True)
        self.assertEqual(len(detailed['joint_positions']['LeftFoot']), len(capture.frames))
        for invalid in ('broken', 'A'*64):
            with self.assertRaises(ScoreError):
                analyze_world_motion(capture, source_file_sha256=invalid)
        with patch('dancerudiments_authoring.world_motion.MAX_WORLD_MATRIX_VALUES', 10):
            with self.assertRaisesRegex(ScoreError, 'budget'):
                evaluate_world_motion(capture)

    def test_invalid_thresholds_cannot_turn_contacts_into_unconditional_acceptance(self):
        for value in (0, -1, float('nan'), True):
            with self.assertRaises(ScoreError):
                ContactThresholds(planar_speed_fraction=value)

    @unittest.skipUnless(importlib.util.find_spec('bpy'), 'optional pinned Blender runtime unavailable')
    def test_world_poses_match_actual_blender_carrier(self):
        import bpy
        from dancerudiments_authoring.blender_import import create_source_armature
        from dancerudiments_authoring.blender_bridge import apply_pose
        capture = portable_capture(fps=30, duration=.5, drift=.7)
        # Rotated, non-axis-aligned rest bases exercise the exact Blender pose
        # inheritance, rather than comparing only axis-aligned translations.
        c, s = math.cos(.6), math.sin(.6)
        rotate = np.array([[c,-s,0,0], [s,c,0,0], [0,0,1,0], [0,0,0,1.]])
        source = capture.profile.source
        for bone in source['skeleton']:
            bone['rest_matrix'] = (rotate @ np.asarray(bone['rest_matrix']).reshape(4,4)).ravel().tolist()
        source['skeleton'].reverse()
        rows = []
        for t, row in zip(capture.frame_times_seconds, capture.frames):
            row = list(row)
            q = (math.cos(t), 0., math.sin(t), 0.)
            for column, channel in enumerate(capture.profile.channels):
                if channel.bone == 'Hips' and channel.data_path == 'rotation_quaternion':
                    row[column] = q[channel.array_index]
            rows.append(tuple(row))
        capture = replace(capture, frames=tuple(rows),
                          profile=replace(capture.profile, source_json=canonical_json(source)))
        world = evaluate_world_motion(capture)
        obj = create_source_armature(capture.profile, name='world_motion_analytic_test')
        data = obj.data
        try:
            for frame in (0, 7, 15):
                apply_pose(obj, capture.profile, capture.frames[frame])
                actual = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                for index, name in enumerate(world.bone_names):
                    np.testing.assert_allclose(np.asarray(actual.pose.bones[name].matrix),
                                               world.world_matrices[frame,index], atol=2e-6)
        finally:
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.armatures.remove(data)


if __name__ == '__main__':
    unittest.main()

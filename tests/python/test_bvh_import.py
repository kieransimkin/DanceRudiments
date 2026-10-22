"""Synthetic BVH regression fixtures; no third-party motion or Blender required."""
from dataclasses import replace
from fractions import Fraction
import itertools
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

try:
    import numpy as np
except ImportError:
    np = None

from dancerudiments_authoring._validation import ScoreError
from dancerudiments_authoring.bvh_import import (
    BVHLimits, BVHMotionChunk, compile_bvh, load_bvh, override_bvh_frame_time, parse_bvh,
)
from dancerudiments_authoring.motion import RigMotion


def fixture(rows, *, dt='0.1', channels=None, child=False, offset='1 2 3'):
    channels = channels or 'Xposition Yposition Zposition Zrotation Xrotation Yrotation'
    joint = '''JOINT Child
 {
  OFFSET 0 2 0
  CHANNELS 6 Xposition Yposition Zposition Yrotation Zrotation Xrotation
  End Site
  {
   OFFSET 0 1 0
  }
 }''' if child else 'End Site\n {\n  OFFSET 0 1 0\n }'
    return (f'HIERARCHY\nROOT Root\n{{\n OFFSET {offset}\n'
            f' CHANNELS {len(channels.split())} {channels}\n {joint}\n}}\nMOTION\n'
            f'Frames: {len(rows)}\nFrame Time: {dt}\n' +
            '\n'.join(' '.join(str(value) for value in row) for row in rows) + '\n')


def parse(text, **kwargs):
    return parse_bvh(text, source_id='synthetic', axis_forward='Y', axis_up='Z', **kwargs)


def rotation_matrix(axis, degrees):
    # Independent matrix formulation verifies all Euler orders, not the same
    # quaternion implementation a second time.
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    if axis == 'X':
        return np.array(((1, 0, 0), (0, c, -s), (0, s, c)))
    if axis == 'Y':
        return np.array(((c, 0, s), (0, 1, 0), (-s, 0, c)))
    return np.array(((c, -s, 0), (s, c, 0), (0, 0, 1)))


def quaternion_matrix(q):
    w, x, y, z = q
    return np.array(((1 - 2*(y*y + z*z), 2*(x*y - w*z), 2*(x*z + w*y)),
                     (2*(x*y + w*z), 1 - 2*(x*x + z*z), 2*(y*z - w*x)),
                     (2*(x*z - w*y), 2*(y*z + w*x), 1 - 2*(x*x + y*y))))


def world_joint_frames(clip, frame):
    rest = {b['name']: np.array(b['rest_matrix']).reshape(4, 4) for b in clip.profile.source['skeleton']}
    result = {}
    for joint in clip.joints:
        location, rotation = np.zeros(3), np.array((1., 0., 0., 0.))
        for channel, value in zip(clip.profile.channels, clip.frames[frame]):
            if channel.bone == joint.name:
                (location if channel.data_path == 'location' else rotation)[channel.array_index] = value
        parent = clip.joints[joint.parent].name if joint.parent is not None else None
        relative_rest = np.linalg.inv(rest[parent]) @ rest[joint.name] if parent else rest[joint.name]
        controls = np.eye(4)
        controls[:3, 3] = location
        controls[:3, :3] = quaternion_matrix(rotation)
        result[joint.name] = (result[parent] if parent else np.eye(4)) @ relative_rest @ controls
    return result


@unittest.skipIf(np is None, 'optional NumPy authoring dependency unavailable')
class BVHImportTests(unittest.TestCase):
    def test_hierarchy_offsets_translations_and_source_channels_are_preserved(self):
        rows = ((4, 5, 6, 90, 90, 0, 1, 2, 3, 30, 40, 50),
                (7, 8, 9, 0, 0, 0, 4, 5, 6, 0, 0, 0))
        clip = parse(fixture(rows, child=True), unit_scale=.01)
        self.assertEqual(clip.frame_time_seconds, Fraction(1, 10))
        self.assertEqual(clip.source_fps, 10.)
        np.testing.assert_array_equal(clip.source_frames, rows)
        self.assertEqual(clip.joints[1].parent, 0)
        self.assertEqual(clip.joints[1].end_sites, ((0., 1., 0.),))
        np.testing.assert_allclose(clip.frames[0, :3], (.04, .05, .06))
        np.testing.assert_allclose(clip.frames[0, 3:7], (.5, .5, .5, .5))
        np.testing.assert_allclose(clip.frames[0, 7:10], (.01, .02, .03))
        skeleton = clip.profile.source['skeleton']
        np.testing.assert_allclose(np.array(skeleton[0]['rest_matrix']).reshape(4, 4)[:3, 3], (.01, .02, .03))
        np.testing.assert_allclose(np.array(skeleton[1]['rest_matrix']).reshape(4, 4)[:3, 3], (.01, .04, .03))
        self.assertFalse(clip.frames.flags.writeable)
        self.assertFalse(clip.source_frames.flags.writeable)
        self.assertEqual(len(clip.profile.channels), 14)
        self.assertEqual(clip.profile.source['omitted_neutral_groups'], [
            {'bone': 'Root', 'data_path': 'scale', 'values': [1., 1., 1.]},
            {'bone': 'Child', 'data_path': 'scale', 'values': [1., 1., 1.]},
        ])

    def test_all_declared_euler_orders_match_independent_matrix_products(self):
        for order in itertools.permutations('XYZ'):
            with self.subTest(order=order):
                clip = parse(fixture(((31, -47, 83),),
                                     channels=' '.join(a + 'rotation' for a in order)))
                expected = np.eye(3)
                for axis, angle in zip(order, (31, -47, 83)):
                    expected = expected @ rotation_matrix(axis, angle)
                np.testing.assert_allclose(quaternion_matrix(clip.frames[0]), expected, atol=1e-14)

    def test_axis_conversion_is_proper_and_includes_offsets_and_local_motion(self):
        clip = parse_bvh(fixture(((1, 2, 3, 90, 0, 0),)), source_id='synthetic')
        # Source -Z forward/Y up -> Blender +Y forward/+Z up.
        np.testing.assert_allclose(clip.frames[0, :3], (1, -3, 2))
        source = clip.profile.source
        c = np.array(source['bvh']['source_to_blender']).reshape(3, 3)
        self.assertAlmostEqual(np.linalg.det(c), 1.)
        np.testing.assert_allclose(quaternion_matrix(clip.frames[0, 3:7]),
                                   c @ rotation_matrix('Z', 90) @ c.T, atol=1e-14)
        np.testing.assert_allclose(np.array(source['skeleton'][0]['rest_matrix']).reshape(4, 4)[:3, 3], (1, -3, 2))
        self.assertEqual(source['bvh']['unit_policy'], 'source-units-unverified')

    def test_profile_stable_across_values_duration_fps_and_filenames(self):
        a = parse(fixture(((0, 0, 0, 0, 0, 0),)), source_name='first.bvh')
        b = parse(fixture(((2000, -1000, 0, 20, 30, 40), (1, 2, 3, 4, 5, 6)), dt='.025'),
                  source_name='other.bvh')
        self.assertEqual(a.profile.fingerprint, b.profile.fingerprint)
        self.assertEqual(a.profile.type_uri, b.profile.type_uri)
        self.assertNotEqual(a.source_sha256, b.source_sha256)
        self.assertEqual(a.profile.source['transform_bounds']['location_range'], 10000.)
        self.assertNotIn('source_fps', a.profile.source)

    def test_profile_identity_canonicalises_linalg_roundoff(self):
        # The root display length is sqrt(14), so its raw binary result is not
        # exactly representable. Profile identity must not depend on tiny
        # BLAS/libm differences between otherwise identical CI runners.
        text = fixture(((0, 0, 0, 0, 0, 0),)).replace(
            'OFFSET 0 1 0', 'OFFSET 1 2 3')
        baseline = parse(text)
        original_norm = np.linalg.norm

        def perturbed_norm(value, *args, **kwargs):
            result = original_norm(value, *args, **kwargs)
            if np.asarray(value).ndim == 1 and np.isscalar(result):
                return float(result) + 1e-14
            return result

        with mock.patch.object(np.linalg, 'norm', side_effect=perturbed_norm):
            perturbed = parse(text)
        self.assertEqual(baseline.profile.type_uri, perturbed.profile.type_uri)
        self.assertEqual(baseline.profile.fingerprint, perturbed.profile.fingerprint)
        self.assertEqual(baseline.profile.source['skeleton'][0]['length'],
                         round(math.sqrt(14), 12))

    def test_absolute_position_convention_is_explicit_and_changes_profile(self):
        text = fixture(((1, 2, 3, 0, 0, 0, 0, 2, 0, 0, 0, 0),), child=True)
        additive = parse(text)
        absolute = parse(text, translation_convention='blender-absolute')
        np.testing.assert_array_equal(absolute.frames[0, :3], (0, 0, 0))
        np.testing.assert_array_equal(absolute.frames[0, 7:10], (0, 0, 0))
        self.assertNotEqual(additive.profile.fingerprint, absolute.profile.fingerprint)
        self.assertEqual(absolute.profile.source['bvh']['translation_convention'], 'blender-absolute')
        with self.assertRaises(ScoreError):
            parse(text, translation_convention='guess')

    def test_root_offset_normalization_is_lossless_and_profiles_share_origins(self):
        rows = ((4, 5, 6, 90, 90, 0, 1, 2, 3, 30, 40, 50),
                (-2, 8, 3, 120, -45, 80, -1, 4, -2, -60, 20, 45))
        text = fixture(rows, child=True)
        for convention in ('offset-plus-channel', 'blender-absolute'):
            retained = parse(text, translation_convention=convention)
            moved = parse(text, translation_convention=convention, root_offset_policy='motion')
            other_origin = parse(fixture(rows, child=True, offset='30 -40 50'),
                                 translation_convention=convention, root_offset_policy='motion')
            self.assertEqual(moved.profile.fingerprint, other_origin.profile.fingerprint)
            self.assertEqual(moved.metadata['original_root_offsets'], {'Root': [1., 2., 3.]})
            self.assertEqual(other_origin.metadata['original_root_offsets'], {'Root': [30., -40., 50.]})
            self.assertEqual(moved.joints[0].offset, (1., 2., 3.))
            self.assertEqual(moved.joints[1].offset, retained.joints[1].offset)
            for frame in range(len(rows)):
                a, b = world_joint_frames(retained, frame), world_joint_frames(moved, frame)
                for joint in a:
                    with self.subTest(convention=convention, frame=frame, joint=joint):
                        np.testing.assert_allclose(a[joint], b[joint], atol=1e-13)
        # A rotation-only root still needs its original origin represented.
        retained = parse(fixture(((45,),), channels='Zrotation'))
        moved = parse(fixture(((45,),), channels='Zrotation'), root_offset_policy='motion')
        self.assertEqual(len(retained.profile.channels), 4)
        self.assertEqual(len(moved.profile.channels), 7)
        np.testing.assert_allclose(world_joint_frames(retained, 0)['Root'],
                                   world_joint_frames(moved, 0)['Root'], atol=1e-13)

    def test_shortest_path_slerp_and_canonical_recording_compatibility(self):
        clip = parse(fixture(((170,), (-170,)), dt='1', channels='Zrotation'))
        chunk, = compile_bvh(clip, name='turn')
        self.assertEqual(chunk.samples.shape, (65, 4))
        middle = chunk.profile.decode(chunk.samples[32].tolist())
        np.testing.assert_allclose(quaternion_matrix(middle), rotation_matrix('Z', 180), atol=1e-11)
        np.testing.assert_allclose(np.linalg.norm(chunk.samples, axis=1), 1., atol=1e-11)
        motion = chunk.to_rig_motion()
        self.assertEqual(motion.to_dict(), chunk.to_dict())
        self.assertEqual(RigMotion.from_dict(chunk.to_dict()).to_dict(), chunk.to_dict())
        self.assertEqual(chunk.metadata['timing_mode'], 'time-only')
        self.assertIsNone(chunk.metadata['musical_bpm'])
        self.assertEqual(chunk.clock.bpm, 60.)
        self.assertEqual(chunk.clock.phase_status, 'unverified')

    def test_complete_valid_grid_and_contiguous_bounded_chunks(self):
        clip = parse(fixture(((0, 0, 0, 0, 0, 0), (1, 2, 3, 4, 5, 6), (2, 4, 6, 8, 10, 12))))
        full, = compile_bvh(clip, name='full')
        chunks = list(compile_bvh(clip, name='split', max_chunk_values=21))
        self.assertEqual([c.clock.start_pip for c in chunks], [0, 3, 6, 9, 12])
        self.assertEqual([len(c.samples) for c in chunks], [3, 3, 3, 3, 1])
        self.assertTrue(all(c.samples.size <= 21 for c in chunks))
        np.testing.assert_array_equal(np.vstack([c.samples for c in chunks]), full.samples)
        self.assertEqual(len(full.samples), 13)
        self.assertAlmostEqual(full.metadata['grid_tail_seconds'], .0125)
        self.assertEqual(full.metadata['source_time_range_seconds'], [0., .2])
        self.assertEqual(full.metadata['sampled_source_time_range_seconds'], [0., .1875])
        for index, chunk in enumerate(chunks):
            self.assertEqual(chunk.metadata['chunk_index'], index)
            self.assertEqual(chunk.metadata['chunk_count'], 5)
            self.assertEqual(chunk.metadata['original_clip_id'], clip.source_sha256)
            self.assertTrue(chunk.metadata['complete_action'])
            self.assertFalse(chunk.samples.flags.writeable)
        self.assertEqual(chunks[-1].to_recording_dict()['clock']['start_pip'], 12)

    def test_explicit_tempo_phase_preserves_prebeat_motion(self):
        clip = parse(fixture(((0,), (90,)), dt='1', channels='Zrotation'))
        chunks = list(compile_bvh(clip, name='phase', source_bpm=120,
                                  source_beat_zero_seconds=.1, max_chunk_values=128))
        self.assertEqual(chunks[0].clock.start_pip, -12)
        self.assertEqual(chunks[-1].clock.start_pip + len(chunks[-1].samples) - 1, 115)
        self.assertEqual(sum(len(c.samples) for c in chunks), 128)
        self.assertEqual(chunks[0].metadata['timing_mode'], 'tempo-and-phase')
        self.assertAlmostEqual(chunks[0].metadata['grid_head_seconds'], .00625)
        self.assertAlmostEqual(chunks[0].metadata['grid_tail_seconds'], .0015625)
        self.assertEqual(chunks[0].clock.phase_status, 'supplied')
        with self.assertRaises(ScoreError):
            list(compile_bvh(clip, name='invalid', source_beat_zero_seconds=.1))

    def test_single_frame_has_one_valid_default_pip(self):
        clip = parse(fixture(((0,),), channels='Yrotation'))
        chunk, = compile_bvh(clip, name='still')
        self.assertEqual(len(chunk.samples), 1)
        self.assertEqual(chunk.metadata['grid_tail_seconds'], 0.)
        with self.assertRaises(ScoreError):
            list(compile_bvh(clip, name='off_grid', source_bpm=120, source_beat_zero_seconds=.001))

    def test_explicit_frame_time_override_preserves_source_and_changes_full_grid(self):
        clip = parse(fixture(tuple((i,) for i in range(61)), dt='.0083333', channels='Zrotation'))
        corrected = override_bvh_frame_time(clip, frame_time_seconds='1/60',
            evidence={'source': 'Synthetic source declaration', 'declared_fps': 60})
        self.assertIs(corrected.frames, clip.frames)
        self.assertIs(corrected.source_frames, clip.source_frames)
        self.assertIs(corrected.profile, clip.profile)
        self.assertIs(corrected.joints, clip.joints)
        self.assertEqual(corrected.source_sha256, clip.source_sha256)
        self.assertEqual(corrected.frame_time_seconds, Fraction(1, 60))
        self.assertEqual(corrected.duration_seconds, 1.)
        self.assertEqual(corrected.metadata['source_fps'], 60.)
        self.assertEqual(corrected.metadata['source_frame_time_fraction'], '1/60')
        self.assertEqual(corrected.metadata['source_duration_seconds'], 1.)
        original = corrected.metadata['frame_time_override']['original_header']
        self.assertEqual(original['frame_time_fraction'], '83333/10000000')
        self.assertEqual(original['fps'], clip.source_fps)
        self.assertEqual(original['duration_seconds'], clip.duration_seconds)
        raw, = compile_bvh(clip, name='declared')
        fixed, = compile_bvh(corrected, name='corrected')
        self.assertEqual(len(raw.samples), 32)
        self.assertEqual(len(fixed.samples), 65)
        self.assertEqual(fixed.metadata['timing_mode'], 'time-only')
        self.assertEqual(fixed.metadata['original_clip_id'], clip.source_sha256)
        self.assertEqual(fixed.metadata['frame_time_override'], corrected.metadata['frame_time_override'])
        self.assertNotIn('frame_time_override', clip.metadata)

    def test_frame_time_override_rejects_invalid_or_evidenceless_corrections(self):
        clip = parse(fixture(((0,),), channels='Yrotation'))
        for interval in ('0', '-1/60', 'nan', '1/0', .0166667, True, Fraction(1, 10**100)):
            with self.subTest(interval=interval), self.assertRaises(ScoreError):
                override_bvh_frame_time(clip, frame_time_seconds=interval, evidence={'source': 'synthetic'})
        for evidence in ({}, None, [], 'source', {'fps': math.nan}):
            with self.subTest(evidence=evidence), self.assertRaises(ScoreError):
                override_bvh_frame_time(clip, frame_time_seconds=Fraction(1, 60), evidence=evidence)

    def test_repeated_frame_time_override_cannot_hide_original_header(self):
        clip = parse(fixture(((0,),), channels='Yrotation'))
        corrected = override_bvh_frame_time(clip, frame_time_seconds=Fraction(1, 60),
                                            evidence={'source': 'synthetic'})
        with self.assertRaisesRegex(ScoreError, 'already has'):
            override_bvh_frame_time(corrected, frame_time_seconds='1/30', evidence={'source': 'second'})

    def test_local_file_hash_and_original_bytes(self):
        text = fixture(((1, 2, 3, 4, 5, 6),))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'own.bvh'
            path.write_bytes(text.encode())
            clip = load_bvh(path, source_id='synthetic', axis_forward='Y', axis_up='Z')
        self.assertEqual(clip.source_sha256, parse(text).source_sha256)
        self.assertEqual(clip.metadata['source_bytes'], len(text))
        self.assertEqual(clip.metadata['source_name'], 'own.bvh')

    def test_limits_reject_before_large_motion_allocation(self):
        text = fixture(((0, 0, 0, 0, 0, 0),))
        for limits in (BVHLimits(max_file_bytes=8), BVHLimits(max_header_bytes=16),
                       BVHLimits(max_line_bytes=8), BVHLimits(max_channels=2),
                       BVHLimits(max_values=5), BVHLimits(max_values=6)):
            with self.subTest(limits=limits), self.assertRaises(ScoreError):
                parse(text, limits=limits)
        with self.assertRaises(ScoreError):
            parse(text.replace('Frames: 1', 'Frames: 2000000000'))
        with self.assertRaises(ScoreError):
            parse(fixture(((0,) * 12,), child=True), limits=BVHLimits(max_depth=1))
        with self.assertRaises(ScoreError):
            parse(fixture(((0,) * 12,), child=True), limits=BVHLimits(max_joints=1))

    def test_malformed_data_rejected_without_eval_or_partial_parse(self):
        text = fixture(((0, 0, 0, 0, 0, 0),))
        mutations = [
            text.replace('Frame Time: 0.1', 'Frame Time: 0'),
            text.replace('Frame Time: 0.1', 'Frame Time: 1e999'),
            text.replace('Frame Time: 0.1', 'Frame Time: nan'),
            text.replace('Frames: 1', 'Frames: 0'),
            text.replace('Xposition', 'Xunknown'),
            text.replace('Yposition', 'Xposition'),
            text.replace('0 0 0 0 0 0\n', '0 0 0 0 0\n'),
            text.replace('0 0 0 0 0 0\n', '0 0 0 0 0 0junk\n'),
            text.replace('0 0 0 0 0 0\n', '0 0 0 0 0 nan\n'),
            text.replace('0 0 0 0 0 0\n', '0 0 0 0 0 1e999\n'),
            text + '0 0 0 0 0 0\n',
            text.replace('MOTION\n', ''),
            fixture(((0,) * 12,), child=True).replace('JOINT Child', 'JOINT Root'),
        ]
        for bad in mutations:
            with self.subTest(bad=bad[-100:]), self.assertRaises(ScoreError):
                parse(bad)
        with self.assertRaises(ScoreError):
            parse_bvh(text, source_id='synthetic', axis_forward='Y', axis_up='-Y')
        with self.assertRaises(ScoreError):
            parse(fixture(((10001, 0, 0, 0, 0, 0),)))

    def test_chunk_validation_checks_normalisation_precision_and_quaternions(self):
        chunk, = compile_bvh(parse(fixture(((0,),), channels='Xrotation')), name='pose')
        for bad in ([[0., 0., 0., 0.]], [[1.1, 0., 0., 0.]], [[math.nan, 0., 0., 0.]],
                    [[1., 0.0000000000001, 0., 0.]], [[1., 0.]], [['bad']]):
            with self.subTest(bad=bad), self.assertRaises(ScoreError):
                BVHMotionChunk('bad', chunk.profile, bad, chunk.clock)
        with self.assertRaises(ScoreError):
            replace(chunk, metadata_json='{"bad":NaN}')
        with self.assertRaises(ScoreError):
            replace(chunk, metadata_json='[]')
        encoded = json.loads(json.dumps(chunk.to_dict(), allow_nan=False))
        self.assertEqual(RigMotion.from_dict(encoded).to_dict(), chunk.to_dict())


@unittest.skipIf(np is None or importlib.util.find_spec('bpy') is None,
                 'optional Blender runtime unavailable')
class BVHBlenderParityTests(unittest.TestCase):
    def test_original_and_native_replay_joint_frames_match(self):
        """Official importer vs portable carrier, including non-root positions."""
        import bpy
        from dancerudiments_authoring.blender_import import create_source_armature
        from dancerudiments_authoring.blender_bridge import apply_pose

        rows = ((0,) * 12,
                (4, 5, 6, 90, 90, 0, 1, 2, 3, 30, 40, 50),
                (-2, 8, 3, 120, -45, 80, -1, 4, -2, -60, 20, 45))
        text = fixture(rows, child=True, dt='.5')
        old_scene = bpy.context.window.scene
        scene = bpy.data.scenes.new('DanceRudiments BVH parity')
        bpy.context.window.scene = scene
        armatures_before = set(bpy.data.armatures)
        actions_before = set(bpy.data.actions)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'synthetic.bvh'
                path.write_text(text)
                bpy.ops.import_anim.bvh(filepath=str(path), axis_forward='-Z', axis_up='Y',
                    global_scale=.1, update_scene_fps=True, frame_start=1)
                original = bpy.context.object
                self.assertEqual(scene.render.fps / scene.render.fps_base, 2.)
                for policy in ('retain', 'motion'):
                    clip = parse_bvh(text, source_id='blender_parity', unit_scale=.1,
                                     translation_convention='blender-absolute', root_offset_policy=policy)
                    chunk, = compile_bvh(clip, name='parity')
                    player = chunk.to_rig_motion().player()
                    carrier = create_source_armature(clip.profile)
                    for frame_index in range(clip.frame_count):
                        scene.frame_set(frame_index + 1)
                        apply_pose(carrier, clip.profile, player.sample(frame_index * 32))
                        for joint in clip.joints:
                            source_pose = original.matrix_world @ original.pose.bones[joint.name].matrix
                            source_rest = original.matrix_world @ original.data.bones[joint.name].matrix_local
                            target_pose = carrier.matrix_world @ carrier.pose.bones[joint.name].matrix
                            target_rest = carrier.matrix_world @ carrier.data.bones[joint.name].matrix_local
                            with self.subTest(policy=policy, frame=frame_index, joint=joint.name):
                                np.testing.assert_allclose(source_pose.translation, target_pose.translation, atol=2e-5)
                                np.testing.assert_allclose(
                                    source_pose.to_3x3() @ source_rest.to_3x3().inverted(),
                                    target_pose.to_3x3() @ target_rest.to_3x3().inverted(), atol=2e-5)
        finally:
            for obj in list(scene.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.context.window.scene = old_scene
            bpy.data.scenes.remove(scene)
            for data in set(bpy.data.armatures) - armatures_before:
                bpy.data.armatures.remove(data)
            for action in set(bpy.data.actions) - actions_before:
                bpy.data.actions.remove(action)


if __name__ == '__main__':
    unittest.main()

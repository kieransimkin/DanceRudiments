"""Source-profile union is offline layout conversion, independent of bpy."""
import unittest

from dancerudiments_authoring._validation import ScoreError, canonical_json
from dancerudiments_authoring.blender_import import (
    SOURCE_ADAPTER, rebind_source_capture, union_source_profile,
)
from dancerudiments_authoring.motion_import import RigCapture
from dancerudiments_authoring.rigs import RigChannel, RigProfile, channel_name


def profile(path):
    defaults = {'location': (0., 0., 0.), 'rotation_quaternion': (1., 0., 0., 0.),
                'scale': (1., 1., 1.)}
    channels = []
    for index, neutral in enumerate(defaults[path]):
        number = index + 1
        bound = 1 if path == 'rotation_quaternion' else 10000
        channels.append(RigChannel(number, channel_name(number, 'Hips', path, index),
                                   'Hips', path, index, 'blender_unit' if path == 'location' else 'unitless',
                                   -bound, bound, neutral,
                                   interpolation='quaternion' if path == 'rotation_quaternion' else 'linear',
                                   rotation_mode='QUATERNION' if path == 'rotation_quaternion' else ''))
    source = dict(adapter=SOURCE_ADAPTER, scene_unit_scale_length=1.,
                  skeleton=[dict(name='Hips', parent=None, rest_matrix=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                                 length=1., use_deform=True)],
                  object_motion_root='Hips', neutral_tolerance=0.,
                  omitted_neutral_groups=[dict(bone='Hips', data_path=p, values=list(v))
                                          for p, v in defaults.items() if p != path])
    return RigProfile('syn://type/danceflow/motion/skeletal/source/test/skeleton_test',
                      'test', tuple(channels), source_json=canonical_json(source))


class SourceLayoutTests(unittest.TestCase):
    def test_union_keeps_first_ids_and_expands_only_declared_neutral_values(self):
        first, second = profile('location'), profile('rotation_quaternion')
        joined = union_source_profile((first, second))
        self.assertEqual(joined.channels[:3], first.channels)
        self.assertEqual(len(joined.channels), 7)
        self.assertEqual(joined.version, 2)
        position = RigCapture(first, (0., 1.), ((0., 0., 0.), (2., 0., 0.)))
        rotation = RigCapture(second, (0., 1.), ((1., 0., 0., 0.), (0., 0., 0., 1.)))
        moved, turned = rebind_source_capture(position, joined), rebind_source_capture(rotation, joined)
        self.assertEqual(moved.frames[-1], (2., 0., 0., 1., 0., 0., 0.))
        self.assertEqual(turned.frames[-1], (0., 0., 0., 0., 0., 0., 1.))
        self.assertEqual(moved.profile.fingerprint, turned.profile.fingerprint)
        self.assertEqual(moved.provenance['source_layout_rebound_from'], first.fingerprint)
        self.assertIs(union_source_profile((joined, first, second)), joined)

    def test_different_rest_basis_or_units_cannot_be_unioned(self):
        original = profile('location')
        document = profile('rotation_quaternion').to_dict()
        document['source']['skeleton'][0]['rest_matrix'][3] = 1
        with self.assertRaises(ScoreError):
            union_source_profile((original, RigProfile.from_dict(document)))
        document = profile('rotation_quaternion').to_dict()
        document['source']['scene_unit_scale_length'] = .01
        with self.assertRaises(ScoreError):
            union_source_profile((original, RigProfile.from_dict(document)))

    def test_rebind_cannot_drop_motion_or_invent_unknown_channels(self):
        position, rotation = profile('location'), profile('rotation_quaternion')
        joined = union_source_profile((position, rotation))
        capture = RigCapture(joined, (0.,), ((2., 0., 0., 1., 0., 0., 0.),))
        with self.assertRaises(ScoreError):
            rebind_source_capture(capture, position)
        document = position.to_dict()
        document['source']['omitted_neutral_groups'] = [g for g in document['source']['omitted_neutral_groups']
                                                      if g['data_path'] != 'rotation_quaternion']
        incomplete = RigCapture(RigProfile.from_dict(document), (0.,), ((0., 0., 0.),))
        with self.assertRaises(ScoreError):
            rebind_source_capture(incomplete, joined)


if __name__ == '__main__':
    unittest.main()

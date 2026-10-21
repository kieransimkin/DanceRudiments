import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from dancerudiments_authoring._validation import ScoreError
from dancerudiments_authoring.rigs import (
    RigChannel, RigProfile, canonical_type_uri, extend_profile, load_builtin_profile,
    load_profile, rigify_catalogue, rig_type_uri, write_profile,
)


def small_profile():
    channels = [RigChannel(1, 'root_x', 'root', 'location', 0, 'blender_unit', -10, 10, 0)]
    for axis, name in enumerate('wxyz'):
        channels.append(RigChannel(axis + 2, 'root_q' + name, 'root', 'rotation_quaternion', axis,
                                   'unitless', -1, 1, 1 if axis == 0 else 0,
                                   interpolation='quaternion', rotation_mode='QUATERNION'))
    channels.append(RigChannel(6, 'parent', 'root', '["parent"]', -1, 'unitless', 0, 7, 0,
                               value_type='integer', interpolation='step'))
    channels.append(RigChannel(7, 'enabled', 'root', '["enabled"]', -1, 'unitless', 0, 1, 0,
                               value_type='boolean', interpolation='step'))
    return RigProfile(rig_type_uri('test', kind='custom'), 'test', tuple(channels))


class RigProfileTests(unittest.TestCase):
    def test_real_blender_inventory_has_every_builtin_model_and_sample(self):
        catalogue = rigify_catalogue()
        self.assertEqual(catalogue['source']['blender_version'], '5.2.2')
        expected = {'Animals.bird': 1327, 'Animals.cat': 2379, 'Animals.horse': 1286,
                    'Animals.shark': 579, 'Animals.wolf': 2669, 'Basic.basic_human': 653,
                    'Basic.basic_quadruped': 799, 'human': 1967}
        self.assertEqual({entry['model']: entry['channel_count'] for entry in catalogue['metarigs']}, expected)
        self.assertEqual(len(catalogue['components']), 28)
        types = []
        for kind, entries in [('metarig', catalogue['metarigs']), ('component', catalogue['components'])]:
            for entry in entries:
                with self.subTest(model=entry['model']):
                    profile = load_builtin_profile(entry['model'], kind=kind)
                    self.assertEqual(profile.fingerprint, entry['sha256'])
                    self.assertEqual(len(profile.channels), entry['channel_count'])
                    self.assertEqual(profile.type_uri, entry['type_uri'])
                    self.assertEqual(profile, RigProfile.from_dict(profile.to_dict()))
                    self.assertEqual([channel.number for channel in profile.channels],
                                     list(range(1, entry['channel_count'] + 1)))
                    neutral = tuple(channel.neutral for channel in profile.channels)
                    decoded = profile.decode(profile.encode(neutral))
                    for actual, wanted in zip(decoded, neutral):
                        self.assertAlmostEqual(actual, wanted, places=8)
                    types.append(profile.type_uri)
        self.assertEqual(len(types), len(set(types)))
        glue = next(entry for entry in catalogue['components'] if entry['model'] == 'skin.glue')
        self.assertEqual(glue['status'], 'generated_with_context')
        self.assertEqual(glue['profile_context']['independent_glue_control_count'], 0)

    def test_type_alias_is_same_identity_and_fingerprint(self):
        profile = small_profile()
        alias = replace(profile, type_uri=profile.type_uri.replace('syn://', 'synny://'))
        self.assertEqual(profile, alias)
        self.assertEqual(profile.fingerprint, alias.fingerprint)
        human = load_builtin_profile('human')
        self.assertEqual(load_builtin_profile(human.type_uri.replace('syn://', 'synny://')), human)
        for invalid in ['dt:skill.definition', 'syn://type/a/../b', 'syn://type/A', 'http://example.com/type']:
            with self.assertRaises(ScoreError):
                canonical_type_uri(invalid)
        with self.assertRaises(ScoreError):
            load_builtin_profile('../../outside')

    def test_physical_units_ranges_and_discrete_quantization_roundtrip(self):
        profile = small_profile()
        for integer in range(8):
            for boolean in (False, True):
                physical = (2.5, 1, 0, 0, 0, integer, boolean)
                encoded = profile.encode(physical)
                decoded = profile.decode(encoded)
                self.assertEqual(decoded, physical)
                self.assertEqual(profile.encode(decoded), encoded)
        with self.assertRaises(ScoreError):
            profile.channels[5].decode(0.0)  # encoded midpoint = invalid selector 3.5
        for value in [10.001, float('nan'), float('inf'), True, 10**1000]:
            with self.assertRaises(ScoreError):
                profile.channels[0].encode(value)
        with self.assertRaises(ScoreError):
            replace(profile.channels[5], minimum=0, maximum=10**15)
        enum = replace(profile.channels[5], enum_items=((0, 'Off'), (7, 'Root')))
        self.assertEqual(enum.decode(enum.encode(7)), 7)
        with self.assertRaises(ScoreError):
            enum.encode(3)
        with self.assertRaises(ScoreError):
            enum.decode(profile.channels[5].encode(3))

    def test_quaternion_metadata_and_values_cannot_bypass_validation(self):
        profile = small_profile()
        neutral = (0, 1, 0, 0, 0, 0, 0)
        for quat in [(0, 0, 0, 0), (1, 1, 0, 0)]:
            with self.assertRaises(ScoreError):
                profile.encode((0, *quat, 0, 0))
        encoded = list(profile.encode(neutral))
        encoded[1] = 0
        with self.assertRaises(ScoreError):
            profile.decode(encoded)
        with self.assertRaises(ScoreError):
            replace(profile.channels[1], interpolation='linear')
        with self.assertRaises(ScoreError):
            replace(profile, channels=profile.channels[:4])
        with self.assertRaises(ScoreError):
            replace(profile.channels[1], rotation_mode='XYZ')

    def test_append_only_numbering_and_explicit_incompatible_changes(self):
        old = small_profile()
        self.assertEqual(extend_profile(old, old).fingerprint, old.fingerprint)
        new = RigChannel(1, 'earlier_sorted', 'aaa', 'location', 0, 'blender_unit', -1, 1, 0)
        observed = replace(old, channels=(new,) + tuple(replace(c, number=c.number + 1) for c in old.channels))
        evolved = extend_profile(old, observed)
        self.assertEqual(evolved.channels[:7], old.channels)
        self.assertEqual(evolved.channels[-1].binding, new.binding)
        self.assertEqual(evolved.channels[-1].number, 8)
        self.assertEqual(evolved.version, 2)
        self.assertNotEqual(evolved.fingerprint, old.fingerprint)
        with self.assertRaises(ScoreError):
            extend_profile(old, replace(old, channels=old.channels[:-1]))
        changed = replace(old, channels=(replace(old.channels[0], maximum=20),) + old.channels[1:])
        with self.assertRaises(ScoreError):
            extend_profile(old, changed)
        # Rest-pose metadata is fingerprinted even if channel names are identical.
        moved_rest = replace(old, source_json=json.dumps({'rest_basis': 'different'}))
        self.assertNotEqual(old.fingerprint, moved_rest.fingerprint)

    def test_profile_io_is_strict_and_refuses_accidental_replacement(self):
        profile = small_profile()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'rig.json'
            write_profile(path, profile)
            self.assertEqual(profile, load_profile(path))
            with self.assertRaises(FileExistsError):
                write_profile(path, profile)
            self.assertEqual(profile, load_profile(path))
        for key, value in [('schema_version', True), ('extra', 'oops'), ('channels', []), ('source', [])]:
            document = copy.deepcopy(profile.to_dict())
            document[key] = value
            with self.subTest(key=key), self.assertRaises(ScoreError):
                RigProfile.from_dict(document)


if __name__ == '__main__':
    unittest.main()

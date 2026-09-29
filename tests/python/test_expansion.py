"""Expansion data, precise rhythm structure and native default parity."""
import copy
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path
import random
import unittest

from dancerudiments_authoring import compile_pack
from dancerudiments_authoring.collections import expansion_pack, initial_pack
try:
    import dancerudiments as native
except ImportError:
    native = None

ROOT = Path(__file__).resolve().parents[2]

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class ExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs = module('expansion_definitions', 'collections/expansion/definitions.py')
        cls.score = cls.defs.document()
        cls.pack = expansion_pack()
        cls.by_name = {p.name: p for p in cls.pack.patterns}
        cls.scores = {p['name']: p for p in cls.score['patterns']}

    def test_exactly_eight_in_each_family(self):
        families = [p.provenance['family'] for p in self.pack.patterns]
        self.assertEqual(len(families), 24)
        self.assertEqual({f: families.count(f) for f in set(families)},
                         {'LFO II': 8, 'Geometry': 8, 'Interlock': 8})

    def test_generated_files_are_current(self):
        module('expansion_builder', 'tools/build_expansion_collection.py').build(check=True)

    def test_independent_recompilation_matches_every_sample(self):
        self.assertEqual(compile_pack(self.score).to_dict(), self.pack.to_dict())

    def test_closed_bounded_and_no_warnings(self):
        for p in self.pack.patterns:
            with self.subTest(pattern=p.name):
                self.assertEqual(p.diagnostics['warnings'], [])
                self.assertLessEqual(p.diagnostics['seam_position_error'], 1e-7)
                self.assertLess(p.diagnostics['max_step'], .25)
                self.assertEqual(p.diagnostics['normalization_scale'], 1)
                self.assertTrue(all(math.isfinite(x) and abs(x) <= 1 for row in p.samples for x in row))

    def test_all_original_and_documented(self):
        for p in self.pack.patterns:
            self.assertEqual(p.provenance['source_kind'], 'original')
            self.assertEqual(p.provenance['license'], 'MIT')
            self.assertEqual(p.provenance['collection_id'], 'expansion-02')
            self.assertEqual(p.provenance['beat_unit'], 'quarter_note')
            self.assertTrue(p.provenance['title'])

    def test_not_identical_to_any_existing_pattern(self):
        signatures = {tuple(p.samples) for p in initial_pack().patterns}
        # Compare equalised phase tables, so merely changing a period cannot pass.
        phase_signatures = {tuple(p.samples[(i*p.period_pips)//256] for i in range(256))
                            for p in initial_pack().patterns}
        for p in self.pack.patterns:
            self.assertNotIn(tuple(p.samples), signatures)
            phase = tuple(p.samples[(i*p.period_pips)//256] for i in range(256))
            self.assertNotIn(phase, phase_signatures)
            phase_signatures.add(phase)
            signatures.add(tuple(p.samples))

    def test_exact_polyrhythm_event_times(self):
        for name, count in [('rhythm_five_four', 5), ('rhythm_seven_four', 7)]:
            events = self.scores[name]['events']
            x = [Fraction(e['beat']) for e in events if e['gesture'] in ('left', 'right')]
            y = [Fraction(e['beat']) for e in events if e['gesture'] in ('up', 'down')]
            self.assertEqual(x, [Fraction(4*i, count) for i in range(2*count)])
            self.assertEqual(y, list(map(Fraction, range(8))))
            self.assertTrue(all(e['anchor'] == 'peak' for e in events))

    def test_euclidean_density_and_gap_balance(self):
        for pulses in (5, 7):
            events = self.scores[f'rhythm_euclid_{pulses}_16']['events']
            times = [Fraction(e['beat']) for e in events if Fraction(e['beat']) < 4]
            self.assertEqual(len(times), pulses)
            gaps = [(times[(i+1) % pulses]-times[i]) % 4 for i in range(pulses)]
            self.assertLessEqual(max(gaps)-min(gaps), Fraction(1, 4))

    def test_seven_eighths_preserves_its_period(self):
        p = self.by_name['rhythm_group_223']
        self.assertEqual(p.period_pips, 448)
        self.assertEqual(p.provenance['meter'], [7, 8])
        self.assertEqual([e['beat'] for e in self.scores[p.name]['events']],
                         ['0', '1', '2', '7/2', '9/2', '11/2'])

    def test_swung_offbeats_are_not_rounded(self):
        beats = [Fraction(e['beat']) for e in self.scores['rhythm_swung_answer']['events']]
        self.assertEqual(beats, [Fraction(i)+v for i in range(4) for v in (0, Fraction(2, 3))])

    def test_three_dimensional_patterns_retain_depth(self):
        for name in ('path_torus_knot', 'path_woven_3d', 'rhythm_three_four_five'):
            z = [v[2] for v in self.by_name[name].samples]
            self.assertGreater(max(z)-min(z), .5)

    def test_subset_loading_and_validation(self):
        p = expansion_pack(['path_torus_knot'])
        self.assertEqual([v.name for v in p.patterns], ['path_torus_knot'])
        for names in ([], ['missing'], ['path_torus_knot']*2, 'path_torus_knot'):
            with self.assertRaises(ValueError):
                expansion_pack(names)

    def test_selection_lock_rejects_tampering(self):
        builder = module('defaults_builder', 'tools/build_default_catalogue.py')
        lock = json.loads((ROOT/'collections/defaults.json').read_text())
        self.assertEqual(len(builder.selected_patterns(lock)), sum(len(s['patterns']) for s in lock['collections']))
        for mutation in ('digest', 'duplicate', 'unsafe', 'schema'):
            changed = copy.deepcopy(lock)
            if mutation == 'digest': changed['collections'][1]['pack_sha256'] = '0'*64
            elif mutation == 'duplicate': changed['collections'][1]['patterns'] *= 2
            elif mutation == 'unsafe': changed['collections'][1]['header'] = '../bad.hpp'
            else: changed['schema_version'] = 99
            with self.assertRaises(ValueError):
                builder.selected_patterns(changed)


@unittest.skipIf(native is None, 'Native extension unavailable')
class ExpansionNativeTests(unittest.TestCase):
    def test_every_sample_and_arbitrary_seek_is_cpp(self):
        names = [p['name'] for p in native.catalogue()]
        self.assertEqual(len(names), 1731)
        for p in expansion_pack().patterns:
            self.assertIn(p.name, names)
            for pip, expected in enumerate(p.samples):
                self.assertEqual(native.sample(p.name, pip).as_tuple(), expected)
                self.assertEqual(native.sample(p.name, pip-p.period_pips).as_tuple(), expected)
            order = list(range(p.period_pips))
            random.Random(6402).shuffle(order)
            for pip in order[:32]+[-2147483648, 2147483647]:
                self.assertEqual(native.sample(p.name, pip).as_tuple(), p.samples[pip % p.period_pips])

    def test_both_legacy_pack_loads_are_idempotent(self):
        for pack in (initial_pack(), expansion_pack()):
            bank = pack.to_native()
            self.assertEqual(bank.catalogue(), native.catalogue())
            for p in pack.patterns:
                self.assertEqual(bank.sample(p.name, -1).as_tuple(), p.samples[-1])

    def test_expansion_override_is_rejected(self):
        p = expansion_pack(['path_torus_knot']).patterns[0]
        rows = list(p.samples)
        rows[12] = (0, 0, 0)
        with self.assertRaisesRegex(ValueError, 'override'):
            native.PatternLibrary([native.SampledPattern(p.name, p.description, rows)])

@unittest.skipIf(native is None, 'Native extension unavailable')
class ReleaseSnapshotTests(unittest.TestCase):
    def test_native_snapshot_contains_both_collections(self):
        release = module('release_demo', 'tools/release_demo.py')
        rows = release.native_snapshot()
        self.assertEqual(len(rows), 1731)
        self.assertEqual([p['name'] for p in rows if p['provenance'].get('collection_id') == 'expansion-02'],
                         [p.name for p in expansion_pack().patterns])

    def test_stale_native_binary_is_rejected(self):
        from unittest.mock import patch
        release = module('release_demo', 'tools/release_demo.py')
        old_catalogue = native.catalogue()[:15]
        with patch.object(native, 'catalogue', return_value=old_catalogue):
            with self.assertRaisesRegex(ValueError, 'Native library is stale'):
                release.native_snapshot()

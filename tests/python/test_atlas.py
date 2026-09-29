"""Motion Atlas generation, rational events, closure, selection and native parity."""
from collections import Counter
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path
import unittest

from dancerudiments_authoring import compile_pack, load_pack
from dancerudiments_authoring._reproducibility import assert_rebuild_equal
from dancerudiments_authoring.collections import atlas_pack, expansion_pack, initial_pack
try:
    import dancerudiments as native
except ImportError:
    native=None
ROOT=Path(__file__).resolve().parents[2]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


class AtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs=module('atlas_definitions_test','collections/atlas/definitions.py')
        cls.builder=module('atlas_builder_test','tools/build_atlas_collection.py')
        cls.document=cls.defs.document()
        cls.scores={p['name']:p for p in cls.document['patterns']}
        cls.pack=atlas_pack()
        cls.by_name={p.name:p for p in cls.pack.patterns}

    def test_256_patterns_and_16_families(self):
        self.assertEqual(len(self.pack.patterns),256)
        self.assertEqual(set(Counter(p.provenance['family'] for p in self.pack.patterns).values()),{16})
        self.assertEqual(len(Counter(p.provenance['family'] for p in self.pack.patterns)),16)

    def test_reproducible_generation_and_documentation(self):
        self.builder.build(check=True)

    def test_score_interchange_recompiles_exactly(self):
        document=json.loads((ROOT/'collections/atlas/atlas.score.json').read_text())
        assert_rebuild_equal(self.document,document,"atlas.recipe")
        assert_rebuild_equal(compile_pack(document).to_dict(),self.pack.to_dict(),"atlas.compiled")

    def test_bounded_nonstationary_and_closed_without_clipping(self):
        for p in self.pack.patterns:
            with self.subTest(name=p.name):
                self.assertEqual(p.diagnostics['warnings'],[])
                self.assertEqual(p.diagnostics['bounds'],'reject')
                self.assertEqual(p.diagnostics['normalization_scale'],1)
                self.assertLess(p.diagnostics['seam_position_error'],1e-7)
                self.assertLess(p.diagnostics['max_step'],.25)
                self.assertGreater(max(math.dist(p.samples[0],r) for r in p.samples),.05)
                self.assertTrue(all(math.isfinite(x) and abs(x)<=1 for r in p.samples for x in r))

    def test_explicit_original_provenance(self):
        for p in self.pack.patterns:
            self.assertEqual(p.provenance['collection_id'],'atlas-03')
            self.assertEqual(p.provenance['source_kind'],'original')
            self.assertEqual(p.provenance['license'],'MIT')
            self.assertEqual(p.provenance['beat_unit'],'quarter_note')
            self.assertTrue(p.provenance['title'])

    def test_no_exact_phase_or_gain_duplicate_of_earlier_packs(self):
        previous=initial_pack().patterns+expansion_pack().patterns
        self.builder.audit(self.pack,previous)

    def test_duplicate_auditor_actually_rejects_a_copy(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            self.builder.audit(self.pack,self.pack.patterns)

    def test_source_functions_are_validated_before_cyclic_sampling(self):
        with self.assertRaisesRegex(ValueError,'not closed'):
            self.defs.function_score('bad','Bad','Test','Open',lambda p:(p,0,0))
        with self.assertRaisesRegex(ValueError,'Stationary'):
            self.defs.function_score('still','Still','Test','Stationary',lambda p:(0,0,0))

    def test_euclidean_gap_balance_and_meter(self):
        for p in self.pack.patterns:
            if p.provenance['family']!='Euclidean II':continue
            info=p.provenance['parameters'];steps=info['onset_steps'];n=info['steps'];k=info['pulses']
            self.assertEqual(len(steps),k)
            self.assertEqual(p.period_pips,n*32)
            gaps=[(steps[(j+1)%k]-steps[j])%n for j in range(k)]
            self.assertLessEqual(max(gaps)-min(gaps),1)

    def test_polyrhythm_events_are_rational_and_peak_anchored(self):
        for s in self.scores.values():
            if s['provenance']['family']!='Polyrhythms II':continue
            a,b=s['provenance']['parameters']['pulses']
            for lane,n in [('left',a),('right',b)]:
                self.assertEqual([Fraction(e['beat']) for e in s['events'] if e['gesture']==lane],
                                 [Fraction(8*i,n) for i in range(n)])
            self.assertTrue(all(e['anchor']=='peak' for e in s['events']))

    def test_additive_meters_are_not_forced_to_four_beats(self):
        for p in self.pack.patterns:
            if p.provenance['family']!='Additive meters':continue
            group=p.provenance['parameters']['eighth_note_groups']
            self.assertEqual(p.period_pips,sum(group)*32)
            self.assertEqual(len(self.scores[p.name]['events']),sum(group))

    def test_swing_offbeats_are_preserved_exactly(self):
        for ratio in ['3/5','2/3','5/7','3/4']:
            s=self.scores['swing_push_'+ratio.replace('/','_')]
            self.assertEqual([Fraction(e['beat']) for e in s['events'] if e['gesture']=='tap'],
                             [Fraction(i)+Fraction(ratio) for i in range(8)])

    def test_all_spatial_loops_have_real_depth(self):
        for p in self.pack.patterns:
            if p.provenance['family']=='Spatial loops':
                self.assertGreater(max(r[2] for r in p.samples)-min(r[2] for r in p.samples),.4)

    def test_randomness_is_repeatable_without_global_state(self):
        self.assertEqual(self.defs.noise_scores(),self.defs.noise_scores())
        self.assertNotEqual(self.defs.random_value(731,1),self.defs.random_value(731,2))

    def test_selection_validates_and_retains_catalogue_order(self):
        a,b=self.pack.patterns[0],self.pack.patterns[-1]
        self.assertEqual([p.name for p in atlas_pack([b.name,a.name]).patterns],[a.name,b.name])
        for names in ([],[a.name,a.name],['missing'],a.name):
            with self.assertRaises(ValueError):atlas_pack(names)

    def test_locked_selection_and_memory_budget(self):
        manifest=json.loads((ROOT/'collections/atlas/manifest.json').read_text())
        self.assertEqual(manifest['sample_count'],167040)
        lock=json.loads((ROOT/'collections/defaults.json').read_text())
        source=next(s for s in lock['collections'] if s['id']=='atlas-03')
        self.assertEqual(source['patterns'],[p.name for p in self.pack.patterns])
        self.assertEqual(source['pack_sha256'],manifest['pack_sha256'])
        self.assertLess(sum(p.period_pips for p in self.pack.patterns),1048576)


@unittest.skipIf(native is None,'Native extension unavailable')
class AtlasNativeTests(unittest.TestCase):
    def test_every_native_sample_matches_compiled_data(self):
        for p in atlas_pack().patterns:
            for i,row in enumerate(p.samples):
                self.assertEqual(native.sample(p.name,i).as_tuple(),row)
                self.assertEqual(native.sample(p.name,i-p.period_pips).as_tuple(),row)

    def test_int32_extremes_and_reverse_seek(self):
        for p in atlas_pack().patterns:
            for pip in [2147483647,-2147483648,100003,511,97,0,-1,-513]:
                self.assertEqual(native.sample(p.name,pip).as_tuple(),p.samples[pip%p.period_pips])

    def test_native_default_count_and_idempotent_reload(self):
        self.assertEqual(len(native.catalogue()),1731)
        self.assertEqual(atlas_pack().to_native().catalogue(),native.catalogue())

    def test_native_snapshot_includes_every_new_default(self):
        demo=module('atlas_native_demo','tools/release_demo.py')
        rows=demo.native_snapshot()
        self.assertEqual(len(rows),1731)
        self.assertEqual(sum(r['provenance'].get('collection_id')=='atlas-03' for r in rows),256)

    def test_no_new_phase_duplicate_of_original_15_native_motions(self):
        builder=module('atlas_native_audit','tools/build_atlas_collection.py')
        from types import SimpleNamespace
        previous=[SimpleNamespace(name=p['name'],samples=tuple(native.sample(p['name'],i).as_tuple()
            for i in range(p['period_pips']))) for p in native.catalogue()[:15]]
        builder.audit(atlas_pack(),previous)

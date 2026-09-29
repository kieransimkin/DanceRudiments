"""Continuum 04: source integrity, cyclic timing, generated registration and C++ parity."""
from collections import Counter
from fractions import Fraction as F
import importlib.util
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

from dancerudiments_authoring import compile_pack
from dancerudiments_authoring._reproducibility import assert_rebuild_equal
from dancerudiments_authoring.collections import continuum_pack, initial_pack, expansion_pack, atlas_pack
try:
    import dancerudiments as native
except ImportError:
    native=None
ROOT=Path(__file__).resolve().parents[2]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


class ContinuumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs=module('continuum_test_defs','collections/continuum/definitions.py')
        cls.builder=module('continuum_test_build','tools/build_continuum_collection.py')
        cls.pack=continuum_pack();cls.scores=cls.defs.document()
        cls.by_name={p.name:p for p in cls.pack.patterns}

    def test_320_presets_in_twenty_balanced_families(self):
        counts=Counter(p.provenance['family'] for p in self.pack.patterns)
        self.assertEqual(len(self.pack.patterns),320);self.assertEqual(len(counts),20)
        self.assertEqual(set(counts.values()),{16})

    def test_checked_in_outputs_reproduce(self):
        self.builder.build(check=True)

    def test_score_interchange_recompiles_exactly(self):
        score=json.loads((ROOT/'collections/continuum/continuum.score.json').read_text())
        assert_rebuild_equal(self.scores,score,"continuum.recipe")
        assert_rebuild_equal(compile_pack(score).to_dict(),self.pack.to_dict(),"continuum.compiled")

    def test_closed_bounded_nonstationary_no_clipping(self):
        for p in self.pack.patterns:
            with self.subTest(name=p.name):
                self.assertEqual(p.diagnostics['warnings'],[])
                self.assertEqual(p.diagnostics['bounds'],'reject')
                self.assertEqual(p.diagnostics['normalization_scale'],1)
                self.assertLess(p.diagnostics['seam_position_error'],1e-7)
                self.assertLess(p.diagnostics['max_step'],.22)
                self.assertGreater(max(math.dist(p.samples[0],r) for r in p.samples),.05)
                self.assertTrue(all(math.isfinite(x) and abs(x)<=1 for r in p.samples for x in r))

    def test_original_provenance_and_explicit_beat_unit(self):
        for p in self.pack.patterns:
            self.assertEqual(p.provenance['collection_id'],'continuum-04')
            self.assertEqual(p.provenance['source_kind'],'original')
            self.assertEqual(p.provenance['license'],'MIT')
            self.assertEqual(p.provenance['beat_unit'],'quarter_note')
            self.assertTrue(p.provenance['title']);self.assertTrue(p.provenance['parameters'])

    def test_duplicate_audit_against_all_previous_sampled_packs(self):
        self.builder.audit(self.pack,initial_pack().patterns+expansion_pack().patterns+atlas_pack().patterns)

    def test_duplicate_detector_rejects_a_copy(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.builder.audit(self.pack,self.pack.patterns)

    def test_source_lf_policy_preserves_hashes_on_windows_checkouts(self):
        self.assertIn('collections/continuum/** text eol=lf', (ROOT/'.gitattributes').read_text())

    def test_manifest_lock_payload_budget_and_names(self):
        m=json.loads((ROOT/'collections/continuum/manifest.json').read_text())
        lock=next(c for c in json.loads((ROOT/'collections/defaults.json').read_text())['collections'] if c['id']=='continuum-04')
        self.assertEqual(m['pattern_count'],320);self.assertEqual(m['sample_count'],252544)
        self.assertEqual(m['table_payload_bytes'],6061056)
        self.assertEqual(m['names'],[p.name for p in self.pack.patterns])
        self.assertEqual(lock['patterns'],m['names']);self.assertEqual(lock['pack_sha256'],m['pack_sha256'])
        self.assertLess(sum(p.period_pips for p in self.pack.patterns),1048576)

    def test_source_path_failures_are_not_hidden_by_looped_arrays(self):
        for fn,error in [(lambda p:(p,0,0),'Open'),(lambda p:(0,0,0),'Stationary'),
                         (lambda p:(float('nan'),0,0),'Invalid'),(lambda p:(1,2),'Invalid')]:
            with self.assertRaisesRegex(ValueError,error):
                self.defs.path_score('bad','Bad','Test','Invalid',fn)

    def test_source_period_and_per_pip_limits(self):
        with self.assertRaisesRegex(ValueError,'period'):
            self.defs.path_score('bad','Bad','Test','Bad',lambda p:(math.sin(math.tau*p),0,0),F(1,3))
        with self.assertRaisesRegex(ValueError,'too far'):
            self.defs.path_score('bad','Bad','Test','Bad',lambda p:(math.sin(250*math.tau*p),0,0))

    def test_every_function_recipe_records_oversampled_source_validation(self):
        function_patterns=[p for p in self.pack.patterns if p.provenance['parameters'].get('source_closed')]
        self.assertEqual(len(function_patterns),192)
        for p in function_patterns:
            self.assertEqual(p.provenance['parameters']['source_checks_per_cycle'],2*p.period_pips+1)
            self.assertLessEqual(max(abs(x) for row in p.samples for x in row),.820000000001)

    def test_source_circuit_validation(self):
        for points,weights in [([],None),([(0,0,0)]*3,[1,0,1]),([(0,0,0)]*3,[1,2])]:
            with self.assertRaises(ValueError):self.defs.circuit(points,weights)

    def test_periodic_cubic_velocity_across_unequal_seam(self):
        points=[(0,-1,0),(1,.2,.3),(-.3,.7,-.4),(-.8,0,.2)]
        fn=self.defs.circuit(points,[1,2,3,4],cubic=True)
        e=1e-7
        for j in range(3):
            a=(fn(e)[j]-fn(0)[j])/e;b=(fn(1)[j]-fn(1-e)[j])/e
            self.assertAlmostEqual(a,b,places=4)
        self.assertEqual(fn(0),fn(1))

    def test_dwell_phrases_really_hold_positions(self):
        for p in self.pack.patterns:
            if p.provenance['family']=='Dwell phrases':
                self.assertGreater(sum(a==b for a,b in zip(p.samples,p.samples[1:])),50)

    def test_spatial_families_have_nonzero_depth(self):
        for p in self.pack.patterns:
            if p.provenance['family'] in ('Surface travels','Braided loops','Ribbon sweeps'):
                self.assertGreater(max(v[2] for v in p.samples)-min(v[2] for v in p.samples),.04)

    def test_events_are_exact_ordered_and_explicitly_peak_anchored(self):
        event_scores=[s for s in self.scores['patterns'] if s['events']]
        self.assertEqual(len(event_scores),128)
        for s in event_scores:
            times=[F(e['beat']) for e in s['events']]
            self.assertEqual(times,sorted(times))
            self.assertTrue(all(0<=t<F(s['period_beats']) for t in times))
            self.assertTrue(all(e['anchor']=='peak' for e in s['events']))

    def test_ladders_have_the_declared_subdivision_counts(self):
        for s in self.defs.ladder_scores():
            counts=s['provenance']['parameters']['pulses_per_region']
            for region,n in enumerate(counts):
                times=[F(e['beat']) for e in s['events'] if 2*region<=F(e['beat'])<2*(region+1)]
                self.assertEqual(times,[2*region+F(2*j,n) for j in range(n)])

    def test_meter_dialogues_keep_fractional_periods(self):
        for s in self.defs.meter_scores():
            groups=s['provenance']['parameters']['eighth_note_groups']
            self.assertEqual(F(s['period_beats']),F(sum(groups),2))
            self.assertEqual(self.by_name[s['name']].period_pips,sum(groups)*32)
        self.assertTrue(any(F(s['period_beats']).denominator==2 for s in self.defs.meter_scores()))

    def test_migrating_accents_retain_even_pulse_grid(self):
        for s in self.defs.migration_scores():
            params=s['provenance']['parameters'];n=params['pulses_per_bar'];stride=params['accent_stride']
            for bar in range(4):
                ev=[e for e in s['events'] if e['gesture'] in ('left','right') and 4*bar<=F(e['beat'])<4*(bar+1)]
                self.assertEqual([F(e['beat']) for e in ev],[4*bar+F(4*j,n) for j in range(n)])
                self.assertEqual([i for i,e in enumerate(ev) if e['strength']==.95],
                                 [j for j in range(n) if (j-bar*stride)%n in (0,2)])

    def test_echo_timing_is_rational_not_repeatedly_rounded(self):
        for s in self.defs.echo_scores():
            times=s['provenance']['parameters']['echo_times']
            for t in times:self.assertIn(F(t),[F(e['beat']) for e in s['events']])
        self.assertTrue(any(F(e['beat']).denominator%3==0 for s in self.defs.echo_scores() for e in s['events']))

    def test_subset_selection_preserves_source_order_and_rejects_invalid_names(self):
        a,b=self.pack.patterns[0],self.pack.patterns[-1]
        self.assertEqual([p.name for p in continuum_pack([b.name,a.name]).patterns],[a.name,b.name])
        for names in ([],[a.name,a.name],['missing'],a.name):
            with self.assertRaises(ValueError):continuum_pack(names)

    def test_registration_lookup_index_is_a_sorted_permutation(self):
        builder=module('continuum_registry','tools/build_default_catalogue.py')
        patterns=builder.selected_patterns(json.loads((ROOT/'collections/defaults.json').read_text()))
        cpp=(ROOT/'include/dancerudiments/detail/default_registry.inc').read_text()
        values=re.search(r'default_lookup_indices\{\{(.*?)\}\}',cpp,re.S).group(1)
        indices=list(map(int,re.findall(r'\d+',values)))
        self.assertEqual(sorted(indices),list(range(len(patterns))))
        names=[patterns[i][0].name for i in indices]
        self.assertEqual(names,sorted(names));self.assertEqual(len(names),len(set(names)))
        self.assertEqual(len(patterns),1716)


@unittest.skipIf(native is None,'Native extension unavailable')
class ContinuumNativeTests(unittest.TestCase):
    def test_all_new_native_samples_and_negative_positions(self):
        for p in continuum_pack().patterns:
            for i,row in enumerate(p.samples):
                self.assertEqual(native.sample(p.name,i).as_tuple(),row)
                self.assertEqual(native.sample(p.name,i-p.period_pips).as_tuple(),row)

    def test_extreme_pips_and_random_access(self):
        for p in continuum_pack().patterns:
            for pip in [-2147483648,2147483647,1000003,-17,511,0,9,-1]:
                self.assertEqual(native.sample(p.name,pip).as_tuple(),p.samples[pip%p.period_pips])

    def test_default_order_is_append_only(self):
        entries=native.catalogue();self.assertEqual(len(entries),1731)
        expected=initial_pack().patterns+expansion_pack().patterns+atlas_pack().patterns+continuum_pack().patterns
        self.assertEqual([p['name'] for p in entries[15:15+len(expected)]],[p.name for p in expected])

    def test_exact_pack_reload_is_idempotent(self):
        self.assertEqual(continuum_pack().to_native().catalogue(),native.catalogue())

    def test_lookup_rejects_unknown_names_near_sort_boundaries(self):
        for name in ['', 'a', 'zzzzzz', 'ribbon_1_2', 'ribbon_1_2_slim_', 'surface_3_5_wideX', 'canon_00_close']:
            with self.assertRaises(ValueError):native.sample(name,0)

    def test_no_phase_copy_of_original_fifteen_core_motions(self):
        builder=module('continuum_native_audit','tools/build_continuum_collection.py')
        core=[SimpleNamespace(name=p['name'],samples=tuple(native.sample(p['name'],i).as_tuple()
               for i in range(p['period_pips']))) for p in native.catalogue()[:15]]
        builder.audit(continuum_pack(),core)

    def test_release_snapshot_contains_every_default(self):
        demo=module('continuum_demo','tools/release_demo.py');rows=demo.native_snapshot()
        self.assertEqual(len(rows),1731)
        self.assertEqual(sum(p['provenance'].get('collection_id')=='continuum-04' for p in rows),320)

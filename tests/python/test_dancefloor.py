"""Coverage, source timing, deterministic baking and real C++ sample regression."""
from fractions import Fraction as F
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path
import unittest
from dancerudiments_authoring.collections import club_pack, dancefloor_pack
from dancerudiments_authoring._validation import MAX_PACK_SAMPLES, MAX_PATTERNS
try:
    import dancerudiments as native
except ImportError:
    native=None
ROOT=Path(__file__).resolve().parents[2]

class DancefloorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('test_dancefloor_defs',ROOT/'collections/dancefloor/definitions.py')
        cls.defs=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.defs)
        cls.data=json.loads((ROOT/'collections/dancefloor/rhythms.json').read_text())
        cls.rhythms={r['id']:r for r in cls.data['rhythms']}
        cls.pack=dancefloor_pack();cls.old=club_pack()
        cls.manifest=json.loads((ROOT/'collections/dancefloor/manifest.json').read_text())
    def times(self,r,lane):return [F(e['beat']) for e in self.rhythms[r]['events'] if e['lane']==lane]
    def test_counts(self):
        self.assertEqual(len(self.rhythms),68);self.assertEqual(len(self.pack.patterns),944)
        self.assertEqual(len(self.defs.new_rhythms()),32)
    def test_full_cartesian_coverage(self):
        names={p.name for p in self.pack.patterns+self.old.patterns}
        self.assertEqual(names,{'beat_'+r+'_'+m for r in self.rhythms for m in self.defs.MAPPINGS})
        self.assertEqual(len(names),1088)
    def test_retained_rhythm_documents_exact(self):
        old=json.loads((ROOT/'collections/club/rhythms.json').read_text())['rhythms']
        self.assertEqual(self.data['rhythms'][:36],old)
        self.assertEqual(sha256((ROOT/'collections/club/rhythms.json').read_bytes()).hexdigest(),self.manifest['club_rhythms_sha256'])
    def test_jersey_five_is_straight_grid(self):
        self.assertEqual(self.times('jersey_five','kick'),[F(i,4) for i in (0,4,8,11,14,16,20,24,27,30)])
        self.assertTrue(all((t*4).denominator==1 for t in self.times('jersey_five','kick')))
    def test_clave_sides_and_duration(self):
        self.assertEqual(self.times('son_clave_32','rim'),[F(0),F(3,2),F(3),F(5),F(6)])
        self.assertEqual(self.times('son_clave_23','rim'),[F(1),F(2),F(4),F(11,2),F(7)])
        self.assertEqual(self.rhythms['son_clave_32']['period_beats'],'8')
    def test_clave_reversal_is_four_beats(self):
        self.assertEqual(sorted((t+4)%8 for t in self.times('son_clave_32','rim')),self.times('son_clave_23','rim'))
    def test_reggae_foundations(self):
        self.assertEqual(self.times('reggae_one_drop','kick'),[F(2),F(6)])
        self.assertEqual(self.times('reggae_one_drop','rim'),[F(2),F(6)])
        self.assertEqual(self.times('reggae_steppers','kick'),[F(i) for i in range(8)])
        self.assertEqual(self.times('reggae_rockers','kick'),[F(i) for i in (0,2,4,6)])
    def test_rolling_bass_is_not_triplets(self):
        self.assertEqual(self.times('psy_rolling','bass'),[F(i,4) for i in range(32) if i%4])
        self.assertTrue(all((t*4).denominator==1 for t in self.times('psy_rolling','bass')))
    def test_true_fractional_footwork_and_afro_cross(self):
        self.assertTrue(any(t.denominator==3 for t in self.times('footwork_triplet','bass')))
        self.assertEqual(self.times('afro_cross','tom'),[F(i*4,3) for i in range(6)])
    def test_swing_keeps_low_drum_positions(self):
        self.assertEqual(self.times('ukg_rim_shuffle','kick'),[F(i,4) for i in (0,10,16,23,26)])
        self.assertIn(F(5,16),self.times('ukg_rim_shuffle','rim'))
        self.assertNotIn(F(1,4),self.times('ukg_rim_shuffle','rim'))
    def test_events_valid_unique(self):
        for r in self.rhythms.values():
            self.assertEqual(len(r['events']),len({(e['lane'],F(e['beat'])) for e in r['events']}))
            self.assertTrue(all(0<=F(e['beat'])<F(r['period_beats']) and 0<e['velocity']<=1 for e in r['events']))
    def test_sources_scope_and_references(self):
        for r in self.rhythms.values():
            self.assertTrue(r['reference_ids'])
            for key in r['reference_ids']:
                self.assertTrue(self.data['sources'][key]['supports'])
                self.assertTrue(self.data['sources'][key]['url'].startswith('https://'))
    def test_samples_bounded_finite_nonconstant(self):
        for p in self.pack.patterns:
            self.assertEqual(len(p.samples),p.period_pips)
            self.assertTrue(all(math.isfinite(v) and abs(v)<=.920000000001 for row in p.samples for v in row))
            self.assertGreater(len(set(p.samples)),8)
            self.assertLessEqual(max(math.dist(p.samples[i-1],p.samples[i]) for i in range(p.period_pips)),.35)
    def test_no_exact_duplicate_arrays(self):
        hashes=[sha256(repr(p.samples).encode()).hexdigest() for p in self.pack.patterns+self.old.patterns]
        self.assertEqual(len(hashes),len(set(hashes)))
    def test_bpm_does_not_change_movement(self):
        r=dict(self.rhythms['jersey_five']);a=self.defs._new_tables(r);r['bpm']=80
        self.assertEqual(a,self.defs._new_tables(r))
    def test_missing_lane_fallback_is_declared(self):
        for p in self.pack.patterns:
            if p.provenance['rhythm_id']=='four_floor':self.assertEqual(len(p.provenance['missing_lane_fallbacks']),3)
    def test_causal_kernel_is_at_rest_before_event(self):
        r=self.defs.make('fixture','Fixture','Test',120,1,{'kick':[8]})
        _,_,spring,_=self.defs._kernel_fields(r)
        self.assertTrue(all(all(v==0 for v in axis[:129]) for axis in spring))
        self.assertTrue(any(any(v!=0 for v in axis[129:170]) for axis in spring))
    def test_complete_spring_mapping_has_no_anticipatory_bed(self):
        r=self.defs.make('fixture','Fixture','Test',120,1,{'kick':[8]})
        samples=self.defs._new_tables(r)[0]['spring']
        self.assertTrue(all(row==(0.0,0.0,0.0) for row in samples[:129]))
        self.assertTrue(any(any(v!=0 for v in row) for row in samples[129:170]))
    def test_kernel_tail_wraps_and_is_seek_independent(self):
        r=self.defs.make('fixture','Fixture','Test',120,1,{'kick':[F(63,4)]})
        fields,_,_,_=self.defs._kernel_fields(r)
        self.assertGreater(fields['kick'][0],0)
        self.assertEqual(fields,self.defs._kernel_fields(r)[0])
    def test_gain_of_kernel_is_linear(self):
        a=self.defs.make('a','A','Test',120,1,{'kick':[(4,1)]})
        b=self.defs.make('b','B','Test',120,1,{'kick':[(4,.5)]})
        fa=self.defs._kernel_fields(a)[0]['kick'];fb=self.defs._kernel_fields(b)[0]['kick']
        self.assertEqual(fa,[x*2 for x in fb])
    def test_anchors_distinguish_causal_motion(self):
        for p in self.pack.patterns:
            anchor=p.provenance['event_anchor']
            if p.name.endswith('_spring'):self.assertIn('causal',anchor)
            if p.name.endswith('_pendulum'):self.assertEqual(anchor,'phase modulation')
    def test_recipe_hashes_and_pack_hash(self):
        recipes=json.loads((ROOT/'collections/dancefloor/recipes.json').read_text())
        self.assertEqual({x['name']:x['source_sha256'] for x in recipes['patterns']},{p.name:p.source_sha256 for p in self.pack.patterns})
        canonical=json.dumps(self.pack.to_dict(),sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
        self.assertEqual(sha256(canonical.encode()).hexdigest(),self.manifest['pack_sha256'])
    def test_limits_are_not_relaxed_for_user_packs(self):
        self.assertEqual(MAX_PATTERNS,1024);self.assertEqual(MAX_PACK_SAMPLES,1048576)
        self.assertLess(sum(p.period_pips for p in self.pack.patterns),MAX_PACK_SAMPLES)
    def test_subset_api(self):
        name='beat_amen_four_bar_spring'
        self.assertEqual([p.name for p in dancefloor_pack([name]).patterns],[name])
        with self.assertRaises(ValueError):dancefloor_pack(['missing'])
        with self.assertRaises(ValueError):dancefloor_pack([])
    @unittest.skipIf(native is None,'native extension not built')
    def test_native_all_samples_extremes_and_order(self):
        self.assertEqual(len(native.catalogue()),1731)
        self.assertEqual([p['name'] for p in native.catalogue()[787:]],[p.name for p in self.pack.patterns])
        for p in self.pack.patterns:
            for i,row in enumerate(p.samples):self.assertEqual(native.sample(p.name,i).as_tuple(),row)
            for i in (2147483647,-2147483648,-1,0,p.period_pips):
                self.assertEqual(native.sample(p.name,i).as_tuple(),p.samples[i%p.period_pips])
    @unittest.skipIf(native is None,'native extension not built')
    def test_legacy_load_is_idempotent(self):
        self.assertEqual(len(dancefloor_pack(['beat_amen_four_bar_spring']).to_native().catalogue()),1731)

if __name__=='__main__':unittest.main()

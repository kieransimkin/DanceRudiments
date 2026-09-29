"""Musical landmarks, exact fractional timing and native movement registration."""
from fractions import Fraction as F
import importlib.util
import json
import math
from pathlib import Path
import unittest
from dancerudiments_authoring import compile_pack
from dancerudiments_authoring.collections import club_pack
try:
    import dancerudiments as native
except ImportError:
    native=None
ROOT=Path(__file__).resolve().parents[2]
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

class ClubRhythmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs=module('collections/club/definitions.py','club_test_definitions')
        cls.rhythms={r['id']:r for r in cls.defs.rhythm_scores()};cls.pack=club_pack()
    def times(self,name,lane):return [F(e['beat']) for e in self.rhythms[name]['events'] if e['lane']==lane]
    def test_counts(self):
        self.assertEqual(len(self.rhythms),36);self.assertEqual(len(self.pack.patterns),144)
        for r in self.rhythms:
            self.assertEqual({p.provenance['mapping'] for p in self.pack.patterns if p.provenance['rhythm_id']==r},set(self.defs.MAPPINGS))
    def test_four_floor_quarters(self):self.assertEqual(self.times('four_floor','kick'),[F(0),F(1),F(2),F(3)])
    def test_house_backbeats(self):self.assertEqual(self.times('house_classic','clap'),[F(1),F(3),F(5),F(7)])
    def test_ukg_two_step(self):
        self.assertEqual(self.times('ukg_two_step','kick'),[F(0),F(5,2),F(4),F(13,2)])
        self.assertEqual(self.times('ukg_two_step','snare'),[F(1),F(3),F(5),F(7)])
    def test_swing_only_selected_lanes(self):
        self.assertEqual(self.times('house_shuffle','kick'),[F(i) for i in range(8)])
        hats=self.times('house_shuffle','hat');self.assertIn(F(3,10),hats);self.assertNotIn(F(1,4),hats)
    def test_amen_four_bars_and_repeated_opening(self):
        r=self.rhythms['amen_four_bar'];self.assertEqual(r['period_beats'],'16')
        first=[(F(e['beat']),e['lane'],e['velocity']) for e in r['events'] if F(e['beat'])<4]
        second=[(F(e['beat'])-4,e['lane'],e['velocity']) for e in r['events'] if 4<=F(e['beat'])<8]
        self.assertEqual(first,second)
    def test_amen_displaced_closers_and_crash(self):
        sn=self.times('amen_four_bar','snare');self.assertIn(F(23,2),sn);self.assertIn(F(31,2),sn)
        self.assertNotIn(F(11),sn);self.assertNotIn(F(15),sn)
        self.assertEqual(self.times('amen_four_bar','crash'),[F(29,2)])
    def test_amen_no_ghost_comparison(self):
        full=self.rhythms['amen_four_bar']['events'];reduced=self.rhythms['amen_no_ghosts']['events']
        self.assertEqual(reduced,[e for e in full if e['lane']!='snare' or e['velocity']>=.8])
    def test_drill_grouping_is_not_triplets(self):
        r=self.rhythms['drill_tresillo'];hats=[b for b in self.times(r['id'],'hat') if b<4]
        self.assertEqual(hats,[F(i,4) for i in [0,3,6,8,11,14]])
        self.assertTrue(all((t*4).denominator==1 for t in hats))
    def test_drill_snare_moves(self):self.assertEqual(self.times('drill_displaced','snare'),[F(2),F(7)])
    def test_actual_triplet_fill_is_rational(self):self.assertTrue(any(F(e['beat']).denominator%3==0 for e in self.rhythms['drill_rolls']['events']))
    def test_three_step_cycle_closes_after_three_bars(self):
        self.assertEqual(self.rhythms['techno_polymeter']['period_beats'],'12')
        self.assertEqual(self.times('techno_polymeter','rim'),[F(i,4) for i in range(0,48,3)])
    def test_dembow_offbeat_answers(self):self.assertEqual(self.times('dembow','snare'),[F(i,4) for i in [3,6,11,14,19,22,27,30]])
    def test_events_valid_and_no_duplicate_lane_onsets(self):
        for r in self.rhythms.values():
            events=r['events'];self.assertEqual(len(events),len({(e['beat'],e['lane']) for e in events}))
            self.assertTrue(all(0<=F(e['beat'])<F(r['period_beats']) and 0<e['velocity']<=1 for e in events))
            self.assertEqual(r['beat_unit'],'quarter_note')
    def test_scores_recompile(self):
        score=json.loads((ROOT/'collections/club/club.score.json').read_text())
        self.assertEqual(compile_pack(score).to_dict(),self.pack.to_dict())
    def test_regeneration(self):module('tools/build_club_collection.py','club_test_builder').build(check=True)
    def test_envelope_peak_and_edges(self):
        self.assertEqual(self.defs.envelope(0,.1,.4),1)
        for t in [-.1,.4,-10,10]:self.assertAlmostEqual(self.defs.envelope(t,.1,.4),0)
    def test_bpm_metadata_does_not_change_samples(self):
        r=dict(self.rhythms['four_floor']);a=self.defs.bake_motion(r,'bounce');r['bpm']=200
        self.assertEqual(self.defs.bake_motion(r,'bounce'),a)
    def test_bounds_and_exact_duplicate_arrays(self):
        tables=set()
        for p in self.pack.patterns:
            self.assertLess(p.diagnostics['max_step'],.35);self.assertLess(p.diagnostics['seam_position_error'],1e-6)
            self.assertTrue(all(math.isfinite(v) and abs(v)<=.9 for row in p.samples for v in row))
            self.assertNotIn(p.samples,tables);tables.add(p.samples)
    def test_provenance_references(self):
        for p in self.pack.patterns:
            self.assertEqual(p.provenance['collection_id'],'club-05');self.assertEqual(p.provenance['beat_unit'],'quarter_note')
            self.assertTrue(p.provenance['reference_urls']);self.assertTrue(p.provenance['event_markers'])
    def test_named_subset(self):
        selected=club_pack(['beat_amen_four_bar_bounce']);self.assertEqual(len(selected.patterns),1)
        with self.assertRaises(ValueError):club_pack(['missing'])
    @unittest.skipIf(native is None,'native extension not available')
    def test_all_new_native_samples_and_extremes(self):
        self.assertEqual(len(native.catalogue()),787)
        self.assertEqual([p['name'] for p in native.catalogue()[-144:]],[p.name for p in self.pack.patterns])
        for p in self.pack.patterns:
            for i,row in enumerate(p.samples):self.assertEqual(native.sample(p.name,i).as_tuple(),row)
            for i in [-2147483648,-1,p.period_pips,2147483647]:self.assertEqual(native.sample(p.name,i).as_tuple(),p.samples[i%p.period_pips])
    @unittest.skipIf(native is None,'native extension not available')
    def test_legacy_loader_idempotent(self):self.assertEqual(len(club_pack(['beat_four_floor_bounce']).to_native().catalogue()),787)

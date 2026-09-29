"""Beat coverage tests; no native extension or curve regeneration required."""
import json
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from harness_beats import collect, canonical, CORE_STROKES


class HarnessBeatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library=collect(ROOT)
        cls.beats={b['id']:b for b in cls.library['beats']}

    def test_all_dance_rhythms_present_without_duplicate_shared_scores(self):
        source=json.loads((ROOT/'collections/dancefloor/rhythms.json').read_text())
        self.assertEqual(len([b for b in self.beats.values() if b['kind']=='dance']),len(source['rhythms']))
        for b in source['rhythms']:
            candidate=self.beats[b['id']]
            self.assertEqual(Fraction(candidate['period_beats']),Fraction(b['period_beats']))
            self.assertEqual(sorted((Fraction(e['beat']),e['lane'],e['velocity']) for e in b['events']),
                             sorted((Fraction(e['beat']),e['lane'],e['velocity']) for e in candidate['events']))

    def test_complete_amen_and_no_ghost_comparison(self):
        amen=self.beats['amen_four_bar']
        self.assertEqual(Fraction(amen['period_beats']),16)
        self.assertEqual(len(amen['events']),81)
        self.assertTrue(any(e['lane']=='crash' for e in amen['events']))
        self.assertLess(len(self.beats['amen_no_ghosts']['events']),len(amen['events']))

    def test_four_floor_quarters(self):
        self.assertEqual([Fraction(e['beat']) for e in self.beats['four_floor']['events']],[0,1,2,3])
        self.assertTrue(all(e['note']==36 and e['channel']==9 for e in self.beats['four_floor']['events']))

    def test_event_scores_are_not_silently_omitted(self):
        linked=self.library['pattern_beats']
        count=0
        for path in (ROOT/'collections').glob('*/*.score.json'):
            for p in json.loads(path.read_text())['patterns']:
                if p.get('events'):
                    self.assertIn(p['name'],linked)
                    beat=self.beats[linked[p['name']]]
                    self.assertEqual(len(p['events']),len(beat['events']))
                    self.assertEqual(sorted(Fraction(e['beat'])%Fraction(p['period_beats']) for e in p['events']),
                                     sorted(Fraction(e['beat']) for e in beat['events']))
                    count+=1
        self.assertGreaterEqual(count,230)

    def test_core_stickings_extracted_and_linked(self):
        for name in CORE_STROKES:
            beat=self.beats[self.library['pattern_beats'][name]]
            self.assertEqual(beat['kind'],'core');self.assertTrue(beat['events'])
            self.assertIn('AFTER',beat['notes'])

    def test_exactly_all_beat_derived_movements_are_linked(self):
        count=0
        for path in (ROOT/'python/dancerudiments_authoring/packs').glob('*.json'):
            for p in json.loads(path.read_text())['patterns']:
                rid=p.get('provenance',{}).get('rhythm_id')
                if rid:
                    self.assertEqual(self.library['pattern_beats'][p['name']],rid);count+=1
        self.assertGreaterEqual(count,1088)
        self.assertGreaterEqual(self.library['coverage']['linked_movements'],1325)
        self.assertNotIn('lfo_breathe',self.library['pattern_beats'])

    def test_groove_credits_and_open_hat_articulation_survive(self):
        grooves=[b for b in self.beats.values() if b['kind']=='groove']
        self.assertEqual(len(grooves),4)
        for b in grooves:
            self.assertEqual(b['license'],'CC-BY-4.0')
            self.assertIn('Google',b['provenance']['attribution'])
        self.assertTrue(any(e['note']==46 for b in grooves for e in b['events']))
        self.assertTrue(any(Fraction(e['beat']).denominator>16 for b in grooves for e in b['events']))

    def test_source_hashes_and_registry_reproduce(self):
        doc=dict(self.library);digest=doc.pop('sha256')
        self.assertEqual(sha256(canonical(doc).encode()).hexdigest(),digest)
        for path,digest in doc['source_hashes'].items():
            self.assertEqual(sha256((ROOT/path).read_bytes()).hexdigest(),digest)
        saved=json.loads((ROOT/'harness/beats.json').read_text(encoding='utf-8'))
        self.assertEqual(saved,self.library)

    def test_protocol_fields_and_fractional_meters(self):
        for b in self.beats.values():
            period=Fraction(b['period_beats'])
            for e in b['events']:
                self.assertTrue(0<=Fraction(e['beat'])<period)
                self.assertTrue(0<=e['note']<=127 and 0<=e['channel']<16 and 0<e['velocity']<=1)
        self.assertTrue(any(Fraction(b['period_beats']).denominator==2 for b in self.beats.values()))

if __name__=='__main__':unittest.main()

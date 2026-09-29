"""Source provenance, exact timing, build determinism and optional pack loading."""
import base64
from collections import Counter
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest

from dancerudiments_authoring import compile_pack, load_pack, read_json
from dancerudiments_authoring.collections import initial_pack
from dancerudiments_authoring.initial_sources import (read_midi, read_akwf_header, verify_blob,
    nearest_sixteenth, excerpt_hits, smooth_periodic)

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'collections/initial'
try:
    import dancerudiments as native
except ImportError:
    native=None


def midi_file(track, ppq=480, fmt=0):
    return b'MThd'+struct.pack('>IHHH',6,fmt,1,ppq)+b'MTrk'+struct.pack('>I',len(track))+track


class InitialCollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack=initial_pack()
        cls.score=read_json(SOURCE/'initial.score.json')
        cls.raw=base64.b64decode(b''.join((SOURCE/'sources/groove/1_funk_80_beat_4-4.mid.b64').read_bytes().split()),validate=True)
        cls.midi=read_midi(cls.raw)

    def test_inventory(self):
        self.assertEqual(len(self.pack.patterns),28)
        self.assertEqual(sum(p.period_pips for p in self.pack.patterns),8704)
        self.assertEqual(Counter(p.provenance['family'] for p in self.pack.patterns),
                         {'LFO':8,'Rhythm':4,'Rudiment':4,'Easing':4,'AKWF':4,'Groove MIDI':4})

    def test_compilation_is_reproducible(self):
        self.assertEqual(compile_pack(self.score).to_dict(),self.pack.to_dict())

    def test_manifest_digest(self):
        manifest=read_json(SOURCE/'manifest.json')
        payload=json.dumps(self.pack.to_dict(),sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
        self.assertEqual(manifest['pack_sha256'],hashlib.sha256(payload.encode()).hexdigest())
        self.assertEqual([p.name for p in self.pack.patterns],[p['name'] for p in manifest['candidates']])

    def test_motion_bounds_and_seams(self):
        for p in self.pack.patterns:
            self.assertFalse(p.diagnostics['warnings'],p.name)
            self.assertLess(p.diagnostics['seam_position_error'],1e-7,p.name)
            self.assertLess(p.diagnostics['max_step'],.2,p.name)
            self.assertTrue(all(abs(v)<=1 for row in p.samples for v in row))
            self.assertGreater(max(abs(v) for row in p.samples for v in row),.25,p.name)

    def test_subset_preserves_data_and_provenance(self):
        chosen=['groove_b_played','akwf_round_saw','ease_rebound']
        subset=initial_pack(chosen)
        self.assertEqual([p.name for p in subset.patterns],['ease_rebound','akwf_round_saw','groove_b_played'])
        source={p.name:p.to_dict() for p in self.pack.patterns}
        for p in subset.patterns: self.assertEqual(p.to_dict(),source[p.name])

    def test_subset_rejects_bad_names(self):
        for names in [[],['missing'],['lfo_breathe','lfo_breathe'],'lfo_breathe',[3]]:
            with self.assertRaises(ValueError): initial_pack(names)

    def test_akwf_tables_and_notices(self):
        for filename in (SOURCE/'sources/akwf').glob('*.h'):
            raw=filename.read_bytes()
            values=read_akwf_header(raw)
            self.assertEqual(len(values),256)
            self.assertIn(b'CC0 1.0',raw)
            result=smooth_periodic(values)
            self.assertAlmostEqual(sum(result),0,places=10)
            self.assertAlmostEqual(max(abs(v) for v in result),.85,places=12)
        with self.assertRaises(ValueError): read_akwf_header(b'const int16_t x[256]={1};')
        with self.assertRaises(ValueError): verify_blob(b'wrong','0'*40)

    def test_groove_identity_and_metadata(self):
        verify_blob(self.raw,'4d4889860dea1b6ed9b65ee395aff3eb75c76ad1')
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),'cd8ed5d6c2564221e7d53c6a5b80d67f229c29a9558203d743418950b9fa3355')
        self.assertEqual(len(self.midi.hits),773)
        self.assertEqual(self.midi.ppq,480)
        self.assertEqual(self.midi.tempos,((0,750000),))
        self.assertEqual(self.midi.meters,((0,4,4),))

    def test_groove_pairs_keep_hits_and_velocities(self):
        for start in (4,36):
            played=excerpt_hits(self.midi,start,8)
            grid=excerpt_hits(self.midi,start,8,True)
            self.assertEqual([h for _,h in played],[h for _,h in grid])
            self.assertTrue(any(a!=b for (a,_),(b,_) in zip(played,grid)))
            self.assertTrue(all((t*4).denominator==1 for t,_ in grid))
            self.assertTrue(all(0<=t<8 for t,_ in played+grid))
        # Early downbeat belongs to A but is not silently shifted onto beat zero.
        early=[(t,h) for t,h in excerpt_hits(self.midi,4,8) if h.note==36 and h.tick==1919]
        self.assertEqual(early[0][0],Fraction(3839,480))

    def test_nearest_grid_ties(self):
        self.assertEqual(nearest_sixteenth(Fraction(1,8)),Fraction(1,4))
        self.assertEqual(nearest_sixteenth(Fraction(-1,8)),0)
        self.assertEqual(nearest_sixteenth(Fraction(1919,480)),4)

    def test_played_and_grid_motion_differ(self):
        byname={p.name:p for p in self.pack.patterns}
        for letter in 'ab':
            a,b=(byname[f'groove_{letter}_{v}'] for v in ('played','grid'))
            self.assertGreater(max(abs(x-y) for av,bv in zip(a.samples,b.samples) for x,y in zip(av,bv)),.02)
            self.assertEqual(a.provenance['license'],'CC-BY-4.0')
            self.assertEqual(a.provenance['source_sha256'],b.provenance['source_sha256'])
            self.assertIn('attribution',a.provenance)

    def test_d3_licence_survives_export(self):
        for name in ('ease_rebound','ease_anticipate','ease_overshoot'):
            p=initial_pack([name]).patterns[0]
            self.assertIn('Mike Bostock',p.provenance['license_notice'])
            self.assertIn('Redistributions in binary form',p.provenance['license_notice'])
            self.assertEqual(p.provenance['license'],'BSD-3-Clause')

    @unittest.skipIf(native is None,'Native Python extension not built')
    def test_native_library_every_sample_and_negative_seek(self):
        bank=self.pack.to_native()
        self.assertEqual(len(native.catalogue()),15)
        self.assertEqual(len(bank.catalogue()),43)
        for p in self.pack.patterns:
            for pip in list(range(-p.period_pips,p.period_pips))+[-2147483648,2147483647]:
                self.assertEqual(bank.sample(p.name,pip).as_tuple(),p.samples[pip%p.period_pips])


class MidiReaderTests(unittest.TestCase):
    def test_running_status_and_velocity_zero(self):
        track=bytes([0,0x99,36,80, 10,38,70, 10,38,0, 0,0xFF,0x2F,0])
        p=read_midi(midi_file(track))
        self.assertEqual([(h.tick,h.note,h.velocity,h.channel) for h in p.hits],[(0,36,80,9),(10,38,70,9)])

    def test_all_truncations_are_rejected(self):
        raw=midi_file(bytes([0,0x99,36,80,0,0xFF,0x2F,0]))
        for length in range(len(raw)):
            with self.assertRaises(ValueError): read_midi(raw[:length])

    def test_reject_smpte_and_format2(self):
        for kwargs in [dict(ppq=0),dict(ppq=0xE728),dict(fmt=2)]:
            with self.assertRaises(ValueError): read_midi(midi_file(bytes([0,0xFF,0x2F,0]),**kwargs))

    def test_reject_invalid_event_data_and_vlq(self):
        for track in [bytes([0,36,80]),bytes([0,0x99,36,128]),bytes([255]*5),
                      bytes([0,0xF1,0]),bytes([0,0x99,36,80])]:
            with self.assertRaises(ValueError): read_midi(midi_file(track))

    def test_sysex_and_metadata(self):
        track=bytes([0,0xF0,3,1,2,0xF7,0,0xFF,0x51,3,7,161,32,0,0x99,36,99,0,0xFF,0x2F,0])
        score=read_midi(midi_file(track))
        self.assertEqual(score.tempos,((0,500000),))
        self.assertEqual(len(score.hits),1)

if __name__=='__main__': unittest.main()

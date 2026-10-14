import copy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from dancerudiments_authoring import load_pack
from dancerudiments_authoring._validation import ScoreError
from dancerudiments_authoring.recording import Recording, RecordingClock, load_recording, write_recording, write_document
from dancerudiments_authoring.harness import build_recording_harness, ASSETS


class RecordingTests(unittest.TestCase):
    def recording(self, dims=6, name='audio_recording'):
        return Recording(name, tuple('axis_'+str(i) for i in range(dims)),
                         tuple(tuple(round(.7*math.sin((i+j)*.1),12) for j in range(dims)) for i in range(128)),
                         RecordingClock(123.456, 'test', beat_zero_seconds=.25, start_pip=-32))

    def test_clock_requires_bpm_and_labels(self):
        for bpm in [None, 0, -1, True, float('nan'), float('inf'), '120']:
            with self.subTest(bpm=bpm), self.assertRaises(ScoreError):
                RecordingClock(bpm, 'test')
        for kwargs in [dict(bpm_source=''), dict(bpm_status='unknown'), dict(phase_status='confirmed'), dict(start_pip=True)]:
            with self.assertRaises(ScoreError):
                RecordingClock(**dict(dict(bpm=120,bpm_source='test'), **kwargs))

    def test_all_dimensions_roundtrip_and_precision(self):
        with tempfile.TemporaryDirectory() as folder:
            for dims in [1,2,3,4,8,128]:
                r=self.recording(dims)
                p=Path(folder)/(str(dims)+'.json')
                write_recording(p,r)
                self.assertEqual(load_recording(p),r)
            r=Recording('precise',('x',),((.1234567890123456,),),RecordingClock(120,'test'))
            self.assertEqual(r.samples[0][0],.123456789012)

    def test_validation_headers_shapes_and_values(self):
        doc=self.recording().to_dict()
        for key,value in [('pips_per_beat',16),('sample_dtype','int16'),('sample_decimals',6),
                          ('schema_version',True),('dimensions',['x','x']),('samples',[[0]]),
                          ('samples',[[float('inf')]*6]),('provenance',[]),('clock',{})]:
            data=copy.deepcopy(doc)
            data[key]=value
            with self.subTest(key=key),self.assertRaises(ScoreError):
                Recording.from_dict(data)
        data=copy.deepcopy(doc)
        data['extra']=0
        with self.assertRaises(ScoreError):
            Recording.from_dict(data)

    def test_legacy_selection_and_native(self):
        r=self.recording()
        with self.assertRaises(ScoreError):
            r.to_compiled_pack()
        pack=r.to_compiled_pack(dimensions=('axis_4','axis_0'))
        self.assertEqual(pack.patterns[0].samples[0],(r.samples[0][4],r.samples[0][0],0.))
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'legacy.json'
            write_document(p,pack.to_dict())
            self.assertEqual(load_pack(p),pack)
        try:
            import dancerudiments
        except ImportError:
            if os.environ.get('DANCERUDIMENTS_REQUIRE_NATIVE')=='1':
                raise
            self.skipTest('Native extension not installed')
        self.assertTrue(hasattr(dancerudiments,'SampledRecording'))
        native=r.to_native()
        for i in (0,63,127):
            self.assertEqual(native.sample(r.clock.start_pip+i),list(r.samples[i]))
        with self.assertRaises(IndexError):
            native.sample(r.clock.start_pip-1)
        with self.assertRaises(IndexError):
            native.sample(r.clock.start_pip+len(r.samples))
        lib=pack.to_native()
        self.assertEqual(lib.sample(r.name,0).as_tuple(),pack.patterns[0].samples[0])

    def test_no_clobber_and_strict_json(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'r.json'
            write_recording(p,self.recording())
            before=p.read_bytes()
            with self.assertRaises(FileExistsError):
                write_recording(p,self.recording(2))
            self.assertEqual(p.read_bytes(),before)
            p.write_text('{"format":1,"format":2}')
            with self.assertRaises(ScoreError):
                load_recording(p)

    def test_shared_harness_and_column_dedup(self):
        with tempfile.TemporaryDirectory() as folder:
            a=self.recording()
            b=Recording('second',a.dimensions,a.samples,a.clock)
            output=Path(folder)/'index.html'
            report=build_recording_harness([a,b],output)
            self.assertEqual(report['unique_columns'],6)
            self.assertEqual(report['candidates'],2)
            self.assertIn((ASSETS/'app.js').read_text(),output.read_text())
            self.assertIn('sample_recording',output.read_text())
            self.assertNotIn('https://cdn',output.read_text())
            with self.assertRaises(FileExistsError):
                build_recording_harness([a],output)
            mismatch=Recording('mismatch',a.dimensions,a.samples,RecordingClock(120,'test'))
            with self.assertRaises(ScoreError):
                build_recording_harness([a,mismatch],Path(folder)/'bad.html')
            self.assertFalse((Path(folder)/'bad.html').exists())

    def test_script_content_is_data_not_markup(self):
        r=self.recording(2)
        r=Recording(r.name,r.dimensions,r.samples,r.clock,json.dumps({'title':'</script><script>window.BAD=1</script>'}))
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'a.html'
            build_recording_harness([r],p)
            self.assertNotIn('</script><script>window.BAD',p.read_text())
            self.assertIn('\\u003c/script>',p.read_text())

    def test_wasm_source_and_binary_checksums(self):
        import base64
        manifest=json.loads((ASSETS/'recording.wasm.json').read_text())
        raw=base64.b64decode((ASSETS/'recording.wasm.b64').read_text())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),manifest['wasm_sha256'])
        root=Path(__file__).resolve().parents[2]
        for rel in ['tools/recording_wasm.cpp','include/dancerudiments/recording_view.hpp']:
            self.assertEqual(hashlib.sha256((root/rel).read_bytes()).hexdigest(),manifest[rel])

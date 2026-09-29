from __future__ import annotations

import copy
from fractions import Fraction
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from dancerudiments_authoring import (CompiledPack, ScoreError, compile_pack, compile_score,
                                      emit_cpp, emit_json, load_pack, read_json)
from dancerudiments_authoring.cli import main

ROOT = Path(__file__).resolve().parents[2]


def single(curve=None, **updates):
    score = {'name': 'custom', 'period_beats': 1,
             'tracks': [{'axis': 'x', 'curve': curve or {'type': 'lfo'}}]}
    score.update(updates)
    return score


def events(anchor='peak'):
    return {'name': 'hits', 'period_beats': 1,
            'gestures': {'hit': {'duration_beats': '1/2', 'axes': {'x': 1}}},
            'events': [{'beat': 0, 'gesture': 'hit', 'anchor': anchor}]}


class AuthoringTests(unittest.TestCase):
    def test_sine_samples(self):
        p = compile_score(single())
        self.assertEqual(p.period_pips, 64)
        self.assertEqual(p.samples[16], (1, 0, 0))
        self.assertEqual(p.samples[48], (-1, 0, 0))

    def test_non_four_beat_periods(self):
        for n in (3, 5, 7, 8, 16):
            self.assertEqual(compile_score(single(period_beats=n)).period_pips, 64*n)

    def test_fractional_enclosing_period(self):
        self.assertEqual(compile_score(single(period_beats='3/2')).period_pips, 96)
        with self.assertRaises(ScoreError):
            compile_score(single(period_beats='1/3'))

    def test_triangle_and_skew(self):
        self.assertEqual(compile_score(single({'type':'lfo', 'shape':'triangle'})).samples[32][0], 1)
        p = compile_score(single({'type':'lfo', 'shape':'skew_triangle', 'duty':.25}))
        self.assertEqual(p.samples[16][0], 1)

    def test_saw_requires_explicit_jump(self):
        for shape in ('saw_up', 'saw_down', 'pulse'):
            with self.subTest(shape=shape):
                with self.assertRaisesRegex(ScoreError, 'position reset'):
                    compile_score(single({'type':'lfo', 'shape':shape}))
                p = compile_score(single({'type':'lfo', 'shape':shape}, loop_policy='allow_jump'))
                self.assertTrue(p.diagnostics['warnings'])

    def test_phase_offset(self):
        p = compile_score(single({'type':'lfo', 'phase':'1/4'}))
        self.assertEqual(p.samples[0][0], 1)

    def test_exact_triplet_phase(self):
        p = compile_score(single({'type':'lfo', 'period_beats':'1/3'}))
        for i, v in enumerate(p.samples):
            expected = math.sin(2*math.pi*float((Fraction(i,64)*3) % 1))
            self.assertAlmostEqual(v[0], expected, places=11)
        self.assertAlmostEqual(p.diagnostics['seam_position_error'], 0, places=7)

    def test_keyframes(self):
        for interpolation in ('linear', 'smoothstep', 'smootherstep', 'cubic'):
            point = {'beat':0,'value':0,'interpolation':interpolation}
            if interpolation == 'cubic': point.update(control1=0, control2=1)
            curve = {'type':'keyframes','points':[point, {'beat':'1/2','value':1}, {'beat':1,'value':0}]}
            p = compile_score(single(curve))
            self.assertEqual(p.samples[32][0], 1)
            self.assertAlmostEqual(p.samples[16][0], .5)

    def test_hold_keyframes(self):
        p = compile_score(single({'type':'keyframes', 'points':[
            {'beat':0,'value':0,'interpolation':'hold'},
            {'beat':'1/2','value':1,'interpolation':'hold'}, {'beat':1,'value':0}]},
            loop_policy='allow_jump'))
        self.assertEqual(p.samples[31][0], 0)
        self.assertEqual(p.samples[32][0], 1)

    def test_bad_keyframes(self):
        for points in ([{'beat':0,'value':0},{'beat':0,'value':1}],
                       [{'beat':'.5','value':0},{'beat':1,'value':0}],
                       [{'beat':0,'value':0,'control1':2},{'beat':1,'value':0}]):
            with self.assertRaises(ScoreError): compile_score(single({'type':'keyframes','points':points}))

    def test_sampled_curve_wrap(self):
        p = compile_score(single({'type':'samples','values':[0,1,0,-1]}))
        self.assertEqual([p.samples[i][0] for i in (0,16,32,48)], [0,1,0,-1])
        self.assertAlmostEqual(p.samples[63][0], -.0625)

    def test_mix_and_layers(self):
        p = compile_score(single({'type':'mix', 'a':{'type':'constant','value':-1},
                                 'b':{'type':'constant','value':1}, 'amount':.75}))
        self.assertEqual(p.samples[0], (.5,0,0))
        for kind, expected in [('sum', .75), ('product', .125)]:
            p = compile_score(single({'type':kind,'curves':[{'type':'constant','value':.5},
                                                           {'type':'constant','value':.25}]}))
            self.assertEqual(p.samples[0][0], expected)

    def test_mix_rejects_out_of_range(self):
        with self.assertRaises(ScoreError):
            compile_score(single({'type':'mix','a':{'type':'constant','value':0},
                                  'b':{'type':'constant','value':1},'amount':2}))

    def test_seeded_random(self):
        s = single({'type':'random_smooth','seed':98,'steps':7})
        a, b = compile_score(s), compile_score(s)
        self.assertEqual(a.samples, b.samples)
        s['tracks'][0]['curve']['seed'] = 99
        self.assertNotEqual(a.samples, compile_score(s).samples)
        self.assertLess(a.diagnostics['seam_position_error'], 1e-7)

    def test_random_hold(self):
        p = compile_score(single({'type':'random_hold','seed':3,'steps':4}, loop_policy='allow_jump'))
        self.assertEqual(p.samples[0], p.samples[15])
        self.assertNotEqual(p.samples[15], p.samples[16])

    def test_peak_onset_end_anchors(self):
        for anchor, index in [('peak',0), ('onset',16), ('end',48)]:
            p = compile_score(events(anchor))
            self.assertEqual(p.samples[index][0], 1)

    def test_event_wraps_into_previous_loop(self):
        p = compile_score(events())
        self.assertEqual(p.samples[1], p.samples[63])
        self.assertEqual(p.samples[16][0], 0)

    def test_event_shapes_asymmetric_peak(self):
        for shape in ('cosine','smoothstep','triangle'):
            score = events('onset')
            score['gestures']['hit'].update(shape=shape, peak_fraction='1/4')
            self.assertEqual(compile_score(score).samples[8][0], 1)

    def test_event_overlap_and_bounds(self):
        score = events()
        score['events'] *= 2
        with self.assertRaisesRegex(ScoreError, 'exceeds'): compile_score(score)
        score['bounds'] = 'scale'
        p = compile_score(score)
        self.assertEqual(p.samples[0][0], 1)
        self.assertEqual(p.diagnostics['normalization_scale'], .5)
        score['bounds'] = 'clip'
        self.assertTrue(compile_score(score).diagnostics['warnings'])

    def test_tiny_event_warning(self):
        score = events('onset')
        score['events'][0].update(beat='1/1000',duration_beats='1/1000')
        p = compile_score(score)
        self.assertTrue(any('no nonzero sample' in w for w in p.diagnostics['warnings']))

    def test_event_validation(self):
        for change in ({'anchor':'contact'}, {'gesture':'missing'}, {'beat':1},
                       {'strength':-1}, {'duration_beats':0}):
            score = events();score['events'][0].update(change)
            with self.assertRaises(ScoreError): compile_score(score)

    def test_unknown_fields_and_types(self):
        for score in [single(extra=1), single({'type':'eval','code':'print(1)'}),
                      single({'type':'lfo','peroid_beats':1}), single(period_beats=True),
                      single({'type':'constant','value':float('nan')}), single({'type':'lfo','duty':0})]:
            with self.subTest(score=score):
                with self.assertRaises(ScoreError): compile_score(score)

    def test_arithmetic_failures_are_score_errors(self):
        curve={'type':'sum','curves':[{'type':'constant','value':2,'gain':1e308},
                                     {'type':'constant','value':-2,'gain':1e308}]}
        with self.assertRaises(ScoreError): compile_score(single(curve))

    def test_recursion_limit(self):
        curve = {'type':'constant','value':0}
        for _ in range(18): curve = {'type':'sum','curves':[curve]}
        with self.assertRaises(ScoreError): compile_score(single(curve))

    def test_names_and_duplicates(self):
        for identifier in ('Bad', 'x;exit()', '', '9nine'):
            with self.assertRaises(ScoreError): compile_pack(single(name=identifier))
        with self.assertRaises(ScoreError): compile_pack(single(name='circle'))
        with self.assertRaises(ScoreError):
            compile_pack({'format':'dancerudiments.score-pack','schema_version':1,'patterns':[single(),single()]})

    def test_source_digest_and_metadata(self):
        score = single(provenance={'license':'MIT','author':'A'})
        p = compile_score(score)
        self.assertEqual(p.source_sha256, compile_score(dict(reversed(list(score.items())))).source_sha256)
        external = p.provenance;external['license']='changed'
        self.assertEqual(p.provenance['license'], 'MIT')
        self.assertEqual(len(p.source_sha256),64)

    def test_compiled_roundtrip(self):
        pack = compile_pack(single())
        self.assertEqual(CompiledPack.from_dict(json.loads(emit_json(pack))), pack)

    def test_compiled_validation(self):
        for path, value in [('period_pips',3), ('source_sha256','bad'), ('samples',[[2,0,0]]*64)]:
            data = compile_pack(single()).to_dict();data['patterns'][0][path]=value
            with self.assertRaises(ScoreError): CompiledPack.from_dict(data)
        data = compile_pack(single()).to_dict();data['pips_per_beat']=16
        with self.assertRaises(ScoreError): CompiledPack.from_dict(data)

    def test_all_starter_examples(self):
        pack = compile_pack(read_json(ROOT/'examples/patterns/starter.json'))
        self.assertEqual([p.period_pips for p in pack.patterns], [128,64,192,512])
        self.assertTrue(all(not p.diagnostics['warnings'] for p in pack.patterns))

    def test_cli_compile_check_and_staleness(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.json';source.write_text(json.dumps(single()))
            target=Path(directory)/'pack.json';header=Path(directory)/'pack.hpp'
            args=[str(source),'--json',str(target),'--cpp',str(header)]
            self.assertEqual(main(['compile']+args),0)
            self.assertEqual(main(['check']+args),0)
            self.assertEqual(load_pack(target).patterns[0].name,'custom')
            target.write_text('{}')
            self.assertEqual(main(['check']+args),2)
            self.assertEqual(main(['compile',str(source),'--json',str(source)]),2)
            self.assertEqual(main(['validate',str(source)]),0)

    def test_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.json'
            for value in ('{"a":1,"a":2}', '{"a":NaN}'):
                path.write_text(value)
                with self.assertRaises(ScoreError): read_json(path)

    def test_pack_limits_fail_before_compilation(self):
        from unittest.mock import patch
        scores=[single(name=f'pattern_{i}', period_beats=1000) for i in range(17)]
        document={'format':'dancerudiments.score-pack','schema_version':1,'patterns':scores}
        with patch('dancerudiments_authoring.compiler.compile_score') as compile_one:
            with self.assertRaisesRegex(ScoreError, 'total sample'):
                compile_pack(document)
            compile_one.assert_not_called()

    def test_bad_cpp_output_does_not_overwrite_json(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.json'; source.write_text(json.dumps(single()))
            target=Path(directory)/'pack.json'; target.write_text('sentinel')
            header=Path(directory)/'pack.hpp'
            self.assertEqual(main(['compile',str(source),'--json',str(target),
                                   '--cpp',str(header),'--namespace','class']),2)
            self.assertEqual(target.read_text(),'sentinel')
            self.assertFalse(header.exists())

    def test_authoring_does_not_import_native(self):
        # A fresh interpreter must author a score without loading the C++ module.
        code = "import sys; from dancerudiments_authoring import compile_score; " \
               "compile_score({'name':'plain','period_beats':1,'tracks':[{'axis':'x','curve':{'type':'lfo'}}]}); " \
               "assert 'dancerudiments' not in sys.modules"
        subprocess.run([sys.executable,'-c',code],check=True)

    def test_codegen_namespace_safety(self):
        pack=compile_pack(single())
        for namespace in ('std', 'class', 'bad;code', '_reserved', 'x::__reserved'):
            with self.assertRaises(ScoreError): emit_cpp(pack,namespace)
        self.assertIn('namespace demo::moves',emit_cpp(pack,'demo::moves'))
        with self.assertRaises(ScoreError): emit_cpp(compile_pack(single(name='a__b')))

    def test_generated_header_compiles_and_matches_every_pip(self):
        compiler=shutil.which('g++') or shutil.which('clang++')
        if compiler is None: self.skipTest('C++ compiler unavailable')
        pack=compile_pack(read_json(ROOT/'examples/patterns/starter.json'))
        # Exercise UTF-8 literals and C++-keyword names too.
        unicode_score=single(name='class', description='Quotes " and slash \\ and music \U0001f3b5')
        pack=CompiledPack(pack.patterns+(compile_score(unicode_score),))
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            (directory/'generated.hpp').write_text(emit_cpp(pack),encoding='utf-8')
            (directory/'main.cpp').write_text('''#include "generated.hpp"
#include <iostream>
#include <iomanip>
int main() {
 auto bank=dancerudiments_generated::make_library();
 std::cout << std::setprecision(17);
 for (auto info:bank.catalogue()) {
   if (info.name == "wobble_xy" || info.name == "triplet_steps" || info.name == "segmented_sway" || info.name == "seeded_drift" || info.name == "class") {
     for (int i=-1;i<=info.period_pips;i++) {
       auto v=bank.sample(info.name,i);
       std::cout << info.name << " " << i << " " << v.x << " " << v.y << " " << v.z << "\\n";
     }
   }
 }
 auto a=dancerudiments_generated::sample_wobble_xy(-1);
 auto b=bank.sample("wobble_xy",-1);
 return (a.x == b.x && a.y == b.y && a.z == b.z) ? 0 : 1;
}''')
            executable=directory/'verify'
            subprocess.run([compiler,'-std=c++17','-I',str(ROOT/'include'),'-I',str(directory),
                            str(directory/'main.cpp'),str(ROOT/'src/dance_rudiments.cpp'),
                            str(ROOT/'src/sampled_pattern.cpp'),'-o',str(executable)],check=True,
                           capture_output=True)
            output=subprocess.check_output([str(executable)],text=True)
            by_name={p.name:p for p in pack.patterns}
            for line in output.splitlines():
                identifier,pip,*row=line.split();pattern=by_name[identifier]
                self.assertEqual(tuple(map(float,row)),pattern.samples[int(pip)%pattern.period_pips])


if __name__ == '__main__': unittest.main()

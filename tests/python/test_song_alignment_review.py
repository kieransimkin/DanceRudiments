"""Actual JS/StemLab timing-review interchange with synthetic source identities.

No audio decoding, model inference, browser substitute, media or network input.
The dedicated integration gate sets DANCERUDIMENTS_REQUIRE_STEMLAB=1 so missing
Node or an incompatible optional companion fails instead of silently skipping.
"""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tools' / 'song_loop_viewer' / 'alignment-review.js'
SPEC = importlib.util.spec_from_file_location(
    'song_alignment_review_builder', ROOT / 'tools' / 'build_song_loop_preview.py')
PREVIEW = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PREVIEW
SPEC.loader.exec_module(PREVIEW)

NODE_RUNNER = r"""
import {readFileSync} from 'node:fs';
await import(process.argv[1]);
const input=JSON.parse(readFileSync(0,'utf8'));
const api=globalThis.DanceRudimentsTimingReview;
const before=JSON.stringify(input);
try{
  let value;
  switch(input.operation){
    case 'revision': value=api.makeRevision(input.entry,input.candidateIndex??0,input.options);break;
    case 'segments': value=api.shiftedSegments(input.entry,input.candidateIndex??0,input.offset??0);break;
    case 'inverse': value=input.times.map(t=>api.inverseTime(input.segments,t));break;
    case 'phase': value=input.times.map(t=>api.phaseForSource(input.motion,t));break;
    case 'matching': value=api.matchingReviews(input.reviews,input.song,input.motion);break;
    default: throw Error('Unknown test operation');
  }
  process.stdout.write(JSON.stringify({ok:true,value,inputUnchanged:JSON.stringify(input)===before}));
}catch(error){
  process.stdout.write(JSON.stringify({ok:false,error:error.message,inputUnchanged:JSON.stringify(input)===before}));
}
"""


class SongAlignmentReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from stemlab.analysis import motion_alignment
            for name in ('align_motion_audio', 'make_event_evidence', 'validate_alignment_revision'):
                if not hasattr(motion_alignment, name):
                    raise ImportError(f'Compatible StemLab API missing: {name}')
        except ImportError as exc:
            if os.environ.get('DANCERUDIMENTS_REQUIRE_STEMLAB') == '1':
                raise AssertionError(f'StemLab timing-review integration is required: {exc}') from exc
            raise unittest.SkipTest('Compatible StemLab is an optional offline companion') from exc
        cls.alignment = motion_alignment
        cls.node = shutil.which('node')
        if cls.node is None:
            if os.environ.get('DANCERUDIMENTS_REQUIRE_STEMLAB') == '1':
                raise AssertionError('Node is required for actual JavaScript timing-review interchange')
            raise unittest.SkipTest('Node is required for the optional timing-review integration')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='song-alignment-review-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def fixture(self, *, gaps=False, repaired=False):
        job = self.root / 'source-job'
        job.mkdir()
        (job / 'job.json').write_text('{"synthetic":true}', encoding='utf-8')
        capture = (job / 'repaired-loops' / 'candidate.capture.json' if repaired
                   else job / 'source.capture.json')
        capture.parent.mkdir(exist_ok=True)
        capture.write_bytes(b'{"synthetic":"source capture identity; no third-party motion"}')
        audio = self.root / 'synthetic-audio.source'
        audio.write_bytes(b'synthetic audio source identity; deliberately not an encoded audio file')
        times = [1.40, 2.05, 2.49, 3.20, 3.58, 4.30, 4.88, 5.30, 5.97,
                 6.41, 7.12, 7.50, 8.21, 8.80, 9.20, 9.87, 10.31, 11.02]
        if gaps:
            times = [t for t in times if t <= 5 or t >= 7]
        motion_segments = [[1., 5.], [7., 12.]] if gaps else [[1., 12.]]
        audio_segments = [[0., 5.373], [7.373, 16.]] if gaps else [[0., 16.]]

        def evidence(kind, path, values, bounds, segments):
            return self.alignment.make_event_evidence(
                kind=kind, source_sha256=self.alignment.file_hash(path),
                clock_id=kind + '-original', seconds_range=bounds,
                valid_segments_seconds=segments,
                streams=[dict(id=kind + '-events', family=kind + '-synthetic-family',
                              event_type='observed_feature_peak',
                              events=[dict(seconds=t, strength=1.) for t in values])],
                provenance=dict(synthetic=True))

        motion = evidence('motion', capture, times, [1., 12.], motion_segments)
        sonic = evidence('audio', audio, [t + .373 for t in times], [0., 16.], audio_segments)
        clock = dict(format=self.alignment.CLOCK_FORMAT, schema_version=1,
                     motion_source_sha256=motion['source']['sha256'],
                     audio_source_sha256=sonic['source']['sha256'],
                     motion_clock_id='motion-original', audio_clock_id='audio-original',
                     motion_origin_seconds=1., audio_origin_seconds=1., seconds_scale=1.,
                     relationship='same_performance')
        report = self.alignment.align_motion_audio(
            motion, sonic, clock, motion_source=capture, audio_source=audio,
            max_offset_seconds=.5, rate_multipliers=[1.], variable_tempo=False)
        self.assertTrue(report['candidates'])
        self.assertAlmostEqual(report['candidates'][0]['intercept_seconds'], .373, places=5)
        report_path = self.root / 'alignment.json'
        self.alignment.write_document(report_path, report)
        displayed_motion = dict(id='synthetic-motion', source_capture_sha256=motion['source']['sha256'])
        song = dict(id='synthetic-song', source_sha256=sonic['source']['sha256'])
        entries = PREVIEW._alignment_reviews([report_path], [displayed_motion], [song], [job])
        self.assertEqual(len(entries), 1)
        return dict(job=job, capture=capture, audio=audio, report=report, report_path=report_path,
                    entry=entries[0], motion=displayed_motion, song=song)

    def javascript(self, **payload):
        completed = subprocess.run(
            [self.node, '--input-type=module', '-e', NODE_RUNNER, SCRIPT.as_uri()],
            input=json.dumps(payload, allow_nan=False), capture_output=True,
            text=True, encoding='utf-8', timeout=30, cwd=ROOT)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result['inputUnchanged'], 'Viewer review mutated original input evidence')
        return result

    def test_real_builder_and_javascript_revision_pass_backend_with_phase_meter_and_beat_one(self):
        fixture = self.fixture()
        original_bytes = fixture['report_path'].read_bytes()
        result = self.javascript(operation='revision', entry=fixture['entry'], options=dict(
            offset=.125, reviewer='  Synthetic reviewer  ', beatOne=2.498, meter=[6, 8]))
        self.assertTrue(result['ok'], result)
        revision = result['value']
        validated = self.alignment.validate_alignment_revision(
            fixture['report'], revision, report_sha256=self.alignment.file_hash(fixture['report_path']))
        self.assertEqual(validated, revision)
        self.assertEqual(revision['reviewer'], 'Synthetic reviewer')
        self.assertEqual(revision['mapping_status'], 'user_confirmed')
        self.assertEqual(revision['beat_one_audio_seconds'], 2.498)
        self.assertEqual(revision['beat_one_status'], 'user_confirmed')
        self.assertEqual(revision['meter'], [6, 8])
        self.assertEqual(revision['meter_status'], 'user_confirmed')
        self.assertFalse(revision['loop_seams_verified'])
        self.assertFalse(revision['retargeting_verified'])
        self.assertTrue(revision['reviewed_at'].endswith('Z'))
        before = fixture['report']['candidates'][0]['mapping_segments']
        self.assertEqual(len(before), len(revision['mapping_segments']))
        for original, shifted in zip(before, revision['mapping_segments']):
            self.assertEqual(shifted['anchor_kind'], 'user_phase_correction')
            self.assertEqual(len(original['anchors']), len(shifted['anchors']))
            for a, b in zip(original['anchors'], shifted['anchors']):
                self.assertEqual(a['motion_seconds'], b['motion_seconds'])
                self.assertAlmostEqual(b['audio_seconds'] - a['audio_seconds'], .125)
        self.assertEqual(fixture['report_path'].read_bytes(), original_bytes)
        self.assertIsNone(fixture['report']['selected_candidate_id'])

    def test_mapping_acceptance_does_not_implicitly_confirm_beat_one_or_meter(self):
        fixture = self.fixture()
        result = self.javascript(operation='revision', entry=fixture['entry'],
                                 options=dict(offset=-.25, reviewer='Fixture'))
        self.assertTrue(result['ok'], result)
        revision = result['value']
        self.alignment.validate_alignment_revision(fixture['report'], revision)
        self.assertIsNone(revision['beat_one_audio_seconds'])
        self.assertIsNone(revision['meter'])
        self.assertEqual(revision['beat_one_status'], 'unconfirmed')
        self.assertEqual(revision['meter_status'], 'unconfirmed')

    def test_changed_report_file_content_or_source_identity_reject_exported_revision(self):
        fixture = self.fixture()
        result = self.javascript(operation='revision', entry=fixture['entry'],
                                 options=dict(reviewer='Fixture'))
        self.assertTrue(result['ok'], result)
        original_revision = result['value']
        for mutation in ('report_content', 'report_file_hash', 'motion_hash', 'audio_hash'):
            with self.subTest(mutation=mutation):
                report, revision = deepcopy(fixture['report']), deepcopy(original_revision)
                digest = fixture['entry']['report_sha256']
                if mutation == 'report_content':
                    report['clock_mapping']['seconds_scale'] = 2.
                elif mutation == 'report_file_hash':
                    digest = 'f' * 64
                else:
                    revision[mutation.replace('_hash', '_source_sha256')] = 'f' * 64
                with self.assertRaises(ValueError):
                    self.alignment.validate_alignment_revision(report, revision, report_sha256=digest)

    def test_phase_corrections_outside_bounds_or_numeric_limits_are_rejected(self):
        fixture = self.fixture()
        for offset in (31, -31, -2, 5, '0.1'):
            with self.subTest(offset=offset):
                result = self.javascript(operation='revision', entry=fixture['entry'],
                                         options=dict(offset=offset, reviewer='Fixture'))
                self.assertFalse(result['ok'])
                self.assertRegex(result['error'], 'Phase correction|boundary')
        for options in (dict(beatOne=-.1), dict(beatOne=16.1), dict(meter=[4, 3]),
                        dict(meter=[0, 4]), dict(reviewer='   ')):
            with self.subTest(options=options):
                result = self.javascript(operation='revision', entry=fixture['entry'],
                                         options={**dict(reviewer='Fixture'), **options})
                self.assertFalse(result['ok'])

    def test_source_gaps_survive_javascript_mapping_and_forbid_crossing_phase_edits(self):
        fixture = self.fixture(gaps=True)
        result = self.javascript(operation='segments', entry=fixture['entry'], offset=0.)
        self.assertTrue(result['ok'], result)
        segments = result['value']
        self.assertEqual(len(segments), 2)
        inverse = self.javascript(operation='inverse', segments=segments,
                                  times=[-1., 2.373, 6.373, 8.373, 17.])
        self.assertTrue(inverse['ok'], inverse)
        self.assertEqual(inverse['value'][0], None)
        self.assertAlmostEqual(inverse['value'][1], 2.)
        self.assertIsNone(inverse['value'][2])
        self.assertAlmostEqual(inverse['value'][3], 8.)
        self.assertIsNone(inverse['value'][4])
        for offset in (.1, -.1):
            with self.subTest(offset=offset):
                shifted = self.javascript(operation='segments', entry=fixture['entry'], offset=offset)
                self.assertFalse(shifted['ok'])
                self.assertIn('coverage gap', shifted['error'])
        accepted = self.javascript(operation='revision', entry=fixture['entry'],
                                   options=dict(reviewer='Fixture'))
        self.assertTrue(accepted['ok'], accepted)
        self.alignment.validate_alignment_revision(fixture['report'], accepted['value'])

    def test_source_phase_respects_negative_times_closed_actions_and_loop_end(self):
        motion = dict(source_clock_start_seconds=1.5, source_start_seconds=99.,
                      raw_sample_count=128, estimated_bpm=120., loopable=False)
        end = 1.5 + 127 / 128
        result = self.javascript(operation='phase', motion=motion, times=[-1., 1.4, 1.5, 2., end, 2.5])
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['value'][:3], [None, None, 0])
        self.assertAlmostEqual(result['value'][3], .5)
        self.assertAlmostEqual(result['value'][4], 127 / 128)
        self.assertIsNone(result['value'][5])
        loop = self.javascript(operation='phase', motion={**motion, 'loopable': True}, times=[1.5, 2.49, 2.5])
        self.assertTrue(loop['ok'], loop)
        self.assertEqual(loop['value'][0], 0)
        self.assertAlmostEqual(loop['value'][1], .99)
        self.assertIsNone(loop['value'][2])

    def test_javascript_review_selection_requires_both_displayed_source_hashes(self):
        fixture = self.fixture()
        wrong_audio = deepcopy(fixture['entry'])
        wrong_audio['report']['audio_source']['sha256'] = 'a' * 64
        wrong_motion = deepcopy(fixture['entry'])
        wrong_motion['report']['motion_source']['sha256'] = 'b' * 64
        result = self.javascript(operation='matching', reviews=[wrong_audio, fixture['entry'], wrong_motion],
                                 song=fixture['song'], motion=fixture['motion'])
        self.assertTrue(result['ok'], result)
        self.assertEqual(len(result['value']), 1)
        self.assertEqual(result['value'][0]['report_sha256'], fixture['entry']['report_sha256'])

    def test_builder_hashes_the_actual_capture_and_matches_displayed_motion_and_song(self):
        fixture = self.fixture()
        entry = fixture['entry']
        self.assertEqual(entry['report_sha256'], self.alignment.file_hash(fixture['report_path']))
        self.assertEqual(entry['report_content_sha256'], self.alignment.document_hash(fixture['report']))
        arguments = ([fixture['report_path']], [fixture['motion']], [fixture['song']], [fixture['job']])
        for mutation in ('displayed_motion', 'master', 'capture_bytes', 'missing_job_capture'):
            with self.subTest(mutation=mutation):
                paths, motions, songs, jobs = deepcopy(arguments)
                original = fixture['capture'].read_bytes()
                original_audio = fixture['audio'].read_bytes()
                try:
                    if mutation == 'displayed_motion':
                        motions[0]['source_capture_sha256'] = 'a' * 64
                    elif mutation == 'master':
                        fixture['audio'].write_bytes(b'changed synthetic audio identity')
                        songs[0]['source_sha256'] = self.alignment.file_hash(fixture['audio'])
                    elif mutation == 'capture_bytes':
                        fixture['capture'].write_bytes(b'changed synthetic capture identity')
                    else:
                        jobs = [self.root / 'absent-job']
                    with self.assertRaisesRegex(ValueError, 'differs'):
                        PREVIEW._alignment_reviews(paths, motions, songs, jobs)
                finally:
                    fixture['capture'].write_bytes(original)
                    fixture['audio'].write_bytes(original_audio)

    def test_builder_supports_exact_repaired_capture_identities(self):
        fixture = self.fixture(repaired=True)
        self.assertEqual(fixture['entry']['report']['motion_source']['sha256'],
                         self.alignment.file_hash(fixture['capture']))
        self.assertFalse((fixture['job'] / 'source.capture.json').exists())

    def test_builder_rejects_unverified_or_out_of_source_report_mappings(self):
        fixture = self.fixture()
        for mutation in ('verified_flag', 'format', 'mapping_bounds'):
            with self.subTest(mutation=mutation):
                report = deepcopy(fixture['report'])
                if mutation == 'verified_flag':
                    report['source_bytes_verified'] = False
                elif mutation == 'format':
                    report['format'] = 'some.other-report'
                else:
                    segment = report['candidates'][0]['mapping_segments'][0]
                    segment['anchors'][0]['audio_seconds'] = -.1
                    segment['audio_seconds_range'][0] = -.1
                path = self.root / (mutation + '.json')
                self.alignment.write_document(path, report)
                with self.assertRaises(ValueError):
                    PREVIEW._alignment_reviews([path], [fixture['motion']], [fixture['song']], [fixture['job']])
        with self.assertRaisesRegex(ValueError, 'sixteen'):
            PREVIEW._alignment_reviews([fixture['report_path']] * 17,
                                       [fixture['motion']], [fixture['song']], [fixture['job']])


if __name__ == '__main__':
    unittest.main()

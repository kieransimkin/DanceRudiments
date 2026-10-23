"""Synthetic complete-Action confidence and separate loop-candidate regressions.

No music, mesh, external model, downloads or third-party motion files.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

from dancerudiments_authoring.full_motion_analysis import assess_full_motion, METHOD
from dancerudiments_authoring.motion import load_rig_motion
from dancerudiments_authoring.source_loop_analysis import analyse_source_capture, _native_check
from test_source_loop_analysis import fixture, fake_stemlab


def fake_rhythmic_stemlab(*, weak=False):
    modules = fake_stemlab()
    analyser = modules['stemlab.analysis.rig_motion']
    underlying = analyser.analyze_rig_capture

    def analyze(path, *, min_bpm, max_bpm):
        result = underlying(path, min_bpm=min_bpm, max_bpm=max_bpm)
        result['recommended_tempo'] = dict(bpm=120., beat_zero_seconds=.12,
            score=.95 if not weak else .04,
            group_periodicity=.96 if not weak else .02,
            autocorrelation=.91 if not weak else .03,
            phase_contrast=.72 if not weak else .02,
            active_control_groups=3, supporting_control_groups=3 if not weak else 1)
        result['bpm_candidates'] = [result['recommended_tempo']]
        result['motion_accents'] = [dict(seconds=.12+.5*i, strength=.94)
                                    for i in range(32)] if not weak else [
                                        dict(seconds=i*.97, strength=.8) for i in range(7)]
        return result

    analyser.analyze_rig_capture = analyze
    return modules


class FullMotionConfidenceTests(unittest.TestCase):
    def test_rhythmic_complete_action_surpasses_default_seventy_percent(self):
        capture = fixture()
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(sys.modules, fake_rhythmic_stemlab()):
            root = Path(folder)/'result'
            result = analyse_source_capture(capture, root,
                                            original_source_sha256='c'*64,
                                            target_bpm=124., max_previews=2)
            fit = result['full_motion_fit']
            self.assertEqual(fit['method'], METHOD)
            self.assertGreaterEqual(fit['confidence'], .70)
            self.assertEqual(fit['selected_bpm'], 120)
            self.assertTrue(fit['auto_convert'])
            self.assertEqual(result['full_motion_count'], 1)
            self.assertEqual(result['loopable_clip_count'], 1)
            self.assertEqual(result['preview_count'], 1)  # compatibility alias
            full = result['full_motion_clips'][0]
            self.assertFalse(full['loopable'])
            self.assertTrue(full['requires_review'])
            self.assertEqual(full['source_original_sha256'], 'c'*64)
            self.assertEqual(full['source_capture_sha256'], result['source_capture_sha256'])
            self.assertFalse(full['audio_beat_alignment_verified'])
            self.assertLessEqual(full['omitted_head_seconds'], 60/120/64+.000001)
            self.assertLessEqual(full['omitted_tail_seconds'], 60/120/64+.000001)
            recording = load_rig_motion(root/full['filename'])
            self.assertEqual(recording.profile.fingerprint, capture.profile.fingerprint)
            self.assertEqual(recording.recording.clock.bpm, 124.)
            self.assertEqual(recording.recording.clock.bpm_status, 'estimated')
            self.assertEqual(recording.recording.clock.start_pip, full['start_pip'])
            self.assertEqual(len(recording.recording.samples), full['sample_count'])
            self.assertEqual(recording.recording.provenance['motion_kind'], 'source_full_action')
            self.assertEqual(recording.recording.provenance['loop_policy'], 'non_looping')
            self.assertEqual(recording.recording.provenance['source_original_sha256'], 'c'*64)
            self.assertEqual(recording.recording.provenance['grid_fit_method'], METHOD)
            loop = load_rig_motion(root/result['loopable_clips'][0]['filename'])
            self.assertEqual(loop.recording.provenance['motion_kind'], 'source_loop_candidate')
            self.assertEqual(loop.recording.provenance['loop_policy'], 'non_looping')
            self.assertEqual(loop.recording.provenance['suggested_loop_period_pips'], 256)
            catalog = json.loads((root/result['loopable_catalogue_file']).read_text())
            self.assertEqual(catalog['clips'][0]['filename'], result['previews'][0]['filename'])
            with self.assertRaises(FileExistsError):
                analyse_source_capture(capture, root)

    def test_poor_whole_action_fit_does_not_block_local_loop_candidates(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(sys.modules, fake_rhythmic_stemlab(weak=True)):
            result = analyse_source_capture(fixture(), Path(folder)/'result')
            self.assertLess(result['full_motion_fit']['confidence'], .7)
            self.assertEqual(result['full_motion_count'], 0)
            self.assertEqual(result['loopable_clip_count'], 1)
            self.assertFalse((Path(folder)/'result'/'full-length').exists())
            self.assertTrue((Path(folder)/'result'/'loopable-clips.json').is_file())

    def test_high_threshold_and_explicit_disable_are_independent_of_loop_export(self):
        for params in ({'full_motion_confidence_threshold': 1.},
                       {'export_full_motion': False}):
            with self.subTest(params=params), tempfile.TemporaryDirectory() as folder, mock.patch.dict(
                    sys.modules, fake_rhythmic_stemlab()):
                result = analyse_source_capture(fixture(), Path(folder)/'result', **params)
                self.assertEqual(result['full_motion_count'], 0)
                self.assertEqual(result['loopable_clip_count'], 1)

    def test_invalid_threshold_fails_before_output_mutation(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(sys.modules, fake_rhythmic_stemlab()):
            root = Path(folder)/'result'
            for threshold in (-.1, 1.1, float('nan'), True):
                with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                    analyse_source_capture(fixture(), root, full_motion_confidence_threshold=threshold)
                self.assertFalse(root.exists())

    def test_native_absolute_pips_support_nonzero_full_action_start(self):
        rows=[(-1.,), (0.,), (.5,), (1.,)]
        start=-56
        player=SimpleNamespace(start_pip=start,sample_count=len(rows),
            sample=lambda pip:rows[pip-start])
        profile=SimpleNamespace(decode=lambda normalized:normalized)
        motion=SimpleNamespace(recording=SimpleNamespace(samples=rows,
            clock=SimpleNamespace(start_pip=start)),profile=profile,
            player=lambda:player)
        self.assertTrue(_native_check(motion))

    def test_missing_motion_tempo_and_corrupt_grid_are_not_auto_converted(self):
        capture=fixture()
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(sys.modules, fake_rhythmic_stemlab()):
            src=Path(folder)/'result'
            report=analyse_source_capture(capture, src, export_full_motion=False)
            evidence=json.loads((src/'stemlab-analysis.json').read_text())
            good=assess_full_motion(evidence, capture)
            self.assertGreaterEqual(good['confidence'], .7)
            evidence['estimated_beat_map']['bpm_status']='confirmed'
            bad=assess_full_motion(evidence, capture)
            self.assertFalse(bad['auto_convert'])
            self.assertEqual(bad['reasons'],['missing_or_inconsistent_source_beat_map'])
            evidence['estimated_beat_map']['bpm_status']='estimated'
            evidence['recommended_tempo']=None
            missing=assess_full_motion(evidence, capture)
            self.assertFalse(missing['auto_convert'])
            self.assertEqual(missing['reasons'],['no_supported_stemlab_tempo'])


if __name__ == '__main__':
    unittest.main()

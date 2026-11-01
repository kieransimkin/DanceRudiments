"""Source-time completion integration: evidence, bounded derivatives and exports.

Only synthetic BVH/Blender-index/ZIP fixtures are used. The optional StemLab
checks exercise its actual analysis and event adapter; they never fetch assets.
"""
from __future__ import annotations

import argparse
import contextlib
from dataclasses import replace
import hashlib
import importlib.util
import inspect
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from dancerudiments_authoring._validation import ScoreError, canonical_json
from dancerudiments_authoring.motion import load_rig_motion
from dancerudiments_authoring.motion_import import (
    compile_capture, load_capture, write_capture,
)
from dancerudiments_authoring.source_loop_analysis import (
    _finish_loop_candidates, analyse_source_capture, source_capture_from_bvh,
)


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))
from source_motion_options import add_completion_arguments, completion_options


def tool(name):
    spec = importlib.util.spec_from_file_location('completion_' + name, TOOLS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def synthetic_bvh():
    """Eight seconds of 120-BPM accents, slight travel and stationary feet.

    The full three-dimensional rest hierarchy makes this a portable source
    skeleton, so actual world/contact evidence can be independently evaluated.
    """
    hierarchy = '''HIERARCHY
ROOT Root
{
 OFFSET 0 0 1
 CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation
 JOINT LeftFoot
 {
  OFFSET -0.3 0 -1
  CHANNELS 3 Xposition Yposition Zposition
  End Site { OFFSET 0 0.2 0 }
 }
 JOINT RightFoot
 {
  OFFSET 0.3 0 -1
  CHANNELS 3 Xposition Yposition Zposition
  End Site { OFFSET 0 0.2 0 }
 }
 JOINT Arm
 {
  OFFSET 0 0 0.7
  CHANNELS 3 Zrotation Xrotation Yrotation
  End Site { OFFSET 0.5 0 0 }
 }
 JOINT Knee
 {
  OFFSET 0 0 -0.5
  CHANNELS 3 Zrotation Xrotation Yrotation
  End Site { OFFSET 0.2 0 -0.4 }
 }
}
MOTION
Frames: 513
Frame Time: 0.015625
'''
    rows = []
    for index in range(513):
        t = index / 64
        pulse = .85 * math.exp(-((t % .5 - .12) / .065)**2)
        arm = 40 * (pulse + .12 * math.sin(math.tau * t / 2))
        knee = 2 * math.sin(math.tau * t / 2 + .4)
        # Each foot cancels the small original root travel in world space.
        travel = .004 * t
        rows.append((travel, 0, 0, 0, 0, 0, -travel, 0, 0, -travel, 0, 0,
                     arm, 0, 0, knee, 0, 0))
    return hierarchy + '\n'.join(' '.join(map(str, row)) for row in rows) + '\n'


def portable_capture():
    from dancerudiments_authoring.bvh_import import parse_bvh
    clip = parse_bvh(synthetic_bvh(), source_id='completion_fixture',
                     axis_forward='Y', axis_up='Z', location_range=2.)
    capture = source_capture_from_bvh(clip, calibration_frames=1,
        source_provenance={'source_license': {'id': 'CC0-1.0',
                                            'attribution': 'Synthetic completion regression'},
                           'member': 'dance/fixture.bvh'})
    return clip, capture


def require_stemlab(case):
    try:
        from stemlab.analysis.rig_motion import analyze_rig_capture
        from stemlab.analysis.motion_alignment import events_from_rig_report  # noqa: F401
        if 'world_motion' not in inspect.signature(analyze_rig_capture).parameters:
            raise ImportError('StemLab has no source-world evidence interface')
    except ImportError as exc:
        if os.environ.get('DANCERUDIMENTS_REQUIRE_STEMLAB') == '1':
            case.fail(f'Compatible StemLab integration is required: {exc}')
        case.skipTest('Compatible StemLab source-world/event integration is optional')


def require_native(case):
    try:
        import dancerudiments  # noqa: F401
    except ImportError as exc:
        if os.environ.get('DANCERUDIMENTS_REQUIRE_NATIVE') == '1':
            case.fail(f'Native sample verification is required: {exc}')
        case.skipTest('Native Python extension is not built')


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'Optional NumPy is required')
class SourceMotionCompletionTests(unittest.TestCase):
    def test_source_gaps_cannot_be_filled_by_events_full_actions_or_loop_exports(self):
        require_stemlab(self)
        _, original = portable_capture()
        indices = [i for i, t in enumerate(original.frame_times_seconds) if not 2. < t < 2.2]
        source = replace(original,
            frame_times_seconds=tuple(original.frame_times_seconds[i] for i in indices),
            frames=tuple(original.frames[i] for i in indices))
        for world_space in (True, False):
            with self.subTest(world_space=world_space), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'gap-analysis'
                result = analyse_source_capture(source, output, world_space=world_space,
                    tempo_strategy='control', min_bpm=100, max_bpm=140,
                    full_motion_confidence_threshold=0., max_previews=4,
                    repair_loops=True, max_repairs=3)
                self.assertEqual(result['full_motion_count'], 0)
                self.assertIn('source_time_gaps_prevent_complete_conversion',
                              result['full_motion_fit']['reasons'])
                coverage = result['source_valid_segments_seconds']
                self.assertEqual(len(coverage), 2)
                for clip in result['loopable_clips'] + result['repaired_loop_clips']:
                    self.assertTrue(any(a <= clip['source_start_seconds'] <
                        clip['source_end_seconds'] <= b for a, b in coverage))
                events = read(output / 'motion-events.json')
                self.assertEqual(events['source']['valid_segments_seconds'], [list(x) for x in coverage])
                for stream in events['streams']:
                    self.assertTrue(all(any(a <= e['seconds'] <= b for a, b in coverage)
                                        for e in stream['events']))
                # A pose-valid upstream proposal still cannot cross the gap.
                report = read(output / 'stemlab-analysis.json')
                bpm = report['recommended_tempo']['bpm']
                report['loop_candidates'] = [dict(start_seconds=1.,
                    end_seconds=1.+240./bpm, beats=4, score=.95,
                    alignment='estimated_motion_beat_grid', requires_review=True,
                    repaired=False, evidence='repeated_and_seam',
                    pose_mismatch=.001, velocity_mismatch=.001, root_drift_relative=0.)]
                from dancerudiments_authoring.source_loop_analysis import _preview_eligible
                accepted, rejected = _preview_eligible(report, source, target_bpm=None)
                self.assertFalse(accepted)
                self.assertEqual(rejected[0]['reason'], 'crosses_source_time_gap')

    def test_world_events_and_repaired_catalogue_bind_to_original_source(self):
        require_stemlab(self)
        require_native(self)
        clip, source = portable_capture()
        original = source.to_dict()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'analysis'
            result = analyse_source_capture(source, output,
                original_source_sha256=clip.source_sha256, min_bpm=100, max_bpm=140,
                tempo_strategy='control', export_full_motion=False, max_previews=2,
                repair_loops=True, max_repairs=2, verify_native=True)
            digest = sha(output / 'source.capture.json')
            world = read(output / result['world_motion_evidence_file'])
            events = read(output / result['motion_events_file'])
            analysis = read(output / result['stemlab_analysis_file'])
            self.assertTrue(result['world_motion_supported'])
            self.assertEqual(result['source_capture_sha256'], digest)
            self.assertEqual(world['source_file_sha256'], digest)
            self.assertEqual(world['capture_sha256'], source.fingerprint)
            self.assertEqual(world['profile_sha256'], source.profile.fingerprint)
            self.assertEqual(events['source']['sha256'], digest)
            self.assertEqual(events['source']['clock_id'], 'source_capture_seconds')
            self.assertEqual(events['source']['seconds_range'],
                             [source.frame_times_seconds[0], source.frame_times_seconds[-1]])
            self.assertEqual(events['provenance']['profile_sha256'], source.profile.fingerprint)
            self.assertEqual(events['provenance']['analysis_sha256'],
                hashlib.sha256(canonical_json(analysis).encode('ascii')).hexdigest())
            observed = next(x for x in events['streams'] if x['id'] == 'control_accents')
            expected = analysis.get('control_evidence', analysis)['motion_accents']
            self.assertEqual([x['seconds'] for x in observed['events']],
                             sorted({x['seconds'] for x in expected}))
            self.assertFalse(events['music_timing_verified'])
            self.assertTrue(all(x['event_type'] != 'predicted_grid' for x in events['streams']))
            self.assertEqual(source.to_dict(), original)
            self.assertEqual(load_capture(output / 'source.capture.json').to_dict(), original)

            raw = read(output / 'loopable-clips.json')
            repaired = read(output / 'loop-repairs.json')
            self.assertGreater(result['repaired_loop_count'], 0, repaired['attempts'])
            self.assertEqual(raw['clips'], result['loopable_clips'])
            self.assertEqual(repaired['clips'], result['repaired_loop_clips'])
            self.assertFalse({x['filename'] for x in raw['clips']} &
                             {x['filename'] for x in repaired['clips']})
            self.assertTrue(all(x['filename'].startswith('previews/') for x in raw['clips']))
            self.assertFalse(result['full_motion_count'])
            self.assertFalse(result['inferred_tempo_verified'])
            self.assertFalse(result['confirmed_musical_downbeat'])
            for entry in repaired['clips']:
                motion = load_rig_motion(output / entry['filename'])
                corrected = load_capture(output / entry['corrected_capture_file'])
                repair = read(output / entry['repair_report_file'])
                provenance = motion.recording.provenance
                self.assertEqual(repair['compiled_motion_sha256'], sha(output / entry['filename']))
                self.assertEqual(entry['repair_report_sha256'], sha(output / entry['repair_report_file']))
                self.assertEqual(repair['compiled_verification']['compiled_motion_fingerprint'],
                                 motion.fingerprint)
                self.assertTrue(repair['compiled_verification']['passed'])
                self.assertEqual(provenance['original_source_sha256'], clip.source_sha256)
                self.assertEqual(provenance['original_capture_sha256'], source.fingerprint)
                self.assertEqual(provenance['source_capture_sha256'], corrected.fingerprint)
                self.assertEqual(provenance['corrected_capture_sha256'], corrected.fingerprint)
                self.assertEqual(provenance['repair_id'], repair['repair_id'])
                self.assertEqual(corrected.provenance['source_provenance'], source.provenance)
                self.assertEqual(motion.profile.fingerprint, source.profile.fingerprint)
                self.assertEqual(len(motion.recording.samples), entry['source_beats'] * 64)
                self.assertTrue(entry['native_samples_verified'])
                self.assertTrue(entry['numerical_repeat_seam_verified'])
                self.assertTrue(entry['requires_review'])
                for flag in ('loop_seam_approved', 'audio_beat_alignment_verified',
                             'mesh_deformation_verified'):
                    self.assertFalse(entry[flag])

    def test_bad_compiled_payload_is_not_exported_and_later_candidate_survives(self):
        require_native(self)
        from dancerudiments_authoring.loop_repair import propose_loop_repairs
        _, source = portable_capture()
        proposals = propose_loop_repairs(source, bpm=120., max_candidates=2)
        self.assertEqual(sum(x.accepted for x in proposals), 2)
        for failure in ('wrong_rate', 'compiler_error'):
            calls = 0

            def fail_first(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    if failure == 'compiler_error':
                        raise ScoreError('Synthetic compiler rejection')
                    # A valid compile at the wrong rate retains its provenance,
                    # yet genuinely changes decoded samples and the repeat seam.
                    kwargs['motion_rate'] = .5
                return compile_capture(*args, **kwargs)

            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory, mock.patch(
                    'dancerudiments_authoring.source_loop_analysis.compile_capture', side_effect=fail_first):
                root = Path(directory)
                clips, attempts = _finish_loop_candidates(source, root,
                    {'selected_bpm': 120., 'selected_beat_zero_seconds': 0.},
                    {'supported': False}, max_repairs=2, options=None,
                    target_bpm=None, verify_native=True, original_sha256='a' * 64)
                self.assertEqual(calls, 2)
                self.assertFalse(attempts[0]['accepted'])
                if failure == 'wrong_rate':
                    self.assertFalse(attempts[0]['compiled_verification']['passed'])
                else:
                    self.assertEqual(attempts[0]['status'], 'compilation_rejected')
                self.assertTrue(attempts[1]['compiled_verification']['passed'])
                self.assertTrue(attempts[1]['accepted'])
                self.assertEqual(len(clips), 1)
                self.assertIn('repaired_002_', clips[0]['filename'])
                self.assertFalse(list(root.rglob('repaired_001_*')))
                self.assertEqual(len(list(root.rglob('*.motion.json'))), 1)
                self.assertEqual(len(list(root.rglob('*.capture.json'))), 1)
                self.assertEqual(len(list(root.rglob('*.repair.json'))), 1)

    def test_reviewed_archive_and_blender_index_keep_source_provenance(self):
        require_stemlab(self)
        collection = tool('analyze_motion_collection')
        batch = tool('analyze_blender_capture_batch')
        content = synthetic_bvh().encode()
        original_sha = hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'reviewed.zip'
            with zipfile.ZipFile(archive, 'w') as stream:
                stream.writestr('dance/fixture.bvh', content)
            license_info = {'id': 'CC0-1.0', 'attribution': 'Synthetic completion regression'}
            plan = {'id': 'completion_fixture', 'license': license_info,
                'conversion': {'axis_forward': 'Y', 'axis_up': 'Z', 'location_range': 2.},
                'archives': [{'cache_path': archive.name, 'sha256': sha(archive),
                              'size_bytes': archive.stat().st_size,
                              'members': {'dance/fixture.bvh': {
                                  'sha256': original_sha, 'calibration_frame_count': 1}}}]}
            original_archive = archive.read_bytes()
            output = root / 'collection'
            report = collection.analyze_collection([plan], root, output,
                min_bpm=100, max_bpm=140, tempo_strategy='control', max_previews=0,
                export_full_motion=False, repair_loops=True, max_repairs=1)
            self.assertEqual(report['failed_action_count'], 0, report['failures'])
            self.assertEqual(report['analysed_action_count'], 1)
            self.assertGreater(report['repaired_loop_count'], 0)
            self.assertFalse(report['loopable_shortlist'])
            item = report['repaired_loop_shortlist'][0]
            action = output / item['relative_output']
            capture = load_capture(action / 'source.capture.json')
            self.assertEqual(capture.provenance['source_license'], license_info)
            self.assertEqual(capture.provenance['archive_sha256'], sha(archive))
            self.assertEqual(capture.provenance['member'], 'dance/fixture.bvh')
            self.assertEqual(capture.provenance['source_sha256'], original_sha)
            self.assertEqual(item['source_sha256'], original_sha)
            self.assertEqual(archive.read_bytes(), original_archive)
            self.assertTrue((action / item['repair_report_file']).is_file())

            # A model extraction index has a different original file identity;
            # the batch API must carry it through every corrected derivative.
            extracted = root / 'extracted'
            extracted.mkdir()
            capture = replace(capture, provenance_json=canonical_json(dict(
                capture.provenance, source_file={'filename': 'synthetic.glb', 'sha256': 'b' * 64})))
            write_capture(extracted / 'action.capture.json', capture)
            index = {'format': 'dancerudiments.blender-import', 'schema_version': 1,
                'source': {'filename': 'synthetic.glb', 'sha256': 'b' * 64},
                'captures': [{'capture': 'action.capture.json', 'binding_id': 'synthetic_action',
                              'profile_sha256': capture.profile.fingerprint}]}
            (extracted / 'index.json').write_text(json.dumps(index))
            batch_output = root / 'batch'
            result = batch.analyse_batch(extracted / 'index.json', batch_output,
                tempo_strategy='control', max_previews=0, min_full_confidence=1.,
                repair_loops=True, max_repairs=1)
            self.assertEqual(result['failed_action_count'], 0, result['failures'])
            self.assertGreater(result['repaired_loop_count'], 0)
            self.assertFalse(result['loopable_shortlist'])
            selected = result['repaired_loop_shortlist'][0]
            self.assertEqual(selected['original_source_sha256'], 'b' * 64)
            derivative = load_rig_motion(batch_output / selected['relative_output'] / selected['filename'])
            self.assertEqual(derivative.recording.provenance['original_source_sha256'], 'b' * 64)
            self.assertEqual(load_capture(extracted / 'action.capture.json').fingerprint,
                             capture.fingerprint)

    def test_real_benchmark_surface_keeps_private_derivatives_out_of_summary(self):
        require_stemlab(self)
        require_native(self)
        benchmark = tool('evaluate_real_rig_motions')
        clip, _ = portable_capture()
        scene = {'id': 'synthetic', 'source': {'id': 'synthetic', 'title': 'Synthetic only',
            'sha256': clip.source_sha256, 'source_url': 'https://example.invalid/fixture.bvh',
            'calibration_frame_count': 1}}
        recipe = {'scenes': [scene], 'mirror_commit': 'c' * 40, 'license': {'id': 'CC0-1.0'}}
        with tempfile.TemporaryDirectory() as directory, mock.patch(
                'build_mesh_demo_assets.load_sources', return_value=recipe), mock.patch(
                'build_mesh_demo_assets._prepare_clip', return_value=clip), mock.patch(
                'acquire_cmu_dance._ensure_file') as ensure:
            root = Path(directory)
            output = root / 'summary'
            result = benchmark.evaluate(output, root / 'cache',
                download=False, max_previews=0, tempo_strategy='control',
                repair_loops=True, max_repairs=1)
            self.assertEqual(result['failed_scene_count'], 0)
            self.assertGreater(result['total_corrected_loops'], 0)
            self.assertTrue(result['scenes'][0]['world_motion_supported'])
            self.assertFalse(result['scenes'][0]['beat_alignment_confirmed'])
            ensure.assert_called_once_with((root / 'cache').resolve(), scene['source'], download=False)
            self.assertEqual({p.name for p in output.iterdir()}, {'summary.json'})
            def keys(value):
                if isinstance(value, dict):
                    return set(value).union(*(keys(v) for v in value.values()))
                if isinstance(value, list):
                    return set().union(*(keys(v) for v in value))
                return set()
            self.assertFalse(keys(result) & {'frames', 'samples', 'recording', 'motion'})

    def test_invalid_cli_options_are_rejected_without_an_analysis_directory(self):
        cli = tool('analyze_source_motion')
        _, capture = portable_capture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.capture.json'
            write_capture(source, capture)
            options = root / 'repair-options.json'
            cases = [({'invented_setting': True}, ['--repair-loops'], 'Unknown loop correction'),
                     ({'contact_policy': 'teleport'}, ['--repair-loops'], 'contact_policy'),
                     ([], ['--repair-loops'], 'JSON object'),
                     ({}, [], 'requires --repair-loops')]
            for document, flags, expected in cases:
                options.write_text(json.dumps(document))
                errors = io.StringIO()
                with self.subTest(document=document, flags=flags), contextlib.redirect_stderr(errors), \
                        self.assertRaises(SystemExit) as caught:
                    cli.main([str(source), '--output-dir', str(root / 'analysis'),
                              '--repair-options', str(options), *flags])
                self.assertEqual(caught.exception.code, 2)
                self.assertIn(expected, errors.getvalue())
                self.assertNotIn('Traceback', errors.getvalue())
                self.assertFalse((root / 'analysis').exists())
            # The benchmark entry point must reject settings before source
            # acquisition or expensive analysis, with the same CLI error shape.
            benchmark = tool('evaluate_real_rig_motions')
            options.write_text(json.dumps({'invented_setting': True}))
            errors = io.StringIO()
            with mock.patch.object(benchmark, 'evaluate') as evaluate, \
                    contextlib.redirect_stderr(errors), self.assertRaises(SystemExit) as caught:
                benchmark.main(['--output-dir', str(root / 'benchmark'),
                                '--repair-loops', '--repair-options', str(options)])
            self.assertEqual(caught.exception.code, 2)
            self.assertIn('Unknown loop correction', errors.getvalue())
            evaluate.assert_not_called()
            self.assertFalse((root / 'benchmark').exists())

    def test_no_implicit_repair_and_missing_world_cannot_claim_world_strategy(self):
        parser = argparse.ArgumentParser()
        add_completion_arguments(parser)
        defaults = completion_options(parser.parse_args([]))
        self.assertFalse(defaults['repair_loops'])
        self.assertTrue(defaults['world_space'])
        self.assertEqual(defaults['tempo_strategy'], 'consensus')
        for arguments in (['--max-repairs', '0'], ['--max-repairs', '13'],
                          ['--no-world-space', '--tempo-strategy', 'world'],
                          ['--no-world-space', '--tempo-strategy', 'contact']):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                completion_options(parser.parse_args(arguments))
        _, capture = portable_capture()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'analysis'
            # Dependency loading is irrelevant: this explicit strategy cannot
            # obtain world evidence when the user has disabled its evaluation.
            with mock.patch('dancerudiments_authoring.source_loop_analysis._stemlab',
                            return_value=(mock.Mock(), mock.Mock())):
                with self.assertRaisesRegex(ValueError, 'source-world'):
                    analyse_source_capture(capture, output, world_space=False, tempo_strategy='world')
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()

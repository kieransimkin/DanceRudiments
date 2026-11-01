"""Actual source→repair→review→package→native reload; synthetic fixtures only."""
import importlib.util
import json
import math
import os
import wave
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from dancerudiments_authoring._validation import ScoreError
from dancerudiments_authoring.loop_review import (
    audio_seconds_to_pip,
    create_loop_review,
    document_hash,
    export_reviewed_loop,
    file_hash,
    finish_review_selection,
    load_reviewed_loop,
    load_selection,
    read_review,
    validate_loop_review,
    write_review,
)
from dancerudiments_authoring.motion import RigMotion
from dancerudiments_authoring.motion_import import write_capture
from dancerudiments_authoring.motion_packages import (
    MotionPackage,
    export_motion_package,
    install_motion_package,
)
from test_loop_repair import fixture

pytestmark = pytest.mark.skipif(importlib.util.find_spec('numpy') is None,
                               reason='optional motion-import NumPy dependency unavailable')


def require_runtime():
    if importlib.util.find_spec('dancerudiments') is None:
        if os.environ.get('DANCERUDIMENTS_REQUIRE_NATIVE') == '1':
            pytest.fail('Native runtime is required')
        pytest.skip('Native runtime is optional')


def require_stemlab():
    try:
        from stemlab.analysis.motion_alignment import validate_alignment_revision  # noqa: F401
    except ImportError:
        if os.environ.get('DANCERUDIMENTS_REQUIRE_STEMLAB') == '1':
            pytest.fail('StemLab timing review integration is required')
        pytest.skip('Compatible StemLab is optional')


def resign(document, field):
    value = deepcopy(document)
    value.pop(field)
    value[field] = document_hash(value)
    return value


@pytest.fixture
def selection(tmp_path):
    require_runtime()
    source = tmp_path / 'original.capture.json'
    write_capture(source, fixture())
    selected = tmp_path / 'selection'
    manifest = finish_review_selection(source, selected, start_seconds=0., end_seconds=2.,
        beats=4, original_source_sha256='1' * 64, repair_options={'translation_scale': 1.})
    return selected, manifest, source


@pytest.fixture
def timing(tmp_path, selection):
    require_stemlab()
    from stemlab.analysis.motion_alignment import (
        align_motion_audio,
        create_alignment_revision,
        make_event_evidence,
        write_document,
    )
    _directory, _manifest, source = selection
    audio = tmp_path / 'synthetic-master.wav'
    with wave.open(str(audio), 'wb') as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(8000)
        stream.writeframes(b'\x00\x00' * 32000)
    times = [.1, .23, .42, .63, .9, 1.04, 1.3, 1.63, 1.82]
    def evidence(kind, path, times, end):
        return make_event_evidence(kind=kind, source_sha256=file_hash(path),
            clock_id=kind + '_source_seconds', seconds_range=[0., end],
            streams=[{'id': 'synthetic_events', 'family': 'synthetic_fixture',
                      'event_type': 'human_annotation',
                      'events': [{'seconds': t, 'strength': 1.} for t in times]}])
    motion = evidence('motion', source, times, 2.)
    sound = evidence('audio', audio, [t + .25 for t in times], 4.)
    clock = {'format': 'stemlab.motion-clock-map.v1', 'schema_version': 1,
        'motion_source_sha256': file_hash(source), 'audio_source_sha256': file_hash(audio),
        'motion_clock_id': 'motion_source_seconds', 'audio_clock_id': 'audio_source_seconds',
        'motion_origin_seconds': 0., 'audio_origin_seconds': 0., 'seconds_scale': 1.,
        'relationship': 'creative_retiming'}
    report = align_motion_audio(motion, sound, clock, motion_source=source,
        audio_source=audio, variable_tempo=False, max_offset_seconds=.5, rate_multipliers=[1.])
    report_path, revision_path = tmp_path / 'alignment.json', tmp_path / 'timing-review.json'
    write_document(report_path, report)
    revision = create_alignment_revision(report, report_sha256=file_hash(report_path),
        candidate_id=report['candidates'][0]['candidate_id'], reviewer='Automated synthetic regression',
        manual_anchors=[{'motion_seconds': 0., 'audio_seconds': .25},
                        {'motion_seconds': .8, 'audio_seconds': 1.15},
                        {'motion_seconds': 2., 'audio_seconds': 2.75}])
    write_document(revision_path, revision)
    return report_path, revision_path, audio


TARGET = {'id': 'synthetic_target', 'asset_sha256': 'a' * 64,
          'rig_sha256': 'b' * 64, 'calibration_sha256': 'c' * 64}


def review_for(selection, timing, **kwargs):
    report, revision, audio = timing
    return create_loop_review(selection[0], alignment_report_path=report,
        timing_revision_path=revision, audio_source_path=audio, target=TARGET,
        reviewer='Automated synthetic regression', verdicts={'seam': 'accept', 'feet': 'accept', 'skin': 'accept'},
        review_kind='automated_test', **kwargs)


def export(directory, review, output, audio, **kwargs):
    return export_reviewed_loop(directory, review, output, audio_source_path=audio,
        expected_target=TARGET, package_id='review_fixture', version='1.0.0', title='Synthetic reviewed fixture',
        license={'id': 'CC0-1.0', 'url': 'https://creativecommons.org/publicdomain/zero/1.0/',
                 'attribution': 'Synthetic test movement; no choreography approval'},
        provenance={'source': 'deterministic synthetic regression'}, **kwargs)


def test_explicit_finish_preserves_source_and_half_open_native_grid(selection):
    directory, manifest, original = selection
    assert (directory / 'source.capture.json').read_bytes() == original.read_bytes()
    assert manifest['sample_count'] == 256
    assert manifest['requires_review'] and manifest['numerical_seam_verified']
    assert manifest['native_samples_verified']
    assert load_selection(directory, verify_native=True) == manifest
    motion = read_review(directory / 'finished.motion.json')
    assert len(motion['recording']['samples']) == 256
    assert len(read_review(directory / 'corrected.capture.json')['frames']) == 257
    assert motion['recording']['provenance']['musical_timing_verified'] is False
    with pytest.raises(FileExistsError):
        finish_review_selection(original, directory, start_seconds=0., end_seconds=2., beats=4,
            original_source_sha256='1' * 64, repair_options={'translation_scale': 1.})


def test_full_review_roundtrip_package_and_native_audio_clock(selection, timing, tmp_path):
    directory, _manifest, _ = selection
    review = review_for(selection, timing)
    assert review['human_approved'] is False
    assert review['status'] == 'automated_test_fixture'
    saved = tmp_path / 'decision.json'
    write_review(saved, review)
    assert validate_loop_review(directory, saved, audio_source_path=timing[2], expected_target=TARGET) == review
    with pytest.raises(ScoreError, match='Export requires'):
        export(directory, review, tmp_path / 'refused', timing[2])
    packaged = tmp_path / 'package'
    result = export(directory, review, packaged, timing[2], allow_test_review=True)
    assert result['clips'][0]['metadata']['human_approved'] is False
    assert result['clips'][0]['metadata']['timing_kind'] == 'time-only'
    archive = export_motion_package(packaged, tmp_path / 'package.zip')
    installed = install_motion_package(archive, tmp_path / 'installed')
    original = RigMotion.from_dict(read_review(directory / 'finished.motion.json'))
    with MotionPackage(installed) as package:
        assert package.load(original.name).fingerprint == original.fingerprint
    player = load_reviewed_loop(installed, original.name, allow_test_review=True)
    native = original.player()
    for seconds in [.25, .625, 1.15, 1.6, math.nextafter(2.75, -math.inf)]:
        pip = audio_seconds_to_pip(review, seconds)
        assert player.sample_audio(seconds) == pytest.approx(native.sample(pip), abs=1e-12)
    assert player.sample_audio(2.75) is None
    assert player.sample_audio(.249) is None
    assert player.sample_audio(2.75, repeat=True) == pytest.approx(native.sample(0), abs=1e-12)
    files = {str(p.relative_to(packaged)) for p in packaged.rglob('*') if p.is_file()}
    assert not files & {'source.capture.json', 'synthetic-master.wav', 'corrected.capture.json', 'repair.json'}
    assert {'README.md', 'LICENSE.txt', 'THIRD_PARTY_NOTICES.md', 'SOURCES.json'} <= files
    # Metadata preserves the exact report bytes, including serialization.
    assert review['timing']['report']['json'].encode() == timing[0].read_bytes()


def test_variable_clock_half_open_boundaries_and_repeat(selection, timing):
    review = review_for(selection, timing)
    assert audio_seconds_to_pip(review, .25) == 0
    assert audio_seconds_to_pip(review, 1.15) == 102
    assert audio_seconds_to_pip(review, 2.75) is None
    assert audio_seconds_to_pip(review, math.nextafter(2.75, -math.inf)) == 255
    assert audio_seconds_to_pip(review, 2.75, repeat=True) == 0
    assert audio_seconds_to_pip(review, 5.25, repeat=True) == 0
    assert audio_seconds_to_pip(review, .1, repeat=True) is None
    with pytest.raises(ScoreError):
        audio_seconds_to_pip(review, float('nan'))


def test_audio_identity_target_changes_and_unreviewed_visuals_block_export(selection, timing, tmp_path):
    review = review_for(selection, timing)
    wrong = tmp_path / 'other.wav'; wrong.write_bytes(b'other exact audio bytes')
    with pytest.raises(ScoreError, match='audio master bytes'):
        validate_loop_review(selection[0], review, audio_source_path=wrong)
    changed_target = dict(TARGET, calibration_sha256='d' * 64)
    with pytest.raises(ScoreError, match='calibration changed'):
        validate_loop_review(selection[0], review, expected_target=changed_target)
    changed = deepcopy(review); changed['verdicts']['feet'] = 'unreviewed'; changed['status'] = 'needs_review'
    changed = resign(changed, 'review_id')
    validate_loop_review(selection[0], changed)
    with pytest.raises(ScoreError, match='Export requires'):
        export(selection[0], changed, tmp_path / 'unreviewed', timing[2], allow_test_review=True)


def test_changed_boundaries_or_beat_count_invalidates_review(selection, timing, tmp_path):
    review = review_for(selection, timing)
    for index, (start, end, beats) in enumerate([(0., 2., 2), (.01, 1.99, 4)]):
        directory = tmp_path / ('changed_' + str(index))
        finish_review_selection(selection[2], directory, start_seconds=start, end_seconds=end, beats=beats,
            original_source_sha256='1' * 64, repair_options={'translation_scale': 1.})
        with pytest.raises(ScoreError, match='different source/selection'):
            validate_loop_review(directory, review)


def test_saved_revision_chain_and_changed_timing_are_bound(selection, timing, tmp_path):
    first = review_for(selection, timing)
    path = tmp_path / 'review-1.json'; write_review(path, first)
    second = review_for(selection, timing, previous_review=path, notes='Repeat and feet checked in a synthetic test')
    assert second['revision'] == 2
    assert second['previous_review_sha256'] == document_hash(first)
    validate_loop_review(selection[0], second, previous_review=first)
    changed = deepcopy(second)
    timing_revision = json.loads(changed['timing']['revision']['json'])
    timing_revision['mapping_segments'][0]['anchors'][1]['audio_seconds'] += .1
    changed['timing']['revision']['json'] = json.dumps(timing_revision)
    import hashlib
    changed['timing']['revision']['sha256'] = hashlib.sha256(changed['timing']['revision']['json'].encode()).hexdigest()
    changed = resign(changed, 'review_id')
    with pytest.raises(ScoreError, match='Saved playback differs'):
        validate_loop_review(selection[0], changed)
    with pytest.raises(FileExistsError):
        write_review(path, first)


def test_changed_exact_report_bytes_duplicate_keys_and_asset_escape(selection, timing, tmp_path):
    review = review_for(selection, timing)
    changed = deepcopy(review)
    changed['timing']['report']['json'] += ' '
    changed = resign(changed, 'review_id')
    with pytest.raises(ScoreError, match='Exact saved timing'):
        validate_loop_review(selection[0], changed)
    duplicate = tmp_path / 'duplicate.json'; duplicate.write_text('{"a":1,"a":2}')
    with pytest.raises(ScoreError, match='Duplicate JSON key'):
        read_review(duplicate)
    asset = selection[0] / 'finished.motion.json'
    destination = tmp_path / 'outside.json'; asset.rename(destination); asset.symlink_to(destination)
    with pytest.raises(ScoreError, match='cannot escape'):
        load_selection(selection[0])


def test_changed_native_payload_is_rejected_before_package(selection, timing, tmp_path):
    review = review_for(selection, timing)
    path = selection[0] / 'finished.motion.json'
    payload = read_review(path); payload['recording']['samples'][100][0] += .001
    path.write_text(json.dumps(payload))
    with pytest.raises(ScoreError, match='identity changed'):
        export(selection[0], review, tmp_path / 'bad-package', timing[2], allow_test_review=True)
    assert not (tmp_path / 'bad-package').exists()


def test_rejected_or_gap_crossing_selection_has_no_partial_output(tmp_path):
    require_runtime()
    original = fixture()
    indices = [i for i, t in enumerate(original.frame_times_seconds) if not .8 < t < 1.2]
    gap = replace(original, frame_times_seconds=tuple(original.frame_times_seconds[i] for i in indices),
                  frames=tuple(original.frames[i] for i in indices))
    source = tmp_path / 'gap.json'; write_capture(source, gap)
    out = tmp_path / 'gap-selection'
    with pytest.raises(ScoreError, match='missing source coverage'):
        finish_review_selection(source, out, start_seconds=0., end_seconds=2., beats=4,
            original_source_sha256='1' * 64, repair_options={'translation_scale': 1.})
    assert not out.exists()
    source2 = tmp_path / 'idle.json'
    idle = replace(original, frames=tuple(original.frames[0] for _ in original.frames))
    write_capture(source2, idle)
    with pytest.raises(ScoreError, match='insufficient_meaningful_motion'):
        finish_review_selection(source2, out, start_seconds=0., end_seconds=2., beats=4,
            original_source_sha256='1' * 64, repair_options={'translation_scale': 1.})
    assert not out.exists()


def test_mapping_gaps_cannot_be_promoted_to_one_loop(selection, timing, tmp_path):
    from stemlab.analysis.motion_alignment import (
        create_alignment_revision,
        read_document,
        write_document,
    )
    report, report_hash = read_document(timing[0])
    revision = create_alignment_revision(report, report_sha256=report_hash,
        candidate_id=report['candidates'][0]['candidate_id'], reviewer='Automated synthetic regression',
        manual_anchors=[{'motion_seconds': .2, 'audio_seconds': .45},
                        {'motion_seconds': 1.8, 'audio_seconds': 2.05}])
    path = tmp_path / 'partial-review.json'; write_document(path, revision)
    with pytest.raises(ScoreError, match='does not cover the whole loop'):
        create_loop_review(selection[0], alignment_report_path=timing[0], timing_revision_path=path,
            audio_source_path=timing[2], target=TARGET, reviewer='Synthetic',
            verdicts={'seam': 'accept', 'feet': 'accept', 'skin': 'accept'}, review_kind='automated_test')


def test_native_failure_aborts_selection_transaction(selection, tmp_path, monkeypatch):
    from dancerudiments_authoring import source_loop_analysis
    def fail(_):
        raise RuntimeError('native parity regression')
    monkeypatch.setattr(source_loop_analysis, '_native_check', fail)
    output = tmp_path / 'failed-native'
    with pytest.raises(RuntimeError, match='native parity'):
        finish_review_selection(selection[2], output, start_seconds=0., end_seconds=2., beats=4,
            original_source_sha256='1' * 64, repair_options={'translation_scale': 1.})
    assert not output.exists()


def test_export_refuses_private_paths_without_rewriting_reviewed_motion(selection, timing, tmp_path):
    review = review_for(selection, timing)
    with pytest.raises(ScoreError, match='local filesystem path'):
        export_reviewed_loop(selection[0], review, tmp_path / 'leak',
            audio_source_path=timing[2], expected_target=TARGET,
            package_id='review_fixture', version='1.0.0', title='Synthetic fixture',
            license={'id': 'MIT', 'url': 'https://example.org/license', 'attribution': 'Synthetic'},
            provenance={'original_model': r'C:\Users\Private\dance.blend'}, allow_test_review=True)
    assert not (tmp_path / 'leak').exists()
    assert load_selection(selection[0]) == selection[1]


def test_original_media_hash_must_match_saved_capture_provenance(tmp_path):
    require_runtime()
    capture = fixture()
    capture = replace(capture, provenance_json=json.dumps({'source_file_sha256': '2' * 64}))
    path = tmp_path / 'source.json'; write_capture(path, capture)
    with pytest.raises(ScoreError, match='saved capture provenance'):
        finish_review_selection(path, tmp_path / 'wrong', start_seconds=0., end_seconds=2., beats=4,
            original_source_sha256='1' * 64, repair_options={'translation_scale': 1.})
    assert not (tmp_path / 'wrong').exists()


def test_publication_failure_rolls_back_only_owned_files(selection, tmp_path, monkeypatch):
    import dancerudiments_authoring.loop_review as module
    real_link = module.os.link
    output = tmp_path / 'publication-failure'
    def fail_manifest(source, destination):
        if Path(destination) == output / 'selection.json':
            raise OSError('synthetic publication failure')
        return real_link(source, destination)
    monkeypatch.setattr(module.os, 'link', fail_manifest)
    with pytest.raises(OSError, match='synthetic publication failure'):
        finish_review_selection(selection[2], output, start_seconds=0., end_seconds=2., beats=4,
            original_source_sha256='1' * 64, repair_options={'translation_scale': 1.})
    assert not output.exists()
    assert selection[2].is_file()

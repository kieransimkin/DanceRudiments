"""Source-bound loop finishing, review records and optional-package promotion.

Timing maps choose an integer native pip; C++ still performs every live motion
sample. Review statements record a person's declaration, not an algorithmic
musical/visual approval or an authenticated identity.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from bisect import bisect_right
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from ._validation import ScoreError, canonical_json, fields, integer, number
from .io import _pairs
from .loop_repair import (
    LoopRepairOptions,
    contacts_from_world_report,
    repair_loop,
    verify_compiled_loop_seam,
)
from .motion import RigMotion, write_rig_motion
from .motion_import import RigCapture, write_capture
from .motion_packages import MotionPackage, MotionPackageBuilder
from .recording import _write_bytes_document, _write_json_document
from .source_loop_analysis import _native_check, compile_repaired_loop
from .world_motion import (
    UnsupportedWorldMotion,
    analyze_world_motion,
    source_valid_segments,
)

SELECTION_FORMAT = 'dancerudiments.loop-selection.v1'
REVIEW_FORMAT = 'dancerudiments.loop-review.v1'
PLAYBACK_FORMAT = 'dancerudiments.reviewed-loop-playback.v1'
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_TIMING_BYTES = 2 * 1024 * 1024
MAX_CAPTURE_BYTES = 64 * 1024 * 1024
_FILES = {'source_capture': 'source.capture.json', 'corrected_capture': 'corrected.capture.json',
          'motion': 'finished.motion.json', 'repair': 'repair.json'}
_TARGET_KEYS = {'id', 'asset_sha256', 'rig_sha256', 'calibration_sha256'}


def document_hash(document):
    return hashlib.sha256(canonical_json(document).encode('ascii')).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _hash(value, label):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ScoreError(f'{label} must be a lowercase SHA-256')
    return value


def _label(value, label, maximum=160, *, empty=False):
    if (not isinstance(value, str) or len(value) > maximum or '\0' in value
            or (not empty and not value.strip())):
        raise ScoreError(f'{label} must be bounded text')
    return value.strip()


def _bytes(path, limit):
    with Path(path).open('rb') as stream:
        value = stream.read(limit + 1)
    if not 0 < len(value) <= limit:
        raise ScoreError(f'JSON must contain 1..{limit} bytes')
    return value


def _object_bytes(raw):
    def reject(value):
        raise ScoreError(f'Nonfinite JSON constant: {value}')
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=reject)
        if not isinstance(value, dict):
            raise ScoreError('JSON document must be an object')
        canonical_json(value)
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ScoreError(f'Invalid review JSON: {exc}') from exc


def read_review(path):
    """Read bounded JSON with duplicate-key and nonfinite-value rejection."""
    return _object_bytes(_bytes(path, MAX_DOCUMENT_BYTES))


def write_review(path, review):
    """Write a new revision without replacing any earlier review."""
    raw = (canonical_json(review) + '\n').encode('ascii')
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ScoreError('Review document exceeds 8 MiB')
    _write_bytes_document(Path(path), raw)


@contextmanager
def _new_directory(output, *, commit_files=('manifest.json', 'selection.json')):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.loop-review-', dir=output.parent))
    reserved = False
    linked, directories = [], []
    try:
        yield stage
        # mkdir claims the name atomically: simultaneous writers cannot adopt
        # an existing directory or erase another caller's completed result.
        output.mkdir()
        reserved = True
        # Hard links refuse collisions on every supported platform. Publishing
        # the manifest last gives readers the same transaction boundary as the
        # package builder and avoids replacing a directory on Windows.
        for source in sorted((p for p in stage.rglob('*') if p.is_dir()),
                             key=lambda p: (len(p.parts), str(p))):
            target = output / source.relative_to(stage)
            target.mkdir()
            directories.append(target)
        pending = sorted((p for p in stage.rglob('*') if p.is_file()),
                         key=lambda p: (p.name in commit_files, str(p)))
        for source in pending:
            relative = source.relative_to(stage)
            target = output / relative
            missing = []
            parent = target.parent
            while parent != output and not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for parent in reversed(missing):
                parent.mkdir()
                directories.append(parent)
            os.link(source, target)
            linked.append((source, target))
        reserved = False
    finally:
        if reserved:
            for source, target in reversed(linked):
                try:
                    if os.path.samefile(source, target):
                        target.unlink()
                except FileNotFoundError:
                    pass
            for directory in reversed(directories):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            try:
                output.rmdir()  # Never removes someone else's nonempty data.
            except OSError:
                pass
        if stage.exists():
            shutil.rmtree(stage)


def _descriptor(root, relative):
    raw = _bytes(Path(root) / relative, MAX_CAPTURE_BYTES)
    return {'path': relative, 'sha256': hashlib.sha256(raw).hexdigest(), 'byte_length': len(raw)}


def _asset(root, descriptor, expected_path):
    fields(descriptor, {'path', 'sha256', 'byte_length'}, {'path', 'sha256', 'byte_length'}, 'selection asset')
    if descriptor['path'] != expected_path:
        raise ScoreError('Selection asset must use its fixed local filename')
    _hash(descriptor['sha256'], 'selection asset hash')
    integer(descriptor['byte_length'], 1, MAX_CAPTURE_BYTES, 'asset byte length')
    root = Path(root).resolve()
    target = root / expected_path
    if target.is_symlink() or target.resolve().parent != root:
        raise ScoreError('Selection asset cannot escape its directory')
    try:
        raw = _bytes(target, descriptor['byte_length'])
    except ScoreError as exc:
        raise ScoreError(f'Selection asset identity changed: {expected_path}') from exc
    if len(raw) != descriptor['byte_length'] or hashlib.sha256(raw).hexdigest() != descriptor['sha256']:
        raise ScoreError(f'Selection asset identity changed: {expected_path}')
    return _object_bytes(raw)


def _with_id(value, key):
    result = deepcopy(value)
    result[key] = document_hash(value)
    return result


def _check_id(document, key):
    value = dict(document)
    expected = _hash(value.pop(key, None), key)
    if document_hash(value) != expected:
        raise ScoreError(f'{key} content identity mismatch')


def _original_source(capture, digest):
    claims = [capture.provenance.get('source_file_sha256'), capture.provenance.get('source_sha256')]
    file_record = capture.provenance.get('source_file')
    if isinstance(file_record, dict):
        claims.append(file_record.get('sha256'))
    if any(value is not None and value != digest for value in claims):
        raise ScoreError('Original source hash differs from the saved capture provenance')


def finish_review_selection(capture_path, output_dir, *, start_seconds, end_seconds, beats,
                            original_source_sha256, repair_options=None, verify_native=True,
                            name='reviewed_loop'):
    """Finish an explicit source window into a new immutable review directory.

    Beat count is a review hypothesis. Rejected repairs raise with their reasons
    and leave no output directory; originals and earlier selections are intact.
    """
    if Path(output_dir).exists() or Path(output_dir).is_symlink():
        raise FileExistsError(output_dir)
    original_source_sha256 = _hash(original_source_sha256, 'original source hash')
    integer(beats, 1, 32, 'beats')
    start, end = number(start_seconds, 'start_seconds'), number(end_seconds, 'end_seconds')
    if end <= start or not 30 <= 60 * beats / (end - start) <= 300:
        raise ScoreError('Selected beat interpretation must be within 30..300 BPM')
    if type(verify_native) is not bool:
        raise ScoreError('verify_native must be boolean')
    raw = _bytes(capture_path, MAX_CAPTURE_BYTES)
    source = RigCapture.from_dict(_object_bytes(raw))
    _original_source(source, original_source_sha256)
    if not any(a <= start < end <= b for a, b in source_valid_segments(source)):
        raise ScoreError('Selected boundaries cross missing source coverage')
    if repair_options is None:
        repair_options = LoopRepairOptions()
    elif isinstance(repair_options, dict):
        repair_options = LoopRepairOptions(**repair_options)
    if not isinstance(repair_options, LoopRepairOptions):
        raise ScoreError('repair_options must be bounded loop repair settings')
    options = replace(repair_options, sample_count=beats * 64 + 1)
    try:
        world = analyze_world_motion(source, source_file_sha256=hashlib.sha256(raw).hexdigest())
    except UnsupportedWorldMotion as exc:
        world = {'supported': False, 'reason': str(exc)}
    contacts = contacts_from_world_report(source, world) if world.get('supported') else ()
    result = repair_loop(source, start_seconds=start, end_seconds=end, options=options, contacts=contacts)
    motion, repair = compile_repaired_loop(source, result, beats=beats, name=name,
        original_sha256=original_source_sha256, verify_native=verify_native)
    if motion is None:
        raise ScoreError('Selected window rejected: ' + '; '.join(repair.get('rejection_reasons', [])))
    with _new_directory(output_dir) as stage:
        _write_bytes_document(stage / _FILES['source_capture'], raw)
        write_capture(stage / _FILES['corrected_capture'], result.capture)
        write_rig_motion(stage / _FILES['motion'], motion)
        repair.update(original_source_sha256=original_source_sha256,
            compiled_motion_sha256=file_hash(stage / _FILES['motion']),
            corrected_capture_file=_FILES['corrected_capture'],
            corrected_capture_file_sha256=file_hash(stage / _FILES['corrected_capture']))
        _write_json_document(stage / _FILES['repair'], repair)
        selection = _with_id({'format': SELECTION_FORMAT, 'schema_version': 1,
            'source': {'capture_file_sha256': hashlib.sha256(raw).hexdigest(),
                    'capture_sha256': source.fingerprint, 'profile_sha256': source.profile.fingerprint,
                    'original_source_sha256': original_source_sha256},
            'bounds': {'start_seconds': start, 'end_seconds': end}, 'beat_count': beats,
            'sample_count': beats * 64, 'motion_fingerprint': motion.fingerprint,
            'files': {key: _descriptor(stage, path) for key, path in _FILES.items()},
            'numerical_seam_verified': True, 'native_samples_verified': verify_native,
            'requires_review': True}, 'selection_id')
        write_review(stage / 'selection.json', selection)
    return selection


def load_selection(directory, *, verify_native=False):
    """Verify the saved source/derivative identities and final compiled payload."""
    if (Path(directory) / 'selection.json').is_symlink():
        raise ScoreError('Selection manifest cannot be a symbolic link')
    selection = read_review(Path(directory) / 'selection.json')
    keys = {'format', 'schema_version', 'selection_id', 'source', 'bounds', 'beat_count',
            'sample_count', 'motion_fingerprint', 'files', 'numerical_seam_verified',
            'native_samples_verified', 'requires_review'}
    fields(selection, keys, keys, 'loop selection')
    if (selection['format'] != SELECTION_FORMAT or type(selection['schema_version']) is not int
            or selection['schema_version'] != 1):
        raise ScoreError('Unknown loop selection schema')
    _check_id(selection, 'selection_id')
    fields(selection['files'], _FILES, _FILES, 'selection files')
    docs = {key: _asset(directory, selection['files'][key], path) for key, path in _FILES.items()}
    source = RigCapture.from_dict(docs['source_capture'])
    corrected = RigCapture.from_dict(docs['corrected_capture'])
    motion = RigMotion.from_dict(docs['motion'])
    repair = docs['repair']
    identity = selection['source']
    fields(identity, {'capture_file_sha256', 'capture_sha256', 'profile_sha256', 'original_source_sha256'},
           {'capture_file_sha256', 'capture_sha256', 'profile_sha256', 'original_source_sha256'}, 'selection source')
    for key, value in identity.items():
        _hash(value, key)
    _original_source(source, identity['original_source_sha256'])
    if (identity['capture_file_sha256'] != selection['files']['source_capture']['sha256']
            or identity['capture_sha256'] != source.fingerprint
            or identity['profile_sha256'] != source.profile.fingerprint
            or motion.fingerprint != selection['motion_fingerprint']
            or motion.profile.fingerprint != source.profile.fingerprint
            or corrected.profile.fingerprint != source.profile.fingerprint):
        raise ScoreError('Selection source/profile/compiled identity mismatch')
    fields(selection['bounds'], {'start_seconds', 'end_seconds'}, {'start_seconds', 'end_seconds'}, 'loop bounds')
    start, end = (number(selection['bounds'][key], key) for key in ('start_seconds', 'end_seconds'))
    beats = integer(selection['beat_count'], 1, 32, 'beat_count')
    if (not any(a <= start < end <= b for a, b in source_valid_segments(source))
            or selection['sample_count'] != beats * 64
            or len(motion.recording.samples) != selection['sample_count']
            or motion.recording.clock.start_pip != 0
            or selection['requires_review'] is not True
            or selection['numerical_seam_verified'] is not True
            or type(selection['native_samples_verified']) is not bool):
        raise ScoreError('Selection boundaries, native extent or review state changed')
    if (repair.get('source_start_seconds') != start or repair.get('source_end_seconds') != end
            or repair.get('source_capture_sha256') != source.fingerprint
            or repair.get('source_profile_sha256') != source.profile.fingerprint
            or repair.get('original_source_sha256') != identity['original_source_sha256']
            or repair.get('compiled_motion_sha256') != selection['files']['motion']['sha256']
            or repair.get('corrected_capture_file_sha256') != selection['files']['corrected_capture']['sha256']
            or repair.get('accepted') is not True
            or repair.get('sample_count') != selection['sample_count'] + 1):
        raise ScoreError('Selection repair evidence differs from its files/boundaries')
    checked = verify_compiled_loop_seam(motion, corrected, repair)
    if not checked['passed'] or repair.get('compiled_verification') != checked:
        raise ScoreError('Final compiled motion no longer passes its recorded numerical verification')
    if verify_native:
        _native_check(motion)
    return selection


def validate_target(target):
    fields(target, _TARGET_KEYS, _TARGET_KEYS, 'review target')
    result = {'id': _label(target['id'], 'target id')}
    for key in _TARGET_KEYS - {'id'}:
        result[key] = _hash(target[key], key)
    return result


def _timing_document(path):
    raw = _bytes(path, MAX_TIMING_BYTES)
    doc = _object_bytes(raw)
    return doc, {'json': raw.decode('utf-8'), 'sha256': hashlib.sha256(raw).hexdigest()}


def _embedded_timing(item):
    fields(item, {'json', 'sha256'}, {'json', 'sha256'}, 'timing snapshot')
    if not isinstance(item['json'], str):
        raise ScoreError('Timing snapshot JSON must be text')
    raw = item['json'].encode('utf-8')
    if not 0 < len(raw) <= MAX_TIMING_BYTES or hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise ScoreError('Exact saved timing document bytes changed')
    return _object_bytes(raw)


def _interpolate(anchors, value, input_key, output_key):
    values = [anchor[input_key] for anchor in anchors]
    if not values[0] <= value <= values[-1]:
        raise ScoreError('Timing value is outside its continuous mapping')
    if value == values[0]:
        return anchors[0][output_key]
    if value == values[-1]:
        return anchors[-1][output_key]
    index = min(len(values) - 1, max(1, bisect_right(values, value)))
    first, last = anchors[index - 1], anchors[index]
    weight = (value - first[input_key]) / (last[input_key] - first[input_key])
    return first[output_key] + weight * (last[output_key] - first[output_key])


def _playback(selection, revision):
    if revision.get('decision') != 'accept_mapping':
        raise ScoreError('A loop review needs an explicitly accepted timing mapping')
    start, end = (selection['bounds'][key] for key in ('start_seconds', 'end_seconds'))
    segment = next((s for s in revision['mapping_segments']
                    if s['motion_seconds_range'][0] <= start < end <= s['motion_seconds_range'][1]), None)
    if segment is None:
        raise ScoreError('Accepted mapping does not cover the whole loop in one continuous segment')
    anchors = segment['anchors']
    first = _interpolate(anchors, start, 'motion_seconds', 'audio_seconds')
    last = _interpolate(anchors, end, 'motion_seconds', 'audio_seconds')
    clipped = [{'motion_seconds': start, 'audio_seconds': first}]
    clipped += [{'motion_seconds': a['motion_seconds'], 'audio_seconds': a['audio_seconds']}
                for a in anchors if start < a['motion_seconds'] < end]
    clipped += [{'motion_seconds': end, 'audio_seconds': last}]
    return {'format': PLAYBACK_FORMAT, 'schema_version': 1,
        'source_seconds_range': [start, end], 'audio_seconds_range': [first, last],
        'period_pips': selection['sample_count'], 'pips_per_beat': 64,
        'beat_count': selection['beat_count'], 'repeat_policy': 'explicit_half_open_audio_interval',
        'interpolation': 'piecewise_linear_clock_to_integer_native_pip',
        'mapping_segments': [{'motion_seconds_range': [start, end],
            'audio_seconds_range': [first, last], 'anchors': clipped}]}


def _validate_timing(selection, timing, audio_source_path=None):
    from stemlab.analysis.motion_alignment import validate_alignment_revision
    fields(timing, {'report', 'revision'}, {'report', 'revision'}, 'timing evidence')
    report, revision = _embedded_timing(timing['report']), _embedded_timing(timing['revision'])
    validate_alignment_revision(report, revision, report_sha256=timing['report']['sha256'])
    if report['motion_source']['sha256'] != selection['source']['capture_file_sha256']:
        raise ScoreError('Timing report is bound to a different original capture')
    audio_hash = _hash(report['audio_source']['sha256'], 'audio master hash')
    if audio_source_path is not None and file_hash(audio_source_path) != audio_hash:
        raise ScoreError('Actual audio master bytes differ from the reviewed source')
    return report, revision, _playback(selection, revision)


def _stamp(value):
    try:
        if not isinstance(value, str) or len(value) > 64:
            raise ValueError('invalid timestamp')
        parsed = datetime.fromisoformat(value[:-1] + '+00:00' if value.endswith('Z') else value)
        if parsed.tzinfo is None:
            raise ValueError('missing timezone')
    except (ValueError, TypeError) as exc:
        raise ScoreError('Review timestamp must be ISO time with an explicit timezone') from exc


def _verdicts(value):
    fields(value, {'seam', 'feet', 'skin'}, {'seam', 'feet', 'skin'}, 'visual verdicts')
    if any(item not in ('accept', 'reject', 'unreviewed') for item in value.values()):
        raise ScoreError('Visual verdicts must be accept, reject or unreviewed')
    return deepcopy(value)


def _status(kind, verdicts):
    if 'reject' in verdicts.values():
        return 'reviewer_rejected'
    if 'unreviewed' in verdicts.values():
        return 'needs_review'
    return 'reviewer_accepted' if kind == 'human' else 'automated_test_fixture'


def create_loop_review(selection_dir, *, alignment_report_path, timing_revision_path,
                       audio_source_path, target, reviewer, verdicts, review_kind='human',
                       notes='', previous_review=None):
    """Record explicit timing and visual declarations against the exact result.

    The caller supplies target hashes verified against its actual loaded mesh,
    rig and calibration. This function never infers a human visual verdict.
    """
    selection = load_selection(selection_dir)
    _, report = _timing_document(alignment_report_path)
    _, revision = _timing_document(timing_revision_path)
    timing = {'report': report, 'revision': revision}
    _, _, playback = _validate_timing(selection, timing, audio_source_path)
    target = validate_target(target)
    reviewer = _label(reviewer, 'reviewer')
    notes = _label(notes, 'notes', 4000, empty=True)
    verdicts = _verdicts(verdicts)
    if review_kind not in ('human', 'automated_test'):
        raise ScoreError('Review kind must be human or automated_test')
    previous_hash, revision_number = None, 1
    if previous_review is not None:
        previous = read_review(previous_review) if isinstance(previous_review, (str, Path)) else previous_review
        validate_loop_review(selection_dir, previous)
        previous_hash, revision_number = document_hash(previous), previous['revision'] + 1
    result = _with_id({'format': REVIEW_FORMAT, 'schema_version': 1,
        'revision': revision_number, 'previous_review_sha256': previous_hash,
        'selection_id': selection['selection_id'],
        'selection_sha256': file_hash(Path(selection_dir) / 'selection.json'),
        'motion_sha256': selection['files']['motion']['sha256'],
        'motion_fingerprint': selection['motion_fingerprint'],
        'source': deepcopy(selection['source']), 'timing': timing, 'playback': playback,
        'target': target, 'reviewer': reviewer, 'review_kind': review_kind,
        'reviewed_at': datetime.now(timezone.utc).isoformat(), 'verdicts': verdicts, 'notes': notes,
        'status': _status(review_kind, verdicts),
        'human_approved': review_kind == 'human' and all(v == 'accept' for v in verdicts.values()),
        'numerical_seam_verified': True}, 'review_id')
    validate_loop_review(selection_dir, result, audio_source_path=audio_source_path, expected_target=target)
    return result


def _validate_review_record(review):
    keys = {'format', 'schema_version', 'review_id', 'revision', 'previous_review_sha256',
            'selection_id', 'selection_sha256', 'motion_sha256', 'motion_fingerprint', 'source',
            'timing', 'playback', 'target', 'reviewer', 'review_kind', 'reviewed_at',
            'verdicts', 'notes', 'status', 'human_approved', 'numerical_seam_verified'}
    fields(review, keys, keys, 'loop review')
    if (review['format'] != REVIEW_FORMAT or type(review['schema_version']) is not int
            or review['schema_version'] != 1):
        raise ScoreError('Unknown loop review schema')
    _check_id(review, 'review_id')
    for key in ('selection_id', 'selection_sha256', 'motion_sha256', 'motion_fingerprint'):
        _hash(review[key], key)
    count = integer(review['revision'], 1, 1000000, 'review revision')
    if count == 1:
        if review['previous_review_sha256'] is not None:
            raise ScoreError('First review cannot claim a previous revision')
    else:
        _hash(review['previous_review_sha256'], 'previous review hash')
    _label(review['reviewer'], 'reviewer')
    _label(review['notes'], 'notes', 4000, empty=True)
    _stamp(review['reviewed_at'])
    validate_target(review['target'])
    verdicts = _verdicts(review['verdicts'])
    if review['review_kind'] not in ('human', 'automated_test'):
        raise ScoreError('Unknown review kind')
    accepted = review['review_kind'] == 'human' and all(v == 'accept' for v in verdicts.values())
    if (review['status'] != _status(review['review_kind'], verdicts)
            or review['human_approved'] is not accepted or review['numerical_seam_verified'] is not True):
        raise ScoreError('Review status contradicts the explicit declarations')


def validate_loop_review(selection_dir, review, *, audio_source_path=None, expected_target=None,
                         previous_review=None, require_accepted=False, allow_test_review=False):
    """Reject stale boundary, timing, motion, source and target review records."""
    review = read_review(review) if isinstance(review, (str, Path)) else deepcopy(review)
    _validate_review_record(review)
    selection = load_selection(selection_dir)
    if (review['selection_id'] != selection['selection_id']
            or review['selection_sha256'] != file_hash(Path(selection_dir) / 'selection.json')
            or review['motion_sha256'] != selection['files']['motion']['sha256']
            or review['motion_fingerprint'] != selection['motion_fingerprint']
            or review['source'] != selection['source']):
        raise ScoreError('Review belongs to an earlier or different source/selection/compiled motion')
    _, _, playback = _validate_timing(selection, review['timing'], audio_source_path)
    if review['playback'] != playback:
        raise ScoreError('Saved playback differs from the accepted timing and loop boundaries')
    if expected_target is not None and review['target'] != validate_target(expected_target):
        raise ScoreError('Target asset, rig or calibration changed since visual review')
    if previous_review is not None:
        previous = read_review(previous_review) if isinstance(previous_review, (str, Path)) else previous_review
        _validate_review_record(previous)
        if (review['previous_review_sha256'] != document_hash(previous)
                or review['revision'] != previous['revision'] + 1
                or previous['selection_id'] != review['selection_id']):
            raise ScoreError('Review revision chain differs')
    if require_accepted:
        accepted = review['human_approved'] or (
            allow_test_review and review['review_kind'] == 'automated_test'
            and review['status'] == 'automated_test_fixture')
        if not accepted:
            raise ScoreError('Export requires accepted timing and all three visual decisions')
    return review


def _validate_playback(playback):
    keys = {'format', 'schema_version', 'source_seconds_range', 'audio_seconds_range',
            'period_pips', 'pips_per_beat', 'beat_count', 'repeat_policy', 'interpolation', 'mapping_segments'}
    fields(playback, keys, keys, 'reviewed playback')
    if (playback['format'] != PLAYBACK_FORMAT or type(playback['schema_version']) is not int
            or playback['schema_version'] != 1
            or playback['pips_per_beat'] != 64
            or playback['repeat_policy'] != 'explicit_half_open_audio_interval'
            or playback['interpolation'] != 'piecewise_linear_clock_to_integer_native_pip'):
        raise ScoreError('Unknown reviewed playback contract')
    beats = integer(playback['beat_count'], 1, 32, 'playback beat count')
    if playback['period_pips'] != beats * 64:
        raise ScoreError('Playback period differs from native beat count')
    if not isinstance(playback['mapping_segments'], list) or len(playback['mapping_segments']) != 1:
        raise ScoreError('A reviewed loop must have one continuous mapping')
    segment = playback['mapping_segments'][0]
    fields(segment, {'motion_seconds_range', 'audio_seconds_range', 'anchors'},
           {'motion_seconds_range', 'audio_seconds_range', 'anchors'}, 'playback segment')
    anchors = segment['anchors']
    if not isinstance(anchors, list) or not 2 <= len(anchors) <= 6002:
        raise ScoreError('Playback needs bounded ordered timing anchors')
    previous = None
    for anchor in anchors:
        fields(anchor, {'motion_seconds', 'audio_seconds'}, {'motion_seconds', 'audio_seconds'}, 'playback anchor')
        pair = tuple(number(anchor[k], k) for k in ('motion_seconds', 'audio_seconds'))
        if previous and (pair[0] <= previous[0] or pair[1] <= previous[1]):
            raise ScoreError('Playback timing must increase in both clocks')
        previous = pair
    for side, field in (('motion', 'source'), ('audio', 'audio')):
        bounds = [anchors[0][side + '_seconds'], anchors[-1][side + '_seconds']]
        if segment[side + '_seconds_range'] != bounds or playback[field + '_seconds_range'] != bounds:
            raise ScoreError('Playback range differs from its anchors')
    return playback


def audio_seconds_to_pip(review_or_playback, seconds, *, repeat=False):
    """Choose an existing native integer pip; return None outside known coverage.

    Explicit repeat wraps only this loop's audio interval. Its closing endpoint
    is exclusive, so the duplicate closing pose is never sampled.
    """
    if not isinstance(review_or_playback, dict):
        raise ScoreError('Reviewed playback must be an object')
    playback = review_or_playback.get('playback', review_or_playback)
    _validate_playback(playback)
    seconds = number(seconds, 'audio seconds')
    if type(repeat) is not bool:
        raise ScoreError('repeat must be boolean')
    first, last = playback['audio_seconds_range']
    if seconds < first:
        return None
    if repeat:
        seconds = first + (seconds - first) % (last - first)
        if seconds >= last:  # Floating addition can round a final ULP up.
            seconds = first
    elif seconds >= last:
        return None
    source = _interpolate(playback['mapping_segments'][0]['anchors'], seconds,
                          'audio_seconds', 'motion_seconds')
    start, end = playback['source_seconds_range']
    # Rounding of an interior clock interpolation may land on the last ULP.
    # The range check above already rejected an actual closing endpoint.
    return min(playback['period_pips'] - 1,
               max(0, math.floor((source - start) / (end - start) * playback['period_pips'])))


def _reject_local_paths(value, path='export'):
    """Refuse private provenance without silently changing reviewed motion bytes."""
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_local_paths(item, path + '.' + str(key))
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _reject_local_paths(item, path + '[' + str(index) + ']')
    elif isinstance(value, str):
        candidate = value.strip()
        if (candidate.startswith(('/', '\\\\', '~/'))
                or re.match(r'^[A-Za-z]:[\\/]', candidate)
                or re.match(r'^(?:file|vscode):', candidate, re.IGNORECASE)
                or re.search(r'(?:^|[\s"\'])/(?:home|Users|workspace|tmp|private|root|mnt)/', candidate)
                or re.search(r'(?:^|[\s"\'])[A-Za-z]:[\\/]', candidate)):
            raise ScoreError('Export contains a local filesystem path at ' + path +
                '; prepare portable source provenance and finish/review that capture again')


def export_reviewed_loop(selection_dir, review, output_dir, *, audio_source_path, expected_target,
                         package_id, version, title, license, provenance, allow_test_review=False):
    """Create an optional package with exact native samples and saved review.

    Source captures, audio, target assets and local paths are never copied into
    the package. Automated fixtures stay explicitly unapproved.
    """
    review = validate_loop_review(selection_dir, review, audio_source_path=audio_source_path,
        expected_target=expected_target, require_accepted=True, allow_test_review=allow_test_review)
    selection = load_selection(selection_dir, verify_native=True)
    motion = RigMotion.from_dict(_asset(selection_dir, selection['files']['motion'], _FILES['motion']))
    if not isinstance(license, dict) or not isinstance(provenance, dict):
        raise ScoreError('Export requires explicit reviewed licence and provenance objects')
    for key in ('id', 'url', 'attribution'):
        _label(license.get(key), 'license.' + key, 4000)
    canonical_json(provenance)
    _reject_local_paths(motion.recording.provenance, 'motion.provenance')
    _reject_local_paths(provenance, 'package.provenance')
    _reject_local_paths(license, 'package.license')
    _reject_local_paths(review, 'review')
    for key in ('report', 'revision'):
        _reject_local_paths(_embedded_timing(review['timing'][key]), 'timing.' + key)
    with _new_directory(output_dir) as stage:
        exported_provenance = dict(provenance, source_capture_sha256=selection['source']['capture_sha256'],
            source_capture_file_sha256=selection['source']['capture_file_sha256'],
            original_source_sha256=selection['source']['original_source_sha256'],
            review_id=review['review_id'], selection_id=selection['selection_id'],
            changes='Bounded source-loop correction; exact native samples with explicit reviewed clock mapping.')
        builder = MotionPackageBuilder(stage, package_id=package_id, version=version,
            title=title, profile=motion.profile, license=deepcopy(license), provenance=exported_provenance)
        builder.add(motion, metadata={'timing_kind': 'music' if review['human_approved'] else 'time-only',
            'review_kind': review['review_kind'], 'human_approved': review['human_approved'],
            'native_samples_verified': True, 'reviewed_loop': review,
            'playback_contract': PLAYBACK_FORMAT})
        manifest = builder.finalize()
        _write_bytes_document(stage / 'README.md', (
            '# ' + title + '\n\n'
            'Explicit optional motion package. Use the saved reviewed-loop playback map with the '
            'existing native 64-pip sampler. The stored recording clock alone does not reproduce '
            'a variable audio alignment. Repeat is explicit and the closing endpoint is excluded.\n\n'
            'Review status: ' + review['status'] + '. Review statements are declarations, '
            'not independently authenticated identity or automatic artistic approval.\n\n'
            'Original capture, audio and target geometry are not included. Source rights remain '
            'applicable; see LICENSE.txt, THIRD_PARTY_NOTICES.md and SOURCES.json.\n\n'
            'Music by Kieran Simkin: https://kieransimkin.co.uk/my-songs/\n').encode('utf-8'))
        _write_bytes_document(stage / 'LICENSE.txt',
            (license['id'] + '\n' + license['url'] + '\n' + license['attribution'] + '\n').encode('utf-8'))
        _write_bytes_document(stage / 'THIRD_PARTY_NOTICES.md',
            ('# Source notices\n\n' + license['attribution'] + '\n\n' + license['url'] + '\n').encode('utf-8'))
        _write_json_document(stage / 'SOURCES.json', exported_provenance)
        # Verify the actual packaged representation, not just the builder input.
        with MotionPackage(stage, expected_profile=motion.profile, cache_size=0) as package:
            reloaded = package.load(motion.name)
            if reloaded.fingerprint != motion.fingerprint:
                raise ScoreError('Package reload changed the reviewed native motion')
            _native_check(reloaded)
    return manifest


class ReviewedLoopPlayer:
    """Audio-clock adapter around the existing native player of a package clip."""

    def __init__(self, motion, review, *, allow_test_review=False):
        if not isinstance(motion, RigMotion):
            raise ScoreError('Reviewed playback requires a validated RigMotion')
        _validate_review_record(review)
        _validate_playback(review['playback'])
        playback = review['playback']
        surrogate = {'source': review['source'],
            'bounds': dict(zip(('start_seconds', 'end_seconds'), playback['source_seconds_range'])),
            'sample_count': playback['period_pips'], 'beat_count': playback['beat_count']}
        _, _, expected = _validate_timing(surrogate, review['timing'])
        if expected != playback:
            raise ScoreError('Packaged playback no longer matches its reviewed timing')
        if (motion.fingerprint != review['motion_fingerprint']
                or len(motion.recording.samples) != review['playback']['period_pips']
                or motion.recording.clock.start_pip != 0):
            raise ScoreError('Packaged review and native recording differ')
        if not review['human_approved'] and not (allow_test_review and review['status'] == 'automated_test_fixture'):
            raise ScoreError('The package has no accepted review for playback')
        self.review = deepcopy(review)
        self._player = motion.player()

    def sample_audio(self, seconds, *, repeat=False):
        pip = audio_seconds_to_pip(self.review, seconds, repeat=repeat)
        return None if pip is None else self._player.sample(pip)


def load_reviewed_loop(package_path, clip_id, *, allow_test_review=False):
    """Load one explicit reviewed package clip; no global discovery or downloads."""
    with MotionPackage(package_path, cache_size=0) as package:
        descriptor = next((c for c in package.catalogue() if c['id'] == clip_id), None)
        if descriptor is None:
            raise ScoreError('Unknown reviewed package clip')
        review = descriptor.get('metadata', {}).get('reviewed_loop')
        return ReviewedLoopPlayer(package.load(clip_id), review, allow_test_review=allow_test_review)

"""Analyse original physical rig captures with StemLab before 64-pip compilation.

StemLab owns the beat/loop inference. DanceRudiments owns source parsing,
semantic rig identity, resampling, and native playback. Only explicitly chosen
candidate previews are compiled; original actions and source timing are intact.

This optional offline module does not import StemLab or download models on import.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from fractions import Fraction
from dataclasses import replace
import tempfile

from ._validation import ScoreError, canonical_json
from .motion import write_rig_motion
from .motion_clock import BeatMap
from .motion_import import RigCapture, compile_capture, write_capture
from .recording import RecordingClock, MAX_RECORDING_VALUES
from .full_motion_analysis import assess_full_motion, DEFAULT_THRESHOLD

FORMAT = 'dancerudiments.source-motion-loop-job'
BEAT_COUNTS = frozenset((1, 2, 4, 8, 16, 32))
MAX_PREVIEWS = 12


def source_capture_from_bvh(clip, *, calibration_frames=0, source_provenance=None):
    """Turn original BVH physical frames into a source-time capture, NOT a rudiment.

    Keep the native frame interval, exact source profile and SHA-256. Calibration
    exclusion is explicitly declared and applies only to analysis, not the BVH.
    """
    from .bvh_import import BVHClip
    if not isinstance(clip, BVHClip):
        raise ScoreError('Expected a validated original BVHClip')
    if (type(calibration_frames) is not int or not 0 <= calibration_frames <= 60
            or calibration_frames >= clip.frame_count):
        raise ScoreError('calibration_frames must be 0..60, less than source frame count')
    count = clip.frame_count - calibration_frames
    if count > 200_000 or count * len(clip.profile.channels) > 8_388_608:
        raise ScoreError('Original action exceeds bounded StemLab motion analysis limits')
    if count < 16 or (count - 1) * clip.frame_time_seconds < 3:
        raise ScoreError('StemLab requires at least 16 source frames and three seconds of motion')
    times = tuple(float(index * clip.frame_time_seconds)
                  for index in range(calibration_frames, clip.frame_count))
    if source_provenance is not None and not isinstance(source_provenance, dict):
        raise ScoreError('source_provenance must be a provenance dictionary')
    provenance = dict(clip.metadata, source_file_sha256=clip.source_sha256,
                      source_frame_time_seconds=str(clip.frame_time_seconds),
                      source_profile_sha256=clip.profile.fingerprint,
                      calibration_frames_excluded_from_analysis=calibration_frames,
                      clock='original source seconds; no verified musical beat or phase')
    return RigCapture(clip.profile, times,
                      tuple(tuple(float(value) for value in row)
                            for row in clip.frames[calibration_frames:]),
                      canonical_json(provenance))


def _stemlab():
    try:
        from stemlab.analysis.rig_motion import analyze_rig_capture, write_rig_analysis
    except ImportError as exc:
        raise RuntimeError('Cannot import StemLab source-time motion analysis: '
                           f'{exc}. Install a compatible StemLab runtime; '
                           'kinematic analysis requires NumPy but its package '
                           'initialisation may also require soundfile.') from exc
    return analyze_rig_capture, write_rig_analysis


def _real(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    return float(value)


def _preview_eligible(report, capture, *, target_bpm):
    """Return candidates only when StemLab supplied an estimated beat grid.

    A pose-only recurrence with no supported beat count remains evidence for
    review, not a covert tempo assignment. Tempo ranking is motion-only; audio
    beat/downbeat agreement is a separate optional confirmation.
    """
    chosen, rejected = [], []
    # StemLab's loop windows are hypotheses tied to its estimated source grid.
    # Do not manufacture a preview if the map was absent, replaced or approved.
    grid = report.get('estimated_beat_map')
    try:
        source_map = BeatMap.from_dict(grid) if isinstance(grid, dict) else None
    except (ScoreError, ValueError, TypeError, KeyError):
        source_map = None
    approved_grid = (source_map is not None
                     and source_map.bpm_status == 'estimated'
                     and source_map.phase_status == 'estimated'
                     and source_map.extrapolate is False
                     and isinstance(report.get('source_file_sha256'), str)
                     and report['source_file_sha256'] in source_map.source)
    for source_index, candidate in enumerate(report.get('loop_candidates', ())):
        if not approved_grid:
            rejected.append(dict(source_index=source_index, reason='missing_source_grid_evidence'))
            continue
        if (not isinstance(candidate, dict)
                or candidate.get('alignment') != 'estimated_motion_beat_grid'
                or type(candidate.get('beats')) is not int
                or candidate['beats'] not in BEAT_COUNTS
                or candidate.get('requires_review') is not True
                or candidate.get('repaired') is not False):
            rejected.append(dict(source_index=source_index, reason='not_an_unverified_beat_grid_loop'))
            continue
        start = _real(candidate.get('start_seconds'), 'start_seconds')
        end = _real(candidate.get('end_seconds'), 'end_seconds')
        if not (capture.frame_times_seconds[0] <= start < end <= capture.frame_times_seconds[-1]):
            rejected.append(dict(source_index=source_index, reason='outside_source_bounds'))
            continue
        source_bpm = 60.0 * candidate['beats'] / (end - start)
        if not 30 <= source_bpm <= 300:
            rejected.append(dict(source_index=source_index, reason='tempo_outside_stemlab_limits'))
            continue
        # Reject a stale/inconsistent loop report before compiling anything.
        recommended = report.get('recommended_tempo')
        if (not isinstance(recommended, dict)
                or abs(source_bpm - _real(recommended.get('bpm'), 'estimated bpm'))
                   > max(1., .02 * source_bpm)):
            rejected.append(dict(source_index=source_index, reason='inconsistent_motion_grid'))
            continue
        score = _real(candidate.get('score'), 'loop score')
        if not 0 <= score <= 1:
            rejected.append(dict(source_index=source_index, reason='invalid_loop_score'))
            continue
        # Fail closed if third-party evidence changes its seam thresholds, is
        # corrupted, or omits physical diagnostics. These values match the
        # canonical StemLab source-time seam gates, not post-render approval.
        if (candidate.get('evidence') not in ('seam_only', 'repeated_and_seam')
                or any(type(candidate.get(key)) not in (int, float)
                       or not math.isfinite(candidate[key]) or not 0 <= candidate[key] <= bound
                       for key, bound in (('pose_mismatch', .32),
                                          ('velocity_mismatch', .6),
                                          ('root_drift_relative', .02)))):
            rejected.append(dict(source_index=source_index, reason='unsafe_or_missing_seam_evidence'))
            continue
        speed_ratio = target_bpm / source_bpm if target_bpm is not None else 1.0
        # Existing StemLab diagnostics are retained unchanged. Prefer observed
        # repeated motion, strong original seams and moderate tempo adjustments.
        rank = score / (1 + abs(math.log2(speed_ratio)) * .25)
        chosen.append((rank, source_index, candidate, source_bpm, speed_ratio))
    chosen.sort(key=lambda item: (item[2].get('evidence') != 'repeated_and_seam',
                                  -item[0], -item[2]['beats'], item[1]))
    return chosen, rejected


def _native_check(motion):
    """Verify first/last and interior native 64-pip samples against compiled rows.

    This validates native transport/decoding, NOT continuity of the skinned mesh.
    """
    player = motion.player()  # explicit opt-in: native extension must be installed
    total = len(motion.recording.samples)
    start = motion.recording.clock.start_pip
    if player.start_pip != start or player.sample_count != total:
        raise RuntimeError('Native recording start pip / sample count differs from authored motion')
    for offset in sorted(set((0, 1, total // 2, total - 1))):
        expected = motion.profile.decode(motion.recording.samples[offset])
        pip = start + offset  # Full Actions can begin at negative absolute pips.
        actual = player.sample(pip)
        if len(actual) != len(expected) or any(
                not math.isclose(a, b, abs_tol=5e-7, rel_tol=5e-7)
                for a, b in zip(actual, expected)):
            raise RuntimeError(f'Native motion sample differs from authored recording at pip {pip}')
    return True


def _annotate_motion(motion, **metadata):
    """Keep the exact native Recording schema; enrich its preserved provenance."""
    info = dict(motion.recording.provenance, **metadata)
    return replace(motion, recording=replace(motion.recording,
                                             provenance_json=canonical_json(info)))


def _full_action_recording(capture, fit, *, presentation_bpm, original_source_sha256):
    """Quantise the *entire valid source interval* without endpoint extrapolation.

    Start pips may be negative relative to the motion beat-zero hypothesis.
    Omitted sub-pip ends are explicitly reported, never stretched or fabricated.
    """
    source_bpm = fit['selected_bpm']
    zero = fit['selected_beat_zero_seconds']
    if not source_bpm or zero is None:
        raise ValueError('A valid estimated source BPM and phase are required')
    step = Fraction(60, 64) / Fraction(str(source_bpm))
    origin = Fraction(str(zero))
    first = math.ceil((capture._times[0] - origin) / step)
    last = math.floor((capture._times[-1] - origin) / step)
    count = last - first + 1
    if count < 2 or count > MAX_RECORDING_VALUES // len(capture.profile.channels):
        raise ValueError('Entire source exceeds the available native sample budget')
    from .motion_clock import BeatMap
    source = BeatMap.from_bpm(str(source_bpm), beat_zero_seconds=str(zero),
        source='StemLab source-motion inferred grid; confidence is heuristic, not music-confirmed',
        bpm_status='estimated', phase_status='estimated')
    clock = RecordingClock(float(presentation_bpm),
        'Whole original Action on estimated source grid; target BPM is presentation only',
        'estimated', 0., 'estimated', first)
    motion = compile_capture(capture, name='source_full_action',
                             source_beat_map=source, clock=clock, sample_count=count)
    motion = _annotate_motion(motion, motion_kind='source_full_action',
        estimated_source_bpm=source_bpm, grid_fit_method=fit['method'],
        grid_fit_confidence=fit['confidence'],
        source_original_sha256=original_source_sha256,
        musical_timing_verified=False, source_capture_complete=True,
        playback_loop_policy='non_looping')
    actual_start = origin + first * step
    actual_end = origin + last * step
    return motion, dict(source_bounds_seconds=[float(capture._times[0]), float(capture._times[-1])],
                        sampled_bounds_seconds=[float(actual_start), float(actual_end)],
                        omitted_head_seconds=round(float(actual_start-capture._times[0]), 9),
                        omitted_tail_seconds=round(float(capture._times[-1]-actual_end), 9),
                        start_pip=first, end_pip_exclusive=last+1,
                        sample_count=count, source_pips_per_beat=64)


def analyse_source_capture(capture, output_dir, *, original_source_sha256=None,
                           min_bpm=60.0, max_bpm=200.0, target_bpm=None,
                           max_previews=4, verify_native=False,
                           full_motion_confidence_threshold=DEFAULT_THRESHOLD,
                           export_full_motion=True):
    """Produce a new, transactional analysis directory and optional preview motions.

    Every preview is derived FROM a StemLab source-time loop candidate, never from
    the already quantised full-action recording. No third-party files are fetched.
    No automatically inferred loop is approved or made to repeat at runtime.
    """
    if not isinstance(capture, RigCapture):
        raise ScoreError('Expected source-time RigCapture (not a compiled RigMotion)')
    if type(max_previews) is not int or not 0 <= max_previews <= MAX_PREVIEWS:
        raise ValueError(f'max_previews must be 0..{MAX_PREVIEWS}')
    if not 30 <= _real(min_bpm, 'min_bpm') < _real(max_bpm, 'max_bpm') <= 300:
        raise ValueError('BPM range must be within 30..300 and strictly increasing')
    if target_bpm is not None and not 30 <= _real(target_bpm, 'target_bpm') <= 300:
        raise ValueError('target_bpm must be within 30..300')
    if type(export_full_motion) is not bool:
        raise ValueError('export_full_motion must be true or false')
    if (type(full_motion_confidence_threshold) not in (float, int)
            or not math.isfinite(full_motion_confidence_threshold)
            or not 0 <= full_motion_confidence_threshold <= 1):
        raise ValueError('Full-motion confidence threshold must be within 0..1')
    if original_source_sha256 is not None and (not isinstance(original_source_sha256, str)
            or len(original_source_sha256) != 64
            or any(d not in '0123456789abcdef' for d in original_source_sha256)):
        raise ValueError('original_source_sha256 must be a lowercase SHA-256')
    analyze_rig_capture, write_rig_analysis = _stemlab()
    output_dir = Path(output_dir).expanduser().absolute()
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f'Choose a fresh analysis directory: {output_dir}')
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    # Project-local temporary files; commit a complete result only after validation.
    with tempfile.TemporaryDirectory(prefix='.source-loop-', dir=output_dir.parent) as directory:
        stage = Path(directory) / 'result'
        stage.mkdir()
        capture_path = stage / 'source.capture.json'
        write_capture(capture_path, capture)
        digest = hashlib.sha256(capture_path.read_bytes()).hexdigest()
        report = analyze_rig_capture(capture_path, min_bpm=min_bpm, max_bpm=max_bpm)
        if (report.get('format') != 'stemlab.rig-motion-analysis'
                or report.get('source_kind') != 'capture'
                or report.get('source_file_sha256') != digest
                or report.get('profile_sha256') != capture.profile.fingerprint
                or report.get('type_uri') != capture.profile.type_uri):
            raise ValueError('StemLab report does not match the exact input source capture')
        write_rig_analysis(stage / 'stemlab-analysis.json', report)
        if report.get('estimated_beat_map') is not None:
            from .recording import _write_json_document
            _write_json_document(stage / 'estimated-source-beats.json', report['estimated_beat_map'])
        fit = assess_full_motion(report, capture,
            confidence_threshold=full_motion_confidence_threshold)
        full = []
        if export_full_motion and fit['auto_convert']:
            try:
                presentation = target_bpm if target_bpm is not None else fit['selected_bpm']
                full_motion, boundaries = _full_action_recording(capture, fit,
                    presentation_bpm=presentation,
                    original_source_sha256=original_source_sha256)
                (stage / 'full-length').mkdir()
                path = 'full-length/source_full_action.motion.json'
                write_rig_motion(stage / path, full_motion)
                native = _native_check(full_motion) if verify_native else False
                full.append(dict(filename=path,
                    recording_sha256=hashlib.sha256((stage/path).read_bytes()).hexdigest(),
                    source_original_sha256=original_source_sha256,
                    source_capture_sha256=digest,
                    profile_sha256=capture.profile.fingerprint,
                    motion_type='complete_source_action', loopable=False,
                    bpm_estimated=fit['selected_bpm'],
                    target_bpm_nominal=round(float(presentation), 6),
                    confidence=fit['confidence'],
                    confidence_percent=fit['confidence_percent'],
                    confidence_method=fit['method'],
                    native_samples_verified=native, requires_review=True,
                    audio_beat_alignment_verified=False, **boundaries))
            except (ScoreError, ValueError) as exc:
                fit['auto_convert'] = False
                fit['reasons'].append('full_conversion_unavailable: '+str(exc))
        choices, rejected = _preview_eligible(report, capture, target_bpm=target_bpm)
        summaries = []
        if max_previews:
            (stage / 'previews').mkdir()
        for rank, index, candidate, source_bpm, speed_ratio in choices[:max_previews]:
            start = float(candidate['start_seconds'])
            beats = candidate['beats']
            # Fit the exact candidate interval; rounded evidence start/end may
            # differ by a fraction of a frame from its nominal BPM hypothesis.
            source_map = BeatMap.from_bpm(str(source_bpm), beat_zero_seconds=str(start),
                source='StemLab motion-only estimated beat-grid loop; not audio-confirmed',
                bpm_status='estimated', phase_status='estimated')
            presentation_bpm = target_bpm if target_bpm is not None else source_bpm
            clock = RecordingClock(float(presentation_bpm),
                'Motion-only estimated source grid; target BPM is a preview tempo',
                'estimated', 0., 'estimated', 0)
            name = f'loop_{index+1:03d}_{beats:02d}beats'
            motion = compile_capture(capture, name=name, source_beat_map=source_map,
                                     clock=clock, sample_count=beats*64)
            motion = _annotate_motion(motion, motion_kind='source_loop_candidate',
                suggested_loop_period_pips=beats*64,
                suggested_loop_boundary='start_inclusive_end_exclusive',
                suggested_loop_playback='repeat_after_manual_review',
                source_original_sha256=original_source_sha256,
                musical_timing_verified=False, repeat_seam_verified=False)
            filename = f'previews/{name}.motion.json'
            write_rig_motion(stage / filename, motion)
            native = _native_check(motion) if verify_native else False
            summaries.append(dict(source_candidate_index=index, filename=filename,
                recording_sha256=hashlib.sha256((stage / filename).read_bytes()).hexdigest(),
                source_start_seconds=start, source_end_seconds=float(candidate['end_seconds']),
                source_beats=beats, source_bpm_estimated=round(source_bpm, 6),
                target_bpm_nominal=round(float(presentation_bpm), 6),
                speed_ratio=round(speed_ratio, 6), score=round(rank, 6),
                stemlab_score=candidate['score'], stemlab_diagnostics=candidate,
                start_pip=0, end_pip_exclusive=beats*64, native_samples_verified=native,
                motion_type='loopable_candidate', recommended_loop_pips=beats*64,
                suggested_playback='repeat_after_manual_review',
                requires_review=True, loop_seam_approved=False,
                mesh_deformation_verified=False, audio_beat_alignment_verified=False))
        # Separate catalogue from complete source Actions; these paths reference
        # the native previews instead of copying large rig payloads twice.
        loop_catalogue = dict(format='dancerudiments.loopable-motion-candidates',
            schema_version=1, confidence_interpretation='source_motion_heuristics_only',
            original_source_sha256=original_source_sha256,
            source_capture_sha256=digest,
            clips=[dict(x) for x in summaries])
        (stage / 'loopable-clips.json').write_text(
            json.dumps(loop_catalogue, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        document = dict(format=FORMAT, schema_version=1,
            source_kind='original_bvh_or_blender_capture',
            source_original_sha256=original_source_sha256,
            source_capture_sha256=digest,
            profile_sha256=capture.profile.fingerprint, type_uri=capture.profile.type_uri,
            stemlab_analysis_file='stemlab-analysis.json',
            stemlab_analysis_sha256=hashlib.sha256((stage / 'stemlab-analysis.json').read_bytes()).hexdigest(),
            source_clock='original source seconds', pips_per_beat=64,
            inferred_tempo_verified=False, confirmed_musical_downbeat=False,
            full_motion_fit=fit, full_motion_confidence_threshold=full_motion_confidence_threshold,
            full_motion_count=len(full), full_motion_clips=full,
            full_motion_shortlisted=bool(full),
            loopable_clip_count=len(summaries), loopable_clips=summaries,
            loopable_catalogue_file='loopable-clips.json',
            max_previews=max_previews, preview_count=len(summaries), previews=summaries,
            unconverted_candidate_count=len(report.get('loop_candidates', [])) - len(summaries),
            rejected_candidates=rejected,
            limitations=['Full original Actions remain unchanged and non-looping.',
                'Motion beat grids, bar phase and loop rankings are hypotheses, not music synchronisation.',
                'Full-length grid-fit confidence is an uncalibrated heuristic, not a probability.',
                'Native sample checks do not prove foot contacts or skinned mesh continuity.',
                'Source licenses, retargeting compatibility and final seam transitions require separate review.'])
        (stage / 'job.json').write_text(json.dumps(document, indent=2, allow_nan=False) + '\n',
                                        encoding='utf-8')
        if output_dir.exists() or output_dir.is_symlink():
            raise FileExistsError(f'Analysis output appeared during execution: {output_dir}')
        stage.rename(output_dir)
    return document
